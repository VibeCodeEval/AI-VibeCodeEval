"""
N8 다중 에이전트 토론 SubGraph

[구조]
Round 1 (병렬): r1_strict | r1_advocate | r1_neutral
    → sync_opinions (팬인)
Round 2 (순차): r2_strict → r2_advocate → r2_neutral
    → final_verdict

[에이전트 역할]
- strict   (Gemini 2.5 Pro,   temp=0.1): 검사  — 코드 결함·비효율·프롬프트 품질 문제 집중
- advocate (Gemini 2.0 Flash, temp=0.3): 변호인 — 코드 강점·노력·문제 맥락 고려
- neutral  (Gemini 2.5 Pro,   temp=0.2): 중재자 — 균형 평가

Round 2에서 각 에이전트는 Round 1의 다른 두 에이전트 의견을 참고하여 입장을 재검토합니다.
final_verdict는 6개 의견(Round 1 × 3 + Round 2 × 3)을 모두 취합하여 최종 점수를 도출합니다.
"""

import json
import logging
from typing import Any, Dict, List, Tuple, Union

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from pydantic import BaseModel, Field

from app.domain.langgraph.nodes.eval_turn.utils import get_llm_for_model
from app.domain.langgraph.prompts import load_prompt
from app.domain.langgraph.states import DebateState

logger = logging.getLogger(__name__)

# ============================================================
# LLM 팩토리 (N4 턴 평가와 동일: GEMINI_API_KEY / Vertex)
# ============================================================

# YAML에서 에이전트 설정 로드 (모델명, temperature, 시스템 프롬프트)
_AGENT_CONFIG: Dict[str, Dict[str, Any]] = {
    role: load_prompt("debate_agents", section=role)
    for role in ("strict", "advocate", "neutral", "verdict")
}


def _make_llm(role: str):
    """역할에 맞는 LLM 인스턴스 생성 (debate_agents.yaml 설정 기반)"""
    cfg = _AGENT_CONFIG[role]
    model_name = cfg["model"]
    temperature = float(cfg["temperature"])
    return get_llm_for_model(model_name, temperature)


# ============================================================
# Pydantic 출력 모델
# ============================================================

class AgentOpinion(BaseModel):
    """개별 에이전트의 의견"""
    agent: str = Field(..., description="에이전트 역할 (strict / advocate / neutral)")
    round: int = Field(..., description="라운드 번호 (1 또는 2)")
    stance: str = Field(..., description="평가 입장 요약 (1~2문장)")
    code_quality_assessment: str = Field(..., description="코드 품질 정성 평가")
    prompt_quality_assessment: str = Field(..., description="프롬프트 활용 품질 정성 평가")
    suggested_score: float = Field(..., ge=0.0, le=100.0, description="제안 점수 (0-100)")
    key_points: List[str] = Field(..., description="핵심 근거 목록 (3~5개)")


class FinalVerdict(BaseModel):
    """최종 판결 결과"""
    holistic_flow_score: float = Field(..., ge=0.0, le=100.0, description="최종 종합 점수 (0-100)")
    r4_context_maintenance_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="R4 대화 맥락 유지 점수 (0-100), turn_scores 전체 궤적 기반",
    )
    grade: str = Field(..., description="등급 (A/B/C/D/F)")
    consensus_summary: str = Field(..., description="토론 합의 요약")
    holistic_flow_analysis: str = Field(..., description="종합 분석 (코드 품질 + 프롬프트 활용)")
    score_rationale: str = Field(..., description="최종 점수 도출 근거")


# ============================================================
# 컨텍스트 빌더 유틸
# ============================================================

