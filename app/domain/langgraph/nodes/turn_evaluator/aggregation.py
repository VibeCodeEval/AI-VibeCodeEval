import logging
from typing import Dict, Any
from datetime import datetime

from app.domain.langgraph.states import EvalTurnState

logger = logging.getLogger(__name__)

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
        "rule_setting_eval", "generation_eval", "optimization_eval",
        "debugging_eval", "test_case_eval", "hint_query_eval", "follow_up_eval"
    ]:
        if state.get(eval_key):
            eval_results[eval_key] = state.get(eval_key)
    
    # 평균 점수 계산 (이미 0-100 스케일)
    all_scores = []
    for eval_data in eval_results.values():
        if isinstance(eval_data, dict):
            # TurnEvaluation 모델의 score는 이미 0-100 스케일
            score = eval_data.get("score", eval_data.get("average", 0))
            all_scores.append(score)
    
    # 가드레일 위반 시 점수 처리
    is_guardrail_failed = state.get("is_guardrail_failed", False)
    
    if is_guardrail_failed:
        # 가드레일 위반 시: 평가 점수는 0점 처리
        turn_score = 0
        logger.warning(f"[4.4 턴 로그 집계] 가드레일 위반 - session_id: {session_id}, turn: {turn}, 점수: 0점")
    else:
        # 이미 0-100 스케일이므로 * 10 하지 않음
        turn_score = sum(all_scores) / len(all_scores) if all_scores else 0
    
    # 턴 로그 생성
    # intent_type은 호환성을 위해 첫 번째 의도 사용하거나, intent_types 리스트 사용
    intent_types = state.get("intent_types", [])
    primary_intent = intent_types[0] if intent_types else state.get("intent_type")

    # 평가 결과에서 rubrics와 final_reasoning 추출 (상세 피드백)
    detailed_feedback = []
    comprehensive_reasoning_parts = []
    
    for eval_key, eval_data in eval_results.items():
        if isinstance(eval_data, dict):
            eval_rubrics = eval_data.get("rubrics", [])
            final_reasoning = eval_data.get("final_reasoning", "")
            
            if eval_rubrics or final_reasoning:
                detailed_feedback.append({
                    "intent": eval_key,
                    "rubrics": eval_rubrics if isinstance(eval_rubrics, list) else [],
                    "final_reasoning": final_reasoning
                })
                
                if final_reasoning:
                    comprehensive_reasoning_parts.append(f"[{eval_key}]: {final_reasoning}")
    
    # 전체 턴에 대한 종합 평가 근거
    comprehensive_reasoning = "\n\n".join(comprehensive_reasoning_parts) if comprehensive_reasoning_parts else "평가 완료"
    
    turn_log = {
        "session_id": state.get("session_id"),
        "turn": state.get("turn"),
        "intent_type": primary_intent,  # 대표 의도 (호환성)
        "intent_types": intent_types,   # 전체 의도 리스트
        "intent_confidence": state.get("intent_confidence"),
        "is_guardrail_failed": is_guardrail_failed,
        "guardrail_message": state.get("guardrail_message"),
        "evaluations": eval_results,  # 전체 평가 결과 (상세 정보 포함)
        "detailed_feedback": detailed_feedback,  # 상세 피드백 (rubrics와 final_reasoning)
        "comprehensive_reasoning": comprehensive_reasoning,  # 전체 평가 근거
        "answer_summary": state.get("answer_summary"),
        "turn_score": round(turn_score, 2),  # 이미 0-100 스케일
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    logger.info(f"[4.4 턴 로그 집계] 완료 - session_id: {session_id}, turn: {turn}, 턴 점수: {turn_score:.2f}, 평가 개수: {len(eval_results)}")
    
    return {
        "turn_log": turn_log,
        "turn_score": round(turn_score, 2),  # 이미 0-100 스케일
    }

