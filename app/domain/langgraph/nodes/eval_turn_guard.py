"""
노드 4: Eval Turn Guard (제출 시)
제출 시 모든 턴의 평가가 완료되었는지 확인하고, 누락된 턴을 재평가
"""
import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

from app.domain.langgraph.states import MainGraphState
from app.infrastructure.cache.redis_client import redis_client

logger = logging.getLogger(__name__)


async def eval_turn_submit_guard(state: MainGraphState) -> Dict[str, Any]:
    """
    제출 시 4번 가드 노드
    
    역할:
    1. State의 messages에서 모든 턴 추출 (1 ~ current_turn-1)
    2. 각 턴에 대해 Eval Turn SubGraph를 동기적으로 실행
    3. 모든 턴 평가 완료 후 turn_scores 반환
    4. 다음 노드(평가 플로우)로 진행
    
    ⚠️ 중요: 일반 채팅에서는 평가를 하지 않으므로, 제출 시 모든 턴을 처음부터 평가합니다.
    """
    session_id = state.get("session_id", "unknown")
    current_turn = state.get("current_turn", 0)
    
    logger.info(f"[4. Eval Turn Guard] 진입 - session_id: {session_id}, 현재 턴: {current_turn}")
    
    try:
        # ★ Submit 시 State의 messages에서 모든 턴을 추출하여 확실하게 평가
        # 일반 채팅에서는 평가를 하지 않으므로, 제출 시 모든 턴을 처음부터 평가
        logger.info(f"[4. Eval Turn Guard] State 기반 모든 턴 평가 시작 - session_id: {session_id}, current_turn: {current_turn}")
        
        # State의 messages에서 모든 턴 추출
        messages = state.get("messages", [])
        logger.info(f"[4. Eval Turn Guard] 전체 messages 개수: {len(messages)}")
        
        # 제출 턴(current_turn)은 평가하지 않으므로, 1 ~ (current_turn - 1)만 평가
        turns_to_evaluate = list(range(1, current_turn))
        logger.info(f"[4. Eval Turn Guard] 평가 대상 턴: {turns_to_evaluate}")
        
        if not turns_to_evaluate:
            logger.info(f"[4. Eval Turn Guard] 평가할 턴이 없음 (첫 제출)")
            return {
                "turn_scores": {},
                "updated_at": datetime.utcnow().isoformat(),
            }
        
        # Redis에서 턴-메시지 매핑 조회
        turn_mapping = await redis_client.get_turn_mapping(session_id)
        logger.info(f"[4. Eval Turn Guard] 턴 매핑 조회 - 존재: {turn_mapping is not None}, 턴 개수: {len(turn_mapping) if turn_mapping else 0}")
        
        # 모든 턴 평가
        for turn in turns_to_evaluate:
            logger.info(f"[4. Eval Turn Guard] 턴 {turn} 평가 시작...")
            
            human_msg = None
            ai_msg = None
            
            # 방법 1: 턴 매핑 사용 (추천)
            if turn_mapping and str(turn) in turn_mapping:
                indices = turn_mapping[str(turn)]
                start_idx = indices.get("start_msg_idx")
                end_idx = indices.get("end_msg_idx")
                
                logger.info(f"[4. Eval Turn Guard] 턴 {turn} 매핑 발견 - indices: [{start_idx}, {end_idx}]")
                
                if start_idx is not None and end_idx is not None:
                    if start_idx < len(messages) and end_idx < len(messages):
                        user_msg_obj = messages[start_idx]
                        ai_msg_obj = messages[end_idx]
                        
                        # content 추출 (dict 또는 객체 모두 지원)
                        human_msg = user_msg_obj.get("content") if isinstance(user_msg_obj, dict) else getattr(user_msg_obj, "content", None)
                        ai_msg = ai_msg_obj.get("content") if isinstance(ai_msg_obj, dict) else getattr(ai_msg_obj, "content", None)
                        
                        logger.info(f"[4. Eval Turn Guard] 턴 {turn} 메시지 추출 성공 (매핑 사용)")
                    else:
                        logger.warning(f"[4. Eval Turn Guard] 턴 {turn} 인덱스 범위 초과 - start: {start_idx}, end: {end_idx}, total: {len(messages)}")
                else:
                    logger.warning(f"[4. Eval Turn Guard] 턴 {turn} 매핑 인덱스 누락")
            
            # 방법 2: turn 키로 직접 검색 (fallback)
            if not human_msg or not ai_msg:
                logger.info(f"[4. Eval Turn Guard] 턴 {turn} - turn 키로 직접 검색 시도")
                turn_messages = [
                    msg for msg in messages 
                    if isinstance(msg, dict) and msg.get("turn") == turn
                ]
                
                if len(turn_messages) >= 2:
                    for msg in turn_messages:
                        if msg.get("role") == "user":
                            human_msg = msg.get("content")
                        elif msg.get("role") == "assistant":
                            ai_msg = msg.get("content")
                    
                    if human_msg and ai_msg:
                        logger.info(f"[4. Eval Turn Guard] 턴 {turn} 메시지 추출 성공 (turn 키 사용)")
                else:
                    logger.warning(f"[4. Eval Turn Guard] 턴 {turn} - turn 키로 발견된 메시지: {len(turn_messages)}개")
            
            # 평가 실행
            if human_msg and ai_msg:
                logger.info(f"[4. Eval Turn Guard] 턴 {turn} 동기 평가 실행")
                
                await _evaluate_turn_sync(
                    session_id=session_id,
                    turn=turn,
                    human_message=human_msg,
                    ai_message=ai_msg,
                    problem_context=state.get("problem_context")
                )
                
                logger.info(f"[4. Eval Turn Guard] 턴 {turn} 평가 완료 ✓")
            else:
                logger.error(f"[4. Eval Turn Guard] 턴 {turn} 메시지 추출 실패 - human: {bool(human_msg)}, ai: {bool(ai_msg)}")
                logger.error(f"[4. Eval Turn Guard] 턴 {turn} - 평가 불가능 ✗")
        
        logger.info(f"[4. Eval Turn Guard] 모든 턴 평가 완료 - session_id: {session_id}, 평가 완료: {len(turns_to_evaluate)}턴")
        
        # Redis에서 최신 turn_logs 조회 (평가 결과 반영)
        updated_turn_logs = await redis_client.get_all_turn_logs(session_id)
        
        # turn_logs를 turn_scores로 변환하여 state 업데이트
        # 6b 노드에서 {"turn_score": ...} 형식을 기대하므로 딕셔너리로 저장
        turn_scores = {}
        for turn_key, turn_log in updated_turn_logs.items():
            if isinstance(turn_log, dict) and "prompt_evaluation_details" in turn_log:
                score = turn_log["prompt_evaluation_details"].get("score", 0)
                turn_scores[turn_key] = {
                    "turn_score": score  # 6b 노드가 기대하는 형식으로 변경
                }
        
        logger.info(f"[4. Eval Turn Guard] 완료 - session_id: {session_id}, 최종 턴 로그 개수: {len(updated_turn_logs)}, turn_scores: {turn_scores}")
        
        return {
            "turn_scores": turn_scores,
            "updated_at": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"[4. Eval Turn Guard] 오류 - session_id: {session_id}, error: {str(e)}", exc_info=True)
        return {
            "error_message": f"턴 평가 가드 오류: {str(e)}",
            "updated_at": datetime.utcnow().isoformat(),
        }