def _build_base_context(state: DebateState) -> str:  # noqa: C901
    """
    모든 에이전트가 공통으로 받을 평가 컨텍스트 문자열 생성

    포함 정보:
    - 문제 설명 + 제출 코드
    - N5 Judge0: 정확성/성능 점수 + 실행 시간/메모리/TC 상세 + 오류 원인
    - N6 Radon CC: 복잡도 + Junior Grade 플래그
    - N7 LLM 코드 리뷰: 효율성/가독성/예외처리/종합 요약
    - N4 턴별 숫자 점수 + Redis turn_logs (대화 원문 요약 + LLM 평가 내용 전문)
    """
    problem_context = state.get("problem_context") or {}
    code_content = state.get("code_content") or "(코드 없음)"
    quality = state.get("code_quality_metrics") or {}
    eval_report = state.get("code_eval_report") or {}
    turn_scores = state.get("turn_scores") or {}
    agg_turn = state.get("aggregate_turn_score")
    turn_logs = state.get("turn_logs") or {}

    # N5 상세 지표
    correctness = state.get("code_correctness_score")
    performance = state.get("code_performance_score")
    tc_passed = state.get("test_cases_passed")
    tc_total = state.get("test_cases_total")
    exec_time = state.get("execution_time")
    mem_mb = state.get("memory_used_mb")
    c_reason = state.get("correctness_reasoning") or ""

    basic_info = problem_context.get("basic_info", {})
    problem_desc = basic_info.get("description", "설명 없음")

    radon = quality.get("radon_cc", {})
    delta = quality.get("delta_cc", {})

    # ── N5 포맷 ─────────────────────────────────────────────────────────
    tc_str = f"{tc_passed}/{tc_total}" if tc_total is not None else "N/A"
    exec_str = f"{exec_time:.3f}초" if exec_time is not None else "N/A"
    mem_str = f"{mem_mb:.2f}MB" if mem_mb is not None else "N/A"
    c_reason_str = f"\n  오류 원인: {c_reason}" if c_reason else ""

    judge0_section = (
        f"[Judge0 코드 실행 결과]\n"
        f"- 정확성 점수(Correctness): {correctness}\n"
        f"- 성능 점수(Performance): {performance}\n"
        f"- 테스트 케이스 통과: {tc_str}\n"
        f"- 실행 시간: {exec_str}\n"
        f"- 메모리 사용: {mem_str}{c_reason_str}"
    )

    # ── N6 Radon CC ──────────────────────────────────────────────────────
    radon_section = (
        f"[Radon CC 정적 분석]\n"
        f"- 평균 순환 복잡도(avg_cc): {radon.get('avg_cc', 'N/A')}\n"
        f"- 최대 순환 복잡도(max_cc): {radon.get('max_cc', 'N/A')}\n"
        f"- Delta CC (%): {delta.get('delta_cc_pct', 'N/A')}\n"
        f"- Junior Grade 플래그: {quality.get('junior_grade', False)}"
    )

    # ── N7 LLM 코드 리뷰 ────────────────────────────────────────────────
    n7_section = (
        f"[N7 LLM 코드 리뷰]\n"
        f"- 효율성: {eval_report.get('efficiency_review', 'N/A')}\n"
        f"- 가독성: {eval_report.get('readability_review', 'N/A')}\n"
        f"- 예외 처리: {eval_report.get('error_handling_review', 'N/A')}\n"
        f"- 종합 요약: {eval_report.get('overall_summary', 'N/A')}"
    )

    # ── N4 턴별 숫자 점수 + 상세 대화 로그 ──────────────────────────────
    # turn_scores는 집계 숫자, turn_logs는 Redis에서 읽은 전체 상세 내용
    sorted_turn_keys = sorted(
        set(list(turn_scores.keys()) + list(turn_logs.keys())),
        key=lambda k: _turn_sort_key(str(k)),
    )

    turn_lines: List[str] = []
    for t_key in sorted_turn_keys:
        score_data = turn_scores.get(t_key) or {}
        log_data = turn_logs.get(t_key) or {}

        score_val = score_data.get("turn_score", "N/A") if isinstance(score_data, dict) else score_data

        user_prompt = log_data.get("user_prompt_summary") or log_data.get("user_prompt") or ""
        llm_answer = log_data.get("llm_answer_summary") or log_data.get("llm_answer") or ""
        eval_details = log_data.get("prompt_evaluation_details") or {}

        header = f"  [턴 {t_key}] 점수: {score_val}"
        turn_lines.append(header)

        if user_prompt:
            turn_lines.append(f"    ▶ 사용자 프롬프트 요약: {user_prompt}")
        if llm_answer:
            turn_lines.append(f"    ◀ AI 응답 요약: {llm_answer}")

        if eval_details:
            intent = eval_details.get("intent") or eval_details.get("evaluation_intent") or ""
            if intent:
                turn_lines.append(f"    📌 평가 의도: {intent}")

            # V3.0: rubric_breakdown(Dict[str,int]) 우선, 이전 포맷(rubrics/rubric_scores) 폴백
            applied = eval_details.get("applied_rubrics") or []
            rubrics = (
                eval_details.get("rubric_breakdown")
                or eval_details.get("rubrics")
                or eval_details.get("rubric_scores")
                or {}
            )
            if applied:
                turn_lines.append(f"    🏷 적용 루브릭: {', '.join(applied)}")
            if isinstance(rubrics, dict):
                for r_name, r_val in rubrics.items():
                    if isinstance(r_val, dict):
                        r_score = r_val.get("score", "N/A")
                        r_reason = r_val.get("reasoning") or r_val.get("reason") or ""
                        turn_lines.append(f"    · {r_name}: {r_score}점  {r_reason}")
                    else:
                        # V3.0 형식: 단순 정수 점수 (1~5)
                        turn_lines.append(f"    · {r_name}: {r_val}점")
            elif isinstance(rubrics, list):
                for r_item in rubrics:
                    if isinstance(r_item, dict):
                        r_name = r_item.get("name") or r_item.get("rubric", "")
                        r_score = r_item.get("score", "N/A")
                        r_reason = r_item.get("reasoning") or r_item.get("reason") or ""
                        turn_lines.append(f"    · {r_name}: {r_score}점  {r_reason}")

            final_reasoning = eval_details.get("final_reasoning") or eval_details.get("reasoning") or ""
            if final_reasoning:
                turn_lines.append(f"    💬 종합 평가: {final_reasoning}")

    turn_detail_section = "\n".join(turn_lines) if turn_lines else "  (없음)"

    return f"""== 문제 설명 ==
{problem_desc}

== 제출 코드 ==
```
{code_content}
```

== 객관적 평가 지표 ==
{judge0_section}

{radon_section}

{n7_section}

== 턴별 대화 로그 및 평가 내용 (N4) ==
평균 프롬프트 점수: {agg_turn}
{turn_detail_section}"""


