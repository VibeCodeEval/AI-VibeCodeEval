#!/usr/bin/env python
"""
WizardLM Evol-Instruct 기법으로 v2.1 Seed 프롬프트를 진화시키고, 평가 노드에 태워 reasoning 추출.

[Seed]
- v21_rubric_60.jsonl 또는 generate_synthetic_v21_data의 등급별 기본 프롬프트를 Seed로 사용.

[5단계 진화] (각 Seed에 대해 랜덤 1종 적용)
1. Add Constraints: 시간 복잡도, 특정 라이브러리 미사용 등 물리적 제약 추가.
2. Deepening: 아키텍처적 깊이(Interface 상속 관계 명시 등) 심화.
3. Complicating Input: 입력 데이터 구조를 더 복잡하게 변형.
4. Reasoning Step: "왜 그렇게 설계해야 하는지 논리적 근거를 포함해서 지시해줘."
5. Situation Switching: 공항 → 병원, 은행 등 다른 도메인으로 지시 상황 변경.

[평가 노드 순회]
- --run-eval: 진화된 프롬프트를 Eval Turn SubGraph에 넣어 턴 점수(turn_score), 루브릭(rubrics), reasoning(eval_reasoning) 추출.
- ΔCC, AST 등 코드 품질 지표는 전체 제출 플로우(DB 세션 + EvalService.submit_code)에서 나옴. 진화된 JSONL을 DB에 넣은 뒤 run_synthetic_session_eval.py로 실행하면 됨.

[출력 JSONL 필드]
- seed_label, evolution_type, instruction, instruction_phase2, instruction_evolved_text, context, v2_code, metrics, label, analysis_reasoning, evaluation_log
- --run-eval 시 추가: eval_turn_score, eval_intent_types, eval_intent_confidence, eval_rubrics, eval_reasoning

사용법:
  uv run python scripts/evol_instruction_v21.py --input v21_rubric_60.jsonl -o v21_evol.jsonl
  uv run python scripts/evol_instruction_v21.py --input v21_rubric_60.jsonl -o v21_evol.jsonl --run-eval
  uv run python scripts/evol_instruction_v21.py --input v21_rubric_60.jsonl -o v21_evol.jsonl --max-samples 10
"""

import argparse
import asyncio
import json
import logging
import random
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)

# 5단계 진화 유형 (Evol-Instruct)
EVOLUTION_TYPES = [
    "add_constraints",      # 시간 복잡도, 라이브러리 제약 등
    "deepening",            # Interface 상속·아키텍처 깊이
    "complicating_input",   # 입력 구조 복잡화
    "reasoning_step",       # 설계 근거 포함 지시
    "situation_switching",  # 도메인 변경 (공항→병원/은행 등)
]

# 진화 유형별 LLM 지시문 (한국어)
EVOLUTION_PROMPTS = {
    "add_constraints": (
        "다음 사용자 지시문(Seed)을 **물리적 제약을 추가**한 버전으로 한 문단만 다시 써줘. "
        "예: 시간 복잡도 O(n) 이하로, 외부 라이브러리 미사용, 메모리 제한 등. "
        "의미와 요구사항은 유지하고, 제약만 구체적으로 추가해줘. 다른 설명 없이 진화된 지시문만 출력."
    ),
    "deepening": (
        "다음 사용자 지시문(Seed)을 **아키텍처적 깊이를 더한** 버전으로 한 문단만 다시 써줘. "
        "예: Interface/추상 클래스 상속 관계 명시, 전략 패턴·의존성 주입 등 설계 용어를 구체적으로 넣어줘. "
        "의미는 유지하고, 설계 수준만 심화해줘. 다른 설명 없이 진화된 지시문만 출력."
    ),
    "complicating_input": (
        "다음 사용자 지시문(Seed)을 **입력 데이터 구조가 더 복잡한** 시나리오로 바꾼 버전으로 한 문단만 다시 써줘. "
        "예: 단일 객체가 아니라 리스트/중첩 구조, 여러 조건 조합, 예외 케이스 명시 등. "
        "같은 도메인(공항 게이트)을 유지하면서 입력만 복잡하게 해줘. 다른 설명 없이 진화된 지시문만 출력."
    ),
    "reasoning_step": (
        "다음 사용자 지시문(Seed)을 **왜 그렇게 설계해야 하는지 논리적 근거를 포함**한 지시로 한 문단만 다시 써줘. "
        "예: '확장 가능하게 만들어줘' → '확장 가능하게 만들어줘. 왜냐하면 이후 규칙 추가 시 기존 코드 수정 없이 규칙만 추가할 수 있어야 하기 때문이야.' "
        "의미는 유지하고, 이유/근거만 추가해줘. 다른 설명 없이 진화된 지시문만 출력."
    ),
    "situation_switching": (
        "다음 사용자 지시문(Seed)은 **공항 게이트** 도메인이다. 이를 **완전히 다른 도메인**으로 바꾼 지시문으로 한 문단만 써줘. "
        "도메인 예: 병원 접수/진료 우선순위, 은행 대출 심사 규칙, 주차장 입출차 요금 규칙 등. "
        "Seed와 같은 수준의 구체성(규칙 분리, 확장 가능성 등)을 유지하면서 상황만 바꿔줘. 다른 설명 없이 진화된 지시문만 출력."
    ),
}


