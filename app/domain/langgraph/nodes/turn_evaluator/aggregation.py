import logging
from typing import Dict, Any
from datetime import datetime

from app.domain.langgraph.states import EvalTurnState
from app.domain.langgraph.nodes.turn_evaluator.weights import calculate_weighted_score

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
    
    # 의도 타입 추출 (가중치 적용을 위해)
    intent_types = state.get("intent_types", [])
    primary_intent = intent_types[0] if intent_types else state.get("intent_type")
    
    # 의도 타입을 대문자로 변환 (weights.py의 INTENT_WEIGHTS 키 형식에 맞춤)
    if primary_intent:
        # "follow_up" -> "FOLLOW_UP", "rule_setting" -> "RULE_SETTING" 등
        intent_upper = primary_intent.upper()
    else:
        intent_upper = "HINT_OR_QUERY"  # 기본값
    
    # 가중치를 적용한 점수 계산
    all_scores = []
    for eval_key, eval_data in eval_results.items():
        if isinstance(eval_data, dict):
            rubrics = eval_data.get("rubrics", [])
            
            # 루브릭이 있으면 가중치를 적용하여 점수 계산
            if rubrics:
                # Rubric 모델이 dict로 변환된 형태: {"criterion": str, "score": float, "reasoning": str}
                weighted_score = calculate_weighted_score(rubrics, intent_upper)
                all_scores.append(weighted_score)
                logger.debug(f"[4.4 턴 로그 집계] {eval_key} 가중치 적용 점수: {weighted_score:.2f} (의도: {intent_upper})")
            else:
                # 루브릭이 없으면 기존 score 사용 (fallback)
                score = eval_data.get("score", eval_data.get("average", 0))
                all_scores.append(score)
                logger.warning(f"[4.4 턴 로그 집계] {eval_key} 루브릭 없음 - 기존 score 사용: {score:.2f}")
    
    # 가드레일 위반 시 점수 처리
    is_guardrail_failed = state.get("is_guardrail_failed", False)
    
    if is_guardrail_failed:
        # 가드레일 위반 시: 평가 점수는 0점 처리
        turn_score = 0
        logger.warning(f"[4.4 턴 로그 집계] 가드레일 위반 - session_id: {session_id}, turn: {turn}, 점수: 0점")
    else:
        # 가중치 적용 점수의 평균 계산
        turn_score = sum(all_scores) / len(all_scores) if all_scores else 0
        logger.info(f"[4.4 턴 로그 집계] 가중치 적용 완료 - 의도: {intent_upper}, 최종 점수: {turn_score:.2f}")
    
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