def _turn_sort_key(key: str) -> Tuple[int, Union[int, str]]:
    """turn_scores 키 정렬: 숫자 키 우선, 그 외는 문자열 순."""
    s = str(key)
    if s.isdigit():
        return (0, int(s))
    return (1, s)


def _format_turn_scores_trajectory(turn_scores: Dict[str, Any]) -> str:
    """R4 채점용: 턴별 기록 전체를 JSON으로 직렬화 (순서 보존)."""
    if not turn_scores:
        return "{}"
    ordered = dict(
        sorted(turn_scores.items(), key=lambda kv: _turn_sort_key(str(kv[0])))
    )
    try:
        return json.dumps(ordered, ensure_ascii=False, indent=2, default=str)
    except TypeError:
        return json.dumps(
            {str(k): str(v) for k, v in ordered.items()},
            ensure_ascii=False,
            indent=2,
        )


def _fallback_r4_from_turn_scores(turn_scores: Dict[str, Any]) -> float:
    """
    LLM 판결 실패 시 turn_scores 궤적에서 보수적 추정.
    턴 점수 추세(개선/악화)와 평균을 반영.
    """
    rows: List[Tuple[Tuple[int, Union[int, str]], float]] = []
    for k, v in (turn_scores or {}).items():
        if not isinstance(v, dict) or "turn_score" not in v:
            continue
        try:
            ts = float(v["turn_score"])
        except (TypeError, ValueError):
            continue
        rows.append((_turn_sort_key(str(k)), ts))
    rows.sort(key=lambda x: x[0])
    scores = [s for _, s in rows]
    if not scores:
        return 50.0
    if len(scores) == 1:
        return round(min(100.0, max(0.0, scores[0])), 2)
    first, last = scores[0], scores[-1]
    mid = (first + last) / 2.0
    trend = last - first
    adjusted = mid + max(-12.0, min(12.0, trend * 0.4))
    return round(min(100.0, max(0.0, adjusted)), 2)