def load_seeds(path: Path, max_samples: int | None) -> list[dict]:
    """JSONL에서 Seed 로드. max_samples 있으면 앞에서부터 제한."""
    seeds = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if max_samples is not None and i >= max_samples:
                break
            line = line.strip()
            if not line:
                continue
            seeds.append(json.loads(line))
    return seeds


def get_seed_instruction_text(seed: dict, phase: str = "phase2") -> str:
    """Seed에서 평가에 쓸 지시문 1개 추출. phase2면 Phase2 첫 문장, 아니면 Phase1 첫 문장."""
    if phase == "phase2":
        arr = seed.get("instruction_phase2") or seed.get("instruction") or []
    else:
        arr = seed.get("instruction") or []
    if not arr:
        return ""
    # SAVE 제외, 첫 번째 실제 지시문 사용 (또는 phase2 첫 문장)
    for x in arr:
        if isinstance(x, str) and x.strip() and x.strip().upper() != "SAVE":
            return x.strip()
    return arr[0] if arr else ""


async def evolve_with_llm(seed_instruction: str, evolution_type: str) -> str | None:
    """LLM으로 Seed 지시문을 진화 유형에 맞게 1문단 변환. 실패 시 None."""
    if evolution_type not in EVOLUTION_PROMPTS:
        return None
    prompt = (
        EVOLUTION_PROMPTS[evolution_type]
        + "\n\n[Seed]\n"
        + seed_instruction
    )
    try:
        from app.domain.langgraph.utils.llm_factory import get_llm
        llm = get_llm("writer")
        resp = llm.invoke(prompt)
        text = (resp.content if hasattr(resp, "content") else str(resp)).strip()
        # 한 줄로 정리 (앞뒤 따옴표 제거)
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
        return text[:2000] if text else None
    except Exception as e:
        logger.warning("LLM 진화 실패 (%s): %s", evolution_type, e)
        return None


def evolve_with_template(seed_instruction: str, evolution_type: str) -> str:
    """LLM 없이 템플릿으로 진화된 문장 반환 (폴백)."""
    if evolution_type == "add_constraints":
        return seed_instruction.rstrip(".") + ". 단, 시간 복잡도 O(n) 이하로 구현하고, 외부 라이브러리는 사용하지 말아줘."
    if evolution_type == "deepening":
        return seed_instruction.rstrip(".") + ". 규칙은 공통 Interface를 상속해 선언하고, GateManager는 전략 패턴으로 규칙만 주입받아 동작하게 해줘."
    if evolution_type == "complicating_input":
        return seed_instruction.rstrip(".") + ". 입력은 단일 객체가 아니라 여러 승객 리스트와 컨텍스트(날짜·위협수준·항공편별 과금 횟수)를 함께 받는 구조로 해줘."
    if evolution_type == "reasoning_step":
        return seed_instruction.rstrip(".") + ". 왜 그렇게 설계해야 하는지, 확장성과 유지보수 측면에서 이유를 한 줄씩 포함해서 지시해줘."
    if evolution_type == "situation_switching":
        return (
            "병원 접수 로직을 구현해줘. 환자 위급도, 예약 여부, 보험 검증을 규칙으로 분리하고, "
            "접수 매니저가 규칙을 순서대로 실행해 대기/진료/거절을 결정하게 만들어줘."
        )
    return seed_instruction


