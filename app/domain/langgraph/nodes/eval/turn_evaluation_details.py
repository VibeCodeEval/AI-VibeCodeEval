"""
prompt_evaluations(TURN_EVAL).details 와 동일한 구조를 turn_log에서 조립.

EvaluationStorageService · N9 rubric_json.turn_evaluations 가 공유한다.
"""

from __future__ import annotations

from typing import Any, Dict, List


def build_turn_evaluation_details(turn_log: Dict[str, Any]) -> Dict[str, Any]:
    """turn_log(Redis/N4) → prompt_evaluations.details 스키마."""
    prompt_eval_details = turn_log.get("prompt_evaluation_details", {})
    score = prompt_eval_details.get("score")
    is_guardrail_failed = bool(turn_log.get("is_guardrail_failed", False))
    if is_guardrail_failed:
        score = 0.0
    analysis = turn_log.get("comprehensive_reasoning") or prompt_eval_details.get(
        "final_reasoning"
    )

    rubrics = prompt_eval_details.get("rubrics", [])
    detailed_rubrics: List[Dict[str, Any]] = []
    for rubric in rubrics:
        if isinstance(rubric, dict):
            detailed_rubrics.append(
                {
                    "name": rubric.get("name", rubric.get("criterion", "")),
                    "score": rubric.get("score", 0.0),
                    "reasoning": rubric.get(
                        "reasoning", rubric.get("reason", "평가 없음")
                    ),
                    "criterion": rubric.get("criterion", rubric.get("name", "")),
                }
            )

    intent = prompt_eval_details.get("intent", "UNKNOWN")
    intent_types = turn_log.get("intent_types", [])
    if intent == "UNKNOWN" and intent_types:
        intent = intent_types[0]

    ai_summary = (
        turn_log.get("llm_answer_summary")
        or turn_log.get("answer_summary")
        or ""
    )

    rubric_breakdown = prompt_eval_details.get("rubric_breakdown")
    applied_rubrics = prompt_eval_details.get("applied_rubrics")
    scoring_cot = prompt_eval_details.get("scoring_cot")
    intent_cot = prompt_eval_details.get("intent_cot")
    problem_in_turn = prompt_eval_details.get("problem_in_turn")
    user_request_in_turn = prompt_eval_details.get("user_request_in_turn")
    request_one_liner = prompt_eval_details.get("request_one_liner")
    carry_forward = prompt_eval_details.get("carry_forward")

    if not detailed_rubrics and isinstance(applied_rubrics, list):
        for rubric in applied_rubrics:
            if isinstance(rubric, dict):
                detailed_rubrics.append(
                    {
                        "name": rubric.get("name", rubric.get("criterion", "")),
                        "score": rubric.get("score", 0.0),
                        "reasoning": rubric.get(
                            "reasoning", rubric.get("reason", "평가 없음")
                        ),
                        "criterion": rubric.get("criterion", rubric.get("name", "")),
                    }
                )

    return {
        "score": score,
        "analysis": analysis,
        "intent": intent,
        "intent_types": intent_types,
        "unified_intent": turn_log.get("unified_intent")
        or prompt_eval_details.get("unified_intent"),
        "intent_confidence": turn_log.get(
            "intent_confidence",
            prompt_eval_details.get("intent_confidence", 0.0),
        ),
        "rubrics": detailed_rubrics,
        "rubric_breakdown": rubric_breakdown,
        "applied_rubrics": applied_rubrics,
        "scoring_cot": scoring_cot,
        "intent_cot": intent_cot,
        "problem_in_turn": problem_in_turn,
        "user_request_in_turn": user_request_in_turn,
        "request_one_liner": request_one_liner or turn_log.get("request_one_liner"),
        "carry_forward": carry_forward,
        "spec_paste_guardrail_applied": turn_log.get("spec_paste_guardrail_applied")
        or prompt_eval_details.get("spec_paste_guardrail_applied"),
        "weights": prompt_eval_details.get("weights", {}),
        "turn_score": 0.0 if is_guardrail_failed else turn_log.get("turn_score"),
        "is_guardrail_failed": is_guardrail_failed,
        "guardrail_message": turn_log.get("guardrail_message"),
        "ai_summary": ai_summary,
        "user_prompt_summary": turn_log.get("user_prompt_summary"),
        "llm_answer_summary": turn_log.get("llm_answer_summary"),
        "llm_answer_reasoning": turn_log.get("llm_answer_reasoning"),
    }