def _format_opinions(opinions: List[Dict[str, Any]], exclude_agent: str = "") -> str:
    """의견 목록을 읽기 쉬운 문자열로 변환 (자신 제외 가능)"""
    lines = []
    for op in opinions:
        if op.get("agent") == exclude_agent:
            continue
        lines.append(
            f"[{op.get('agent', '?')} / Round {op.get('round', '?')}]\n"
            f"  입장: {op.get('stance', '')}\n"
            f"  제안 점수: {op.get('suggested_score', 'N/A')}\n"
            f"  핵심 근거: {'; '.join(op.get('key_points', []))}"
        )
    return "\n\n".join(lines) if lines else "(없음)"


# ============================================================
# 시스템 프롬프트 (debate_agents.yaml에서 로드)
# ============================================================

def _sys(role: str) -> str:
    """role에 해당하는 시스템 프롬프트 반환 (YAML 캐시 활용)"""
    return _AGENT_CONFIG[role]["system"]


# ============================================================
# Round 1 노드 (병렬)
# ============================================================

async def _run_round1_agent(state: DebateState, role: str) -> Dict[str, Any]:
    base_ctx = _build_base_context(state)
    human_content = f"""{base_ctx}

위 정보를 바탕으로 당신의 역할({role})에 맞게 평가 의견을 제시하십시오.
반드시 `agent` 필드를 "{role}"로 설정하고, `round` 필드를 1로 설정하십시오."""

    try:
        llm = _make_llm(role)
        structured = llm.with_structured_output(AgentOpinion)
        result: AgentOpinion = await structured.ainvoke([
            SystemMessage(content=_sys(role)),
            HumanMessage(content=human_content),
        ])
        opinion = result.model_dump()
        opinion["agent"] = role
        opinion["round"] = 1
        logger.info(f"[Debate R1/{role}] 의견 생성 완료 - 제안 점수: {opinion['suggested_score']}")
        return {"initial_opinions": [opinion]}
    except Exception as e:
        logger.error(f"[Debate R1/{role}] 실패: {e}", exc_info=True)
        fallback = {
            "agent": role, "round": 1,
            "stance": "평가 실패", "code_quality_assessment": str(e),
            "prompt_quality_assessment": "", "suggested_score": 50.0, "key_points": [],
        }
        return {"initial_opinions": [fallback]}


async def r1_strict(state: DebateState) -> Dict[str, Any]:
    return await _run_round1_agent(state, "strict")


async def r1_advocate(state: DebateState) -> Dict[str, Any]:
    return await _run_round1_agent(state, "advocate")


async def r1_neutral(state: DebateState) -> Dict[str, Any]:
    return await _run_round1_agent(state, "neutral")


# ============================================================
# sync_opinions: Round 1 팬인 동기화 노드 (패스스루)
# ============================================================

async def sync_opinions(state: DebateState) -> Dict[str, Any]:
    opinions = state.get("initial_opinions", [])
    logger.info(f"[Debate sync] Round 1 의견 {len(opinions)}개 수집 완료")
    scores = [op.get("suggested_score", 50) for op in opinions]
    avg = sum(scores) / len(scores) if scores else 50
    logger.info(f"[Debate sync] Round 1 평균 제안 점수: {avg:.1f}")
    return {}


# ============================================================
# Round 2 노드 (순차)
# ============================================================