async def run_eval_turn_subgraph(
    human_message: str,
    problem_context: dict | None,
    session_id: str = "evol_single",
    turn: int = 1,
) -> dict:
    """진화된 프롬프트 1개를 Eval Turn SubGraph에 태워 턴 점수·reasoning 추출."""
    from app.domain.langgraph.states import EvalTurnState
    from app.domain.langgraph.subgraph_eval_turn import create_eval_turn_subgraph

    PLACEHOLDER_AI = "요청을 반영했습니다. (Evol-Instruct 평가용 placeholder)"
    eval_turn_subgraph = create_eval_turn_subgraph()

    turn_state: EvalTurnState = {
        "session_id": session_id,
        "turn": turn,
        "human_message": human_message,
        "ai_message": PLACEHOLDER_AI,
        "is_phase2_first_turn": None,
        "problem_context": problem_context,
        "is_guardrail_failed": False,
        "guardrail_message": None,
        "intent_types": None,
        "intent_confidence": 0.0,
        "unified_intent": None,
        "system_prompt_eval": None,
        "rule_setting_eval": None,
        "generation_eval": None,
        "optimization_eval": None,
        "debugging_eval": None,
        "test_case_eval": None,
        "hint_query_eval": None,
        "follow_up_eval": None,
        "answer_summary": None,
        "turn_log": None,
        "turn_score": None,
        "eval_tokens": None,
    }

    result = await eval_turn_subgraph.ainvoke(turn_state)
    turn_log = result.get("turn_log") or {}
    detailed_feedback = turn_log.get("detailed_feedback") or []
    rubrics = []
    for fb in detailed_feedback:
        if isinstance(fb, dict):
            rubrics.append({
                "name": fb.get("name", fb.get("criterion", "")),
                "score": fb.get("score", 0),
                "reasoning": fb.get("reasoning", ""),
            })
    comprehensive = turn_log.get("comprehensive_reasoning", "")
    return {
        "turn_score": result.get("turn_score"),
        "intent_types": result.get("intent_types", []),
        "intent_confidence": result.get("intent_confidence"),
        "rubrics": rubrics,
        "comprehensive_reasoning": comprehensive,
        "turn_log_summary": {
            "evaluations": turn_log.get("evaluations"),
            "detailed_feedback_count": len(detailed_feedback),
        },
    }


def get_problem_context_sync(spec_id: int = 20):
    """스마트 게이트 2026 problem_context 동기 로드."""
    try:
        from app.domain.langgraph.utils.problem_info import get_problem_info_sync
        return get_problem_info_sync(spec_id)
    except Exception:
        return None


def build_evolved_instruction_list(seed: dict, evolved_phase2: str, evolution_type: str) -> list:
    """Seed의 instruction 리스트에서 Phase2 첫 지시만 진화된 문장으로 교체한 새 리스트."""
    raw = seed.get("instruction") or []
    phase2_raw = seed.get("instruction_phase2") or []
    # Phase2 첫 번째 실제 지시 위치 찾기
    first_phase2_idx = None
    for i, s in enumerate(phase2_raw):
        if isinstance(s, str) and s.strip().upper() != "SAVE":
            first_phase2_idx = i
            break
    if first_phase2_idx is None:
        evolved_phase2_list = [evolved_phase2]
    else:
        evolved_phase2_list = list(phase2_raw)
        evolved_phase2_list[first_phase2_idx] = evolved_phase2
    # instruction은 Phase1 + SAVE + Phase2 형태 유지: Phase2 구간만 진화된 걸로
    out = list(raw)
    # instruction에서 phase2에 해당하는 부분 찾기 (보통 3번째부터가 Phase2)
    if len(out) >= 3:
        # 2번 인덱스(Phase2 첫 지시)를 진화문으로 교체
        out[2] = evolved_phase2
        if len(out) > 3:
            out[3] = evolved_phase2_list[1] if len(evolved_phase2_list) > 1 else out[3]
    else:
        out.append(evolved_phase2)
    return out


