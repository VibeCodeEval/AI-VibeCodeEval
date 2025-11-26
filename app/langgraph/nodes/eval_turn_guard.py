"""
노드 4: Eval Turn Guard (제출 시)
제출 시 모든 턴의 평가가 완료되었는지 확인하고, 누락된 턴을 재평가
"""
import logging
import asyncio
from typing import Dict, Any
from datetime import datetime

from app.langgraph.states import MainGraphState
from app.db.redis_client import redis_client

logger = logging.getLogger(__name__)


async def eval_turn_submit_guard(state: MainGraphState) -> Dict[str, Any]:
    """
    제출 시 4번 가드 노드
    
    역할:
    1. Redis에서 현재 저장된 turn_logs 조회
    2. 현재 턴 번호와 비교하여 누락된 턴 확인
    3. 누락된 턴이 있으면 messages 배열에서 복원하여 재평가 (동기)
    4. 모든 턴 평가가 완료되면 다음 노드로 진행
    """
    session_id = state.get("session_id", "unknown")
    current_turn = state.get("current_turn", 0)
    
    logger.info(f"[4. Eval Turn Guard] 진입 - session_id: {session_id}, 현재 턴: {current_turn}")
    
    try:
        # ★ 백그라운드 평가 완료 대기 (최대 10초)
        logger.info(f"[4. Eval Turn Guard] 백그라운드 평가 완료 대기 시작 - session_id: {session_id}")
        
        max_wait_seconds = 10
        wait_interval = 0.5
        total_waited = 0
        
        while total_waited < max_wait_seconds:
            all_turn_logs = await redis_client.get_all_turn_logs(session_id)
            
            # 모든 턴(1 ~ current_turn 포함)이 평가되었는지 확인
            # 제출 API는 턴 증가 없이 호출되므로 current_turn까지 포함
            expected_turns = set(str(t) for t in range(1, current_turn + 1))
            existing_turns = set(all_turn_logs.keys())
            
            if expected_turns.issubset(existing_turns):
                logger.info(f"[4. Eval Turn Guard] 모든 백그라운드 평가 완료 - 대기 시간: {total_waited:.1f}초")
                break
            
            # 아직 누락된 턴이 있으면 대기
            missing_now = expected_turns - existing_turns
            logger.debug(f"[4. Eval Turn Guard] 백그라운드 평가 대기 중 - 누락: {missing_now}, 대기: {total_waited:.1f}초")
            
            await asyncio.sleep(wait_interval)
            total_waited += wait_interval
        
        if total_waited >= max_wait_seconds:
            logger.warning(f"[4. Eval Turn Guard] 백그라운드 평가 대기 타임아웃 - {max_wait_seconds}초 초과")
        
        # 최종 turn_logs 조회
        all_turn_logs = await redis_client.get_all_turn_logs(session_id)
        
        logger.info(f"[4. Eval Turn Guard] Redis 턴 로그 개수: {len(all_turn_logs)}")
        
        # 누락된 턴 찾기 (현재 턴 포함)
        # 제출 API는 별도 호출이므로 current_turn까지 모두 평가 대상
        missing_turns = []
        for turn in range(1, current_turn + 1):  # current_turn 포함
            if str(turn) not in all_turn_logs:
                missing_turns.append(turn)
        
        if missing_turns:
            logger.warning(f"[4. Eval Turn Guard] 누락된 턴 발견 - session_id: {session_id}, 누락: {missing_turns}")
            
            # Redis에서 턴-메시지 매핑 조회
            turn_mapping = await redis_client.get_turn_mapping(session_id)
            logger.info(f"[4. Eval Turn Guard] 턴 매핑 조회 - 존재: {turn_mapping is not None}, 턴 개수: {len(turn_mapping) if turn_mapping else 0}")
            
            # messages 배열에서 누락된 턴 복원
            messages = state.get("messages", [])
            logger.info(f"[4. Eval Turn Guard] 전체 messages 개수: {len(messages)}")
            
            # 메시지 타입 샘플 확인 (디버깅용)
            if messages:
                sample_msg = messages[0]
                logger.info(f"[4. Eval Turn Guard] 첫 메시지 샘플 - 타입: {type(sample_msg)}, 키: {list(sample_msg.keys()) if isinstance(sample_msg, dict) else 'N/A'}")
            
            for missing_turn in missing_turns:
                logger.info(f"[4. Eval Turn Guard] 턴 {missing_turn} 재평가 시작...")
                
                human_msg = None
                ai_msg = None
                
                # 방법 1: 턴 매핑 사용 (추천)
                if turn_mapping and str(missing_turn) in turn_mapping:
                    indices = turn_mapping[str(missing_turn)]
                    start_idx = indices.get("start_msg_idx")
                    end_idx = indices.get("end_msg_idx")
                    
                    logger.info(f"[4. Eval Turn Guard] 턴 {missing_turn} 매핑 발견 - indices: [{start_idx}, {end_idx}]")
                    
                    if start_idx is not None and end_idx is not None:
                        if start_idx < len(messages) and end_idx < len(messages):
                            user_msg_obj = messages[start_idx]
                            ai_msg_obj = messages[end_idx]
                            
                            # content 추출 (dict 또는 객체 모두 지원)
                            human_msg = user_msg_obj.get("content") if isinstance(user_msg_obj, dict) else getattr(user_msg_obj, "content", None)
                            ai_msg = ai_msg_obj.get("content") if isinstance(ai_msg_obj, dict) else getattr(ai_msg_obj, "content", None)
                            
                            logger.info(f"[4. Eval Turn Guard] 턴 {missing_turn} 메시지 추출 성공 (매핑 사용)")
                        else:
                            logger.warning(f"[4. Eval Turn Guard] 턴 {missing_turn} 인덱스 범위 초과 - start: {start_idx}, end: {end_idx}, total: {len(messages)}")
                    else:
                        logger.warning(f"[4. Eval Turn Guard] 턴 {missing_turn} 매핑 인덱스 누락")
                
                # 방법 2: turn 키로 직접 검색 (fallback)
                if not human_msg or not ai_msg:
                    logger.info(f"[4. Eval Turn Guard] 턴 {missing_turn} - turn 키로 직접 검색 시도")
                    turn_messages = [
                        msg for msg in messages 
                        if isinstance(msg, dict) and msg.get("turn") == missing_turn
                    ]
                    
                    if len(turn_messages) >= 2:
                        for msg in turn_messages:
                            if msg.get("role") == "user":
                                human_msg = msg.get("content")
                            elif msg.get("role") == "assistant":
                                ai_msg = msg.get("content")
                        
                        if human_msg and ai_msg:
                            logger.info(f"[4. Eval Turn Guard] 턴 {missing_turn} 메시지 추출 성공 (turn 키 사용)")
                    else:
                        logger.warning(f"[4. Eval Turn Guard] 턴 {missing_turn} - turn 키로 발견된 메시지: {len(turn_messages)}개")
                
                # 재평가 실행
                if human_msg and ai_msg:
                    logger.info(f"[4. Eval Turn Guard] 턴 {missing_turn} 동기 재평가 실행")
                    
                    await _evaluate_turn_sync(
                        session_id=session_id,
                        turn=missing_turn,
                        human_message=human_msg,
                        ai_message=ai_msg
                    )
                    
                    logger.info(f"[4. Eval Turn Guard] 턴 {missing_turn} 재평가 완료 ✓")
                else:
                    logger.error(f"[4. Eval Turn Guard] 턴 {missing_turn} 메시지 추출 실패 - human: {bool(human_msg)}, ai: {bool(ai_msg)}")
                    logger.error(f"[4. Eval Turn Guard] 턴 {missing_turn} - 재평가 불가능 ✗")
        else:
            logger.info(f"[4. Eval Turn Guard] 모든 턴 평가 완료 확인 - session_id: {session_id}, 총 {current_turn}턴")
        
        # Redis에서 최신 turn_logs 재조회 (재평가 결과 반영)
        updated_turn_logs = await redis_client.get_all_turn_logs(session_id)
        
        # turn_logs를 turn_scores로 변환하여 state 업데이트
        turn_scores = {}
        for turn_key, turn_log in updated_turn_logs.items():
            if isinstance(turn_log, dict) and "prompt_evaluation_details" in turn_log:
                turn_scores[turn_key] = turn_log["prompt_evaluation_details"].get("score", 0)
        
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
    ai_message: str
) -> None:
    """
    특정 턴을 동기적으로 재평가
    
    백그라운드 4번과 동일한 로직이지만 동기적으로 실행
    """
    try:
        from app.langgraph.subgraph_eval_turn import create_eval_turn_subgraph
        from app.langgraph.states import EvalTurnState
        
        # Eval Turn SubGraph 생성
        eval_turn_subgraph = create_eval_turn_subgraph()
        
        # SubGraph 입력 준비
        turn_state: EvalTurnState = {
            "session_id": session_id,
            "turn": turn,
            "human_message": human_message,
            "ai_message": ai_message,
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
        
        logger.info(f"[Eval Turn Sync] 턴 {turn} 재평가 저장 완료 - session_id: {session_id}, score: {turn_score}")
        
    except Exception as e:
        logger.error(f"[Eval Turn Sync] 턴 {turn} 재평가 실패 - session_id: {session_id}, error: {str(e)}", exc_info=True)