async def _run_round2_agent(state: DebateState, role: str) -> Dict[str, Any]:
    base_ctx = _build_base_context(state)
    initial_opinions = state.get("initial_opinions", [])
    rebuttals_so_far = state.get("rebuttals", [])

    others_r1 = _format_opinions(initial_opinions, exclude_agent=role)
    own_r1 = next(
        (op for op in initial_opinions if op.get("agent") == role),
        None,
    )
    own_r1_text = (
        f"입장: {own_r1.get('stance', '')}\n제안 점수: {own_r1.get('suggested_score')}"
        if own_r1
        else "(없음)"
    )
    rebuttals_text = _format_opinions(rebuttals_so_far) if rebuttals_so_far else "(아직 없음)"

    human_content = f"""{base_ctx}

== Round 1 당신의 의견 ==
{own_r1_text}

== Round 1 다른 평가관 의견 ==
{others_r1}

== Round 2 선행 반론 (있는 경우) ==
{rebuttals_text}

위 내용을 참고하여 Round 2 입장을 재검토하십시오.
다른 평가관의 논거 중 수용할 부분이 있다면 반영하고, 동의하지 않는다면 근거를 강화하십시오.
반드시 `agent` 필드를 "{role}"로 설정하고, `round` 필드를 2로 설정하십시오."""

    try:
        llm = _make_llm(role)
        structured = llm.with_structured_output(AgentOpinion)
        result: AgentOpinion = await structured.ainvoke([
            SystemMessage(content=_sys(role)),
            HumanMessage(content=human_content),
        ])
        rebuttal = result.model_dump()
        rebuttal["agent"] = role
        rebuttal["round"] = 2
        logger.info(f"[Debate R2/{role}] 반론 완료 - 제안 점수: {rebuttal['suggested_score']}")
        return {"rebuttals": [rebuttal]}
    except Exception as e:
        logger.error(f"[Debate R2/{role}] 실패: {e}", exc_info=True)
        fallback = {
            "agent": role, "round": 2,
            "stance": "반론 실패", "code_quality_assessment": str(e),
            "prompt_quality_assessment": "", "suggested_score": 50.0, "key_points": [],
        }
        return {"rebuttals": [fallback]}


async def r2_strict(state: DebateState) -> Dict[str, Any]:
    return await _run_round2_agent(state, "strict")


async def r2_advocate(state: DebateState) -> Dict[str, Any]:
    return await _run_round2_agent(state, "advocate")


async def r2_neutral(state: DebateState) -> Dict[str, Any]:
    return await _run_round2_agent(state, "neutral")


# ============================================================
# final_verdict: 최종 판결
# ============================================================