async def _evaluate_turn_sync(
    session_id: str,
    turn: int,
    human_message: str,
    ai_message: str,
    problem_context: Optional[Dict[str, Any]] = None
) -> None:
    """
    특정 턴을 동기적으로 평가
    
    제출 시 모든 턴을 평가하기 위해 사용
    """
    try:
        from app.domain.langgraph.subgraph_eval_turn import create_eval_turn_subgraph
        from app.domain.langgraph.states import EvalTurnState
        
        # Eval Turn SubGraph 생성
        eval_turn_subgraph = create_eval_turn_subgraph()
        
        # SubGraph 입력 준비
        turn_state: EvalTurnState = {
            "session_id": session_id,
            "turn": turn,
            "human_message": human_message,
            "ai_message": ai_message,
            "problem_context": problem_context,  # 문제 정보 전달
            "is_guardrail_failed": False,
            "guardrail_message": None,
            "intent_type": None,
            "intent_confidence": 0.0,
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
        }
        
        # SubGraph 실행 (동기)
        result = await eval_turn_subgraph.ainvoke(turn_state)
        
        intent_type = result.get("intent_type", "UNKNOWN")
        turn_score = result.get("turn_score", 0)
        
        # 개별 평가 결과에서 rubrics 생성
        eval_mapping = {
            "rule_setting_eval": "규칙 설정 (Rules)",
            "generation_eval": "코드 생성 (Generation)",
            "optimization_eval": "최적화 (Optimization)",
            "debugging_eval": "디버깅 (Debugging)",
            "test_case_eval": "테스트 케이스 (Test Case)",
            "hint_query_eval": "힌트/질의 (Hint/Query)",
            "follow_up_eval": "후속 응답 (Follow-up)"
        }
        
        rubrics = []
        for eval_key, criterion_name in eval_mapping.items():
            eval_result = result.get(eval_key)
            if eval_result and isinstance(eval_result, dict):
                rubrics.append({
                    "criterion": criterion_name,
                    "score": eval_result.get("average", 0),
                    "reason": eval_result.get("feedback", "평가 없음")
                })
        
        # 상세 turn_log 구조 생성
        detailed_turn_log = {
            "turn_number": turn,
            "user_prompt_summary": human_message[:200] + "..." if len(human_message) > 200 else human_message,
            "prompt_evaluation_details": {
                "intent": intent_type,
                "score": turn_score,
                "rubrics": rubrics,
                "final_reasoning": result.get("answer_summary", "재평가 완료")
            },
            "llm_answer_summary": result.get("answer_summary", ""),
            "llm_answer_reasoning": rubrics[0].get("reason", "") if rubrics else "평가 없음",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Redis에 상세 turn_log 저장
        await redis_client.save_turn_log(session_id, turn, detailed_turn_log)
        
        # PostgreSQL에 평가 결과 저장
        try:
            from app.infrastructure.persistence.session import get_db_context
            from app.application.services.evaluation_storage_service import EvaluationStorageService
            
            # session_id를 PostgreSQL id로 변환 (Redis session_id: "session_123" -> PostgreSQL id: 123)
            postgres_session_id = int(session_id.replace("session_", "")) if session_id.startswith("session_") else None
            
            if postgres_session_id:
                async with get_db_context() as db:
                    storage_service = EvaluationStorageService(db)
                    
                    # turn_log를 aggregate_turn_log 형식으로 변환
                    turn_log_for_storage = {
                        "prompt_evaluation_details": detailed_turn_log.get("prompt_evaluation_details", {}),
                        "comprehensive_reasoning": detailed_turn_log.get("llm_answer_reasoning", ""),
                        "intent_types": [intent_type],
                        "evaluations": {},
                        "detailed_feedback": [],
                        "turn_score": turn_score,
                        "is_guardrail_failed": False,
                        "guardrail_message": None,
                    }
                    
                    await storage_service.save_turn_evaluation(
                        session_id=postgres_session_id,
                        turn=turn,
                        turn_log=turn_log_for_storage
                    )
                    await db.commit()
                    logger.info(
                        f"[Eval Turn Sync] PostgreSQL 턴 평가 저장 완료 - "
                        f"session_id: {postgres_session_id}, turn: {turn}"
                    )
        except Exception as pg_error:
            # PostgreSQL 저장 실패해도 Redis는 저장되었으므로 경고만
            logger.warning(
                f"[Eval Turn Sync] PostgreSQL 턴 평가 저장 실패 (Redis는 저장됨) - "
                f"session_id: {session_id}, turn: {turn}, error: {str(pg_error)}"
            )
        
        logger.info(f"[Eval Turn Sync] 턴 {turn} 평가 저장 완료 - session_id: {session_id}, score: {turn_score}")
        
    except Exception as e:
        logger.error(f"[Eval Turn Sync] 턴 {turn} 평가 실패 - session_id: {session_id}, error: {str(e)}", exc_info=True)



