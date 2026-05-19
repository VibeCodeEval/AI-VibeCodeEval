import logging
from datetime import datetime
from typing import Any, Dict

from app.domain.langgraph.nodes.eval_turn.grading import likert_to_final
from app.domain.langgraph.nodes.eval_turn.weights import (
    RUBRIC_NAME_MAP,
    legacy_turn_score_from_rubrics,
)
from app.domain.langgraph.states import EvalTurnState

logger = logging.getLogger(__name__)


def _get_rubric_scores_by_criterion(eval_results: dict) -> dict:
    """eval_results에서 루브릭별 점수를 추출 (criterion → score)."""
    out = {}
    for eval_data in eval_results.values():
        if not isinstance(eval_data, dict):
            continue
        for r in eval_data.get("rubrics", []):
            c = r.get("criterion", "")
            key = RUBRIC_NAME_MAP.get(c, c.lower().replace(" ", "_"))
            if key and key not in out:
                out[key] = r.get("score", 0.0)
    return out


async def aggregate_turn_log(state: EvalTurnState) -> Dict[str, Any]:
    """
    4.4: Aggregate Turn Log
    최종 턴 로그 JSON 생성
    """
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.4 턴 로그 집계] 진입 - session_id: {session_id}, turn: {turn}")

    # 평가 결과 수집
    eval_results = {}

    for eval_key in [
        "rule_setting_eval",
        "generation_eval",
        "optimization_eval",
        "debugging_eval",
        "exploration_eval",
        "test_case_eval",
        "hint_query_eval",
        "follow_up_eval",
    ]:
        if state.get(eval_key):
            eval_results[eval_key] = state.get(eval_key)

    # 의도 타입 추출 (가중치 적용을 위해)
    intent_types = state.get("intent_types", [])
    primary_intent = intent_types[0] if intent_types else state.get("intent_type")
    unified_intent = state.get("unified_intent")  # v2.1 5대 통합 의도

    # V2.3: 6대 통합 의도 (SETTING/CREATION/REFINEMENT/DEBUGGING/EXPLORATION/FOLLOW_UP)
    if primary_intent:
        intent_upper = (primary_intent or "").upper().replace("-", "_")
    else:
        intent_upper = "DEBUGGING"  # 기본값

    # Phase 2 첫 지시 여부 (SAVE 직후 턴 → Context 감점 없음)
    is_phase2_first_turn = state.get("is_phase2_first_turn", False)

    # Priority: Tier 1 (New) → Tier 2 (Legacy score) → Tier 3 (Legacy Adapter from rubrics)
    all_scores = []
    for eval_key, eval_data in eval_results.items():
        if not isinstance(eval_data, dict):
            continue
        final = eval_data.get("final_score")
        likert = eval_data.get("likert_score")
        score_val = eval_data.get("score", eval_data.get("average"))
        rubrics = eval_data.get("rubrics", [])

        # Tier 1 (New): likert_score 또는 final_score
        if final is not None:
            try:
                all_scores.append(int(final))
            except (TypeError, ValueError):
                all_scores.append(0)
        elif likert is not None:
            s = likert_to_final(int(likert))
            all_scores.append(s)
            logger.debug(
                f"[4.4 턴 로그 집계] {eval_key} Tier1 Likert {likert} → {s}점 (의도: {intent_upper})"
            )
        # TODO: 모든 프롬프트가 V2.1로 전환된 후 삭제 예정
        elif score_val is not None:
            # Tier 2 (Legacy): score 또는 average
            all_scores.append(float(score_val))
            logger.debug(
                f"[4.4 턴 로그 집계] {eval_key} Tier2 legacy score 사용: {score_val}"
            )
        # TODO: 모든 프롬프트가 V2.1로 전환된 후 삭제 예정
        elif rubrics:
            # Tier 3 (Fallback): rubrics만 있으면 Legacy Adapter
            s = legacy_turn_score_from_rubrics(
                rubrics, intent_upper, context_override_100=is_phase2_first_turn
            )
            all_scores.append(s)
            logger.debug(
                f"[4.4 턴 로그 집계] {eval_key} Tier3 Legacy Adapter(rubrics) → {s}점"
            )
        else:
            all_scores.append(0)

    # 가드레일 위반 시 점수 처리
    is_guardrail_failed = state.get("is_guardrail_failed", False)

    if is_guardrail_failed:
        # 가드레일 위반 시: 평가 점수는 0점 처리
        turn_score = 0
        logger.warning(
            f"[4.4 턴 로그 집계] 가드레일 위반 - session_id: {session_id}, turn: {turn}, 점수: 0점"
        )
    elif state.get("spec_paste_guardrail_applied"):
        turn_score = float(state.get("turn_score") or 30.0)
        logger.info(
            f"[4.4 턴 로그 집계] 스펙만 제시 가드레일 - session_id: {session_id}, "
            f"turn: {turn}, 고정 점수: {turn_score:.2f}"
        )
    else:
        turn_score = sum(all_scores) / len(all_scores) if all_scores else 0

        # Human-Centric 하단 방어선: Clarity·Problem Relevance가 충분히 높으면 최소 85점
        # 0~100 척도: 둘 다 ≥90 / 1~5 척도: 둘 다 ≥4.5
        rubric_scores = _get_rubric_scores_by_criterion(eval_results)
        clarity = rubric_scores.get("clarity")
        problem_relevance = rubric_scores.get("problem_relevance")
        if clarity is not None and problem_relevance is not None:
            is_high_scale = max(clarity, problem_relevance) > 5.0
            threshold = 90.0 if is_high_scale else 4.5
            if clarity >= threshold and problem_relevance >= threshold:
                turn_score = max(turn_score, 85.0)
                logger.info(
                    f"[4.4 턴 로그 집계] Clarity·Problem Relevance ≥{threshold} → 하단 방어선 적용, 턴 점수: {turn_score:.2f}"
                )

        logger.info(
            f"[4.4 턴 로그 집계] 집계 완료 - 의도: {intent_upper}, 최종 점수: {turn_score:.2f}"
        )

    # 턴 로그 생성
    # intent_type은 호환성을 위해 첫 번째 의도 사용하거나, intent_types 리스트 사용
    # (이미 위에서 추출했으므로 재사용)

    # 평가 결과에서 rubrics와 final_reasoning 추출 (상세 피드백)
    detailed_feedback = []
    comprehensive_reasoning_parts = []

    for eval_key, eval_data in eval_results.items():
        if isinstance(eval_data, dict):
            eval_rubrics = eval_data.get("rubrics", [])
            final_reasoning = eval_data.get("final_reasoning", "")

            if eval_rubrics or final_reasoning:
                detailed_feedback.append(
                    {
                        "intent": eval_key,
                        "rubrics": (
                            eval_rubrics if isinstance(eval_rubrics, list) else []
                        ),
                        "final_reasoning": final_reasoning,
                    }
                )

                if final_reasoning:
                    comprehensive_reasoning_parts.append(
                        f"[{eval_key}]: {final_reasoning}"
                    )

    # 전체 턴에 대한 종합 평가 근거
    comprehensive_reasoning = (
        "\n\n".join(comprehensive_reasoning_parts)
        if comprehensive_reasoning_parts
        else "평가 완료"
    )

    turn_log = {
        "session_id": state.get("session_id"),
        "turn": state.get("turn"),
        "intent_type": primary_intent,  # 대표 의도 (호환성)
        "intent_types": intent_types,  # 전체 의도 리스트
        "unified_intent": unified_intent,  # v2.3 6대 통합 의도
        "intent_confidence": state.get("intent_confidence"),
        "intent_cot": state.get("intent_cot"),
        "problem_in_turn": state.get("problem_in_turn"),
        "user_request_in_turn": state.get("user_request_in_turn"),
        "request_one_liner": state.get("request_one_liner"),
        "carry_forward": state.get("carry_forward"),
        "spec_paste_guardrail_applied": state.get("spec_paste_guardrail_applied"),
        "is_guardrail_failed": is_guardrail_failed,
        "guardrail_message": state.get("guardrail_message"),
        "evaluations": eval_results,  # 전체 평가 결과 (상세 정보 포함)
        "detailed_feedback": detailed_feedback,  # 상세 피드백 (rubrics와 final_reasoning)
        "comprehensive_reasoning": comprehensive_reasoning,  # 전체 평가 근거
        "answer_summary": state.get("answer_summary"),
        "turn_score": round(turn_score, 2),  # 이미 0-100 스케일
        "timestamp": datetime.utcnow().isoformat(),
    }

    logger.info(
        f"[4.4 턴 로그 집계] 완료 - session_id: {session_id}, turn: {turn}, 턴 점수: {turn_score:.2f}, 평가 개수: {len(eval_results)}"
    )

    return {
        "turn_log": turn_log,
        "turn_score": round(turn_score, 2),  # 이미 0-100 스케일
    }