async def final_verdict(state: DebateState) -> Dict[str, Any]:
    initial_opinions = state.get("initial_opinions", [])
    rebuttals = state.get("rebuttals", [])
    all_opinions = initial_opinions + rebuttals

    all_opinions_text = _format_opinions(all_opinions)
    base_ctx = _build_base_context(state)

    r1_scores = [op.get("suggested_score", 50) for op in initial_opinions]
    r2_scores = [op.get("suggested_score", 50) for op in rebuttals]
    r1_avg = sum(r1_scores) / len(r1_scores) if r1_scores else 50
    r2_avg = sum(r2_scores) / len(r2_scores) if r2_scores else 50

    turn_scores = state.get("turn_scores") or {}
    trajectory_json = _format_turn_scores_trajectory(turn_scores)

    human_content = f"""{base_ctx}

== 턴별 점수 전체 궤적 (R4 채점용 JSON) ==
{trajectory_json}

== 전체 토론 기록 (총 {len(all_opinions)}개 의견) ==
{all_opinions_text}

== 참고 통계 ==
- Round 1 평균 제안 점수: {r1_avg:.1f}
- Round 2 평균 제안 점수: {r2_avg:.1f}

위 토론 전체와 턴 궤적 JSON을 검토하여 최종 판결을 내리십시오.
3명의 평가관이 합의한 사항과 이견이 있는 사항을 구분하고,
증거에 기반한 공정한 최종 점수·R4 맥락 유지 점수·종합 분석을 제시하십시오."""

    try:
        llm = _make_llm("verdict")
        structured = llm.with_structured_output(FinalVerdict)
        result: FinalVerdict = await structured.ainvoke([
            SystemMessage(content=_sys("verdict")),
            HumanMessage(content=human_content),
        ])
        verdict_dict = result.model_dump()
        r4 = verdict_dict["r4_context_maintenance_score"]
        logger.info(
            f"[Debate Verdict] 최종 점수: {verdict_dict['holistic_flow_score']}, "
            f"R4: {r4}, 등급: {verdict_dict['grade']}"
        )
        debate_log = [op.copy() for op in all_opinions]
        debate_log.append({
            "agent": "verdict",
            "round": 0,
            "holistic_flow_score": verdict_dict["holistic_flow_score"],
            "r4_context_maintenance_score": r4,
            "grade": verdict_dict["grade"],
            "consensus_summary": verdict_dict["consensus_summary"],
        })
        return {
            "holistic_flow_score": verdict_dict["holistic_flow_score"],
            "r4_context_maintenance_score": r4,
            "holistic_flow_analysis": (
                f"[합의 요약] {verdict_dict['consensus_summary']}\n\n"
                f"[종합 분석] {verdict_dict['holistic_flow_analysis']}\n\n"
                f"[점수 근거] {verdict_dict['score_rationale']}\n\n"
                f"[R4 맥락 유지] {r4:.1f}/100 (turn_scores 궤적 기반 수석 심사관 산정)"
            ),
            "debate_log": debate_log,
        }
    except Exception as e:
        logger.error(f"[Debate Verdict] 최종 판결 실패: {e}", exc_info=True)
        all_scores = [op.get("suggested_score", 50) for op in all_opinions]
        fallback_score = sum(all_scores) / len(all_scores) if all_scores else 50.0
        r4_fb = _fallback_r4_from_turn_scores(state.get("turn_scores") or {})
        return {
            "holistic_flow_score": round(fallback_score, 2),
            "r4_context_maintenance_score": r4_fb,
            "holistic_flow_analysis": (
                f"최종 판결 생성 실패 — holistic 평균({fallback_score:.1f}), "
                f"R4 궤적 추정({r4_fb:.1f})로 대체. 오류: {e}"
            ),
            "debate_log": all_opinions,
        }


# ============================================================
# SubGraph 생성
# ============================================================

def create_debate_subgraph():
    """
    N8 다중 에이전트 토론 SubGraph 생성 및 컴파일

    플로우:
    START → init_debate → [Send()] r1_strict | r1_advocate | r1_neutral
          → sync_opinions
          → r2_strict → r2_advocate → r2_neutral
          → final_verdict → END
    """
    builder = StateGraph(DebateState)

    # 노드 등록
    builder.add_node("r1_strict", r1_strict)
    builder.add_node("r1_advocate", r1_advocate)
    builder.add_node("r1_neutral", r1_neutral)
    builder.add_node("sync_opinions", sync_opinions)
    builder.add_node("r2_strict", r2_strict)
    builder.add_node("r2_advocate", r2_advocate)
    builder.add_node("r2_neutral", r2_neutral)
    builder.add_node("final_verdict", final_verdict)

    # START → Round 1 병렬 (Send() API)
    builder.add_conditional_edges(
        START,
        lambda state: [
            Send("r1_strict", state),
            Send("r1_advocate", state),
            Send("r1_neutral", state),
        ],
    )

    # Round 1 팬인 → sync_opinions
    for node in ["r1_strict", "r1_advocate", "r1_neutral"]:
        builder.add_edge(node, "sync_opinions")

    # sync_opinions → Round 2 순차
    builder.add_edge("sync_opinions", "r2_strict")
    builder.add_edge("r2_strict", "r2_advocate")
    builder.add_edge("r2_advocate", "r2_neutral")

    # Round 2 → 최종 판결 → END
    builder.add_edge("r2_neutral", "final_verdict")
    builder.add_edge("final_verdict", END)

    return builder.compile()