async def process_one(seed: dict, evolution_type: str, run_eval: bool, problem_context: dict | None) -> dict | None:
    """Seed 1건에 대해 진화 1회 + (선택) 평가 노드 순회."""
    seed_text = get_seed_instruction_text(seed, "phase2")
    if not seed_text:
        seed_text = get_seed_instruction_text(seed, "phase1")
    if not seed_text:
        logger.warning("Seed에서 지시문 추출 실패, 스킵")
        return None

    evolved = await evolve_with_llm(seed_text, evolution_type)
    if not evolved:
        evolved = evolve_with_template(seed_text, evolution_type)
        logger.info("LLM 폴백: 템플릿 진화 사용 (%s)", evolution_type)

    instruction_evolved = build_evolved_instruction_list(seed, evolved, evolution_type)
    instruction_phase2_evolved = seed.get("instruction_phase2") or []
    if instruction_phase2_evolved:
        instruction_phase2_evolved = list(instruction_phase2_evolved)
        for i, s in enumerate(instruction_phase2_evolved):
            if isinstance(s, str) and s.strip().upper() != "SAVE":
                instruction_phase2_evolved[i] = evolved
                break

    rec = {
        "seed_label": seed.get("label", ""),
        "evolution_type": evolution_type,
        "instruction": instruction_evolved,
        "instruction_phase2": instruction_phase2_evolved,
        "instruction_evolved_text": evolved,
        "context": seed.get("context"),
        "v2_code": seed.get("v2_code"),
        "metrics": seed.get("metrics"),
        "label": seed.get("label"),
        "analysis_reasoning": seed.get("analysis_reasoning"),
        "evaluation_log": seed.get("evaluation_log"),
    }

    if run_eval and problem_context is not None:
        eval_result = await run_eval_turn_subgraph(
            human_message=evolved,
            problem_context=problem_context,
            session_id="evol_" + evolution_type,
            turn=1,
        )
        rec["eval_turn_score"] = eval_result.get("turn_score")
        rec["eval_intent_types"] = eval_result.get("intent_types")
        rec["eval_intent_confidence"] = eval_result.get("intent_confidence")
        rec["eval_rubrics"] = eval_result.get("rubrics")
        rec["eval_reasoning"] = eval_result.get("comprehensive_reasoning")
        logger.info("평가 완료: turn_score=%s intent=%s", eval_result.get("turn_score"), eval_result.get("intent_types"))
    elif run_eval:
        rec["eval_reasoning"] = "(problem_context 없음, 평가 스킵)"
        rec["eval_turn_score"] = None

    return rec


async def main_async(args):
    seeds = load_seeds(args.input, args.max_samples)
    if not seeds:
        logger.error("Seed가 없습니다: %s", args.input)
        return 1

    problem_context = get_problem_context_sync() if args.run_eval else None
    if args.run_eval and not problem_context:
        logger.warning("problem_context 로드 실패. 평가는 reasoning 없이 스킵됩니다.")

    out_path = args.output
    if not Path(out_path).is_absolute():
        out_path = (Path.cwd() / out_path).resolve()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for i, seed in enumerate(seeds):
            evolution_type = random.choice(EVOLUTION_TYPES)
            rec = await process_one(seed, evolution_type, args.run_eval, problem_context)
            if rec:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                written += 1
            if (i + 1) % 10 == 0:
                logger.info("진행: %d/%d", i + 1, len(seeds))

    logger.info("총 %d건 진화 저장: %s", written, out_path)
    return 0


def main():
    parser = argparse.ArgumentParser(description="Evol-Instruct로 Seed 진화 + 선택적 평가 노드 순회")
    parser.add_argument("--input", "-i", default="v21_rubric_60.jsonl", help="Seed JSONL 경로")
    parser.add_argument("--output", "-o", default="v21_evol.jsonl", help="출력 JSONL 경로")
    parser.add_argument("--max-samples", type=int, default=None, help="처리할 Seed 최대 개수 (기본: 전부)")
    parser.add_argument("--run-eval", action="store_true", help="진화된 프롬프트를 Eval Turn SubGraph에 태워 reasoning 추출")
    parser.add_argument("--seed", type=int, default=None, help="random seed (재현용)")
    args = parser.parse_args()
    if args.seed is not None:
        random.seed(args.seed)
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
