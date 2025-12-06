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
    1. Redis에서 현재 저장된 turn_logs 조회
    2. 현재 턴 번호와 비교하여 누락된 턴 확인
    3. 누락된 턴이 있으면 messages 배열에서 복원하여 재평가 (동기)
    4. 모든 턴 평가가 완료되면 다음 노드로 진행
    """
    session_id = state.get("session_id", "unknown")
    current_turn = state.get("current_turn", 0)
    
    logger.info(f"[4. Eval Turn Guard] 진입 - session_id: {session_id}, 현재 턴: {current_turn}")
    
    try:
        # ★ Submit 시 State의 messages에서 모든 턴을 추출하여 확실하게 평가
        # writer.py에서 messages에 turn 정보를 dict 형식으로 추가하므로 State에서 추출 가능
        logger.info(f"[4. Eval Turn Guard] State 기반 턴 평가 시작 - session_id: {session_id}, current_turn: {current_turn}")
        
        # State의 messages에서 모든 턴 추출 (turn과 role로 그룹화)
        messages = state.get("messages", [])
        logger.info(f"[4. Eval Turn Guard] 전체 messages 개수: {len(messages)}")
        
        # Redis turn_mapping을 사용하여 메시지 인덱스 → 턴 번호 매핑 가져오기
        # writer.py에서 save_turn_mapping으로 저장한 정보 사용
        turn_mapping = {}  # {message_index: turn_number}
        try:
            from app.infrastructure.cache.redis_client import redis_client
            # 모든 턴 매핑 조회
            all_mapping = await redis_client.get_turn_mapping(session_id)
            if all_mapping:
                for turn_str, mapping_data in all_mapping.items():
                    try:
                        turn_num = int(turn_str)
                        start_idx = mapping_data.get("start_msg_idx")
                        end_idx = mapping_data.get("end_msg_idx")
                        if start_idx is not None and end_idx is not None:
                            # 메시지 인덱스 범위를 턴 번호에 매핑
                            for idx in range(start_idx, end_idx + 1):
                                turn_mapping[idx] = turn_num
                    except (ValueError, TypeError):
                        continue
                logger.info(f"[4. Eval Turn Guard] turn_mapping 조회 완료 - 매핑 개수: {len(turn_mapping)}")
        except Exception as e:
            logger.warning(f"[4. Eval Turn Guard] turn_mapping 조회 실패 - error: {str(e)}")
        
        # messages에서 turn과 role 정보로 턴별 메시지 추출
        turns_from_state = {}  # {turn: {"user": content, "assistant": content}}
        
        for idx, msg in enumerate(messages):
            turn = None
            role = None
            content = None
            
            # dict 형식 메시지 (writer.py에서 저장한 형식) - 우선 처리
            if isinstance(msg, dict):
                turn = msg.get("turn")
                role = msg.get("role")
                content = msg.get("content")
            # LangChain Message 객체 (HumanMessage, AIMessage 등)
            elif hasattr(msg, "type") and hasattr(msg, "content"):
                # turn_mapping에서 턴 번호 가져오기
                turn = turn_mapping.get(idx)
                
                # role 추출
                msg_type = getattr(msg, "type", "")
                if msg_type == "human":
                    role = "user"
                elif msg_type in ["ai", "assistant"]:
                    role = "assistant"
                else:
                    role = msg_type
                content = getattr(msg, "content", "")
            
            if turn is not None and role and content:
                if turn not in turns_from_state:
                    turns_from_state[turn] = {}
                # role을 소문자로 변환하여 일관성 유지
                role_lower = role.lower()
                if role_lower in ["user", "ai", "assistant"]:
                    # "ai" 또는 "assistant"를 "assistant"로 통일
                    role_key = "assistant" if role_lower in ["ai", "assistant"] else "user"
                    turns_from_state[turn][role_key] = content
        
        logger.info(f"[4. Eval Turn Guard] State에서 추출한 턴 개수: {len(turns_from_state)}, 턴 목록: {sorted(turns_from_state.keys())}")
        
        # 제출 턴(current_turn)은 평가하지 않으므로, 1 ~ (current_turn - 1)만 평가
        # Previous Context 추출: 직전 턴(turn-1)의 AI 답변을 previous_context로 사용
        turns_to_evaluate = []
        for turn in range(1, current_turn):  # 제출 턴 제외
            if turn in turns_from_state:
                turn_data = turns_from_state[turn]
                user_msg = turn_data.get("user")
                assistant_msg = turn_data.get("assistant")
                
                # Previous Context 추출: 직전 턴(turn-1)의 AI 답변
                previous_context = None
                if turn > 1:  # 첫 번째 턴(turn=1)은 previous_context 없음
                    prev_turn_data = turns_from_state.get(turn - 1, {})
                    previous_context = prev_turn_data.get("assistant")  # 직전 턴의 AI 답변
                
                if user_msg and assistant_msg:
                    turns_to_evaluate.append({
                        "turn": turn,
                        "user": user_msg,
                        "assistant": assistant_msg,
                        "previous_context": previous_context  # 직전 턴의 AI 답변 추가
                    })
                    logger.debug(
                        f"[4. Eval Turn Guard] 턴 {turn} 데이터 추출 완료 - "
                        f"previous_context: {bool(previous_context)}"
                    )
                else:
                    logger.warning(
                        f"[4. Eval Turn Guard] 턴 {turn} 메시지 불완전 - "
                        f"user: {bool(user_msg)}, assistant: {bool(assistant_msg)}"
                    )
            else:
                logger.warning(f"[4. Eval Turn Guard] 턴 {turn}이 State messages에 없음")
        
        logger.info(f"[4. Eval Turn Guard] 평가 대상 턴 개수: {len(turns_to_evaluate)}")
        
        # 모든 턴을 확실하게 평가하고 PostgreSQL에 저장
        if turns_to_evaluate:
            logger.info(f"[4. Eval Turn Guard] 모든 턴 평가 및 저장 시작 - session_id: {session_id}, 총 {len(turns_to_evaluate)}개 턴")
            
            # ★ Semaphore 기반 병렬 평가 (최대 5개 동시 실행)
            # LLM API Rate Limit 방지를 위해 동시 실행 수 제한
            sem = asyncio.Semaphore(5)
            
            async def _process_with_semaphore(turn_data: Dict[str, Any]) -> Dict[str, Any]:
                """Semaphore를 적용한 턴 평가 래퍼 함수"""
                async with sem:
                    turn = turn_data["turn"]
                    human_msg = turn_data["user"]
                    ai_msg = turn_data["assistant"]
                    prev_context = turn_data.get("previous_context")
                    
                    logger.info(f"[4. Eval Turn Guard] 턴 {turn} 평가 시작 (Semaphore 적용)")
                    
                    try:
                        result = await _process_single_turn(
                            session_id=session_id,
                            turn=turn,
                            human_message=human_msg,
                            ai_message=ai_msg,
                            previous_context=prev_context,
                            problem_context=state.get("problem_context")
                        )
                        logger.info(f"[4. Eval Turn Guard] 턴 {turn} 평가 완료 - score: {result.get('score', 0)}")
                        return result
                    except Exception as e:
                        logger.error(
                            f"[4. Eval Turn Guard] 턴 {turn} 평가 실패 - "
                            f"session_id: {session_id}, error: {str(e)}",
                            exc_info=True
                        )
                        # 에러 발생 시 기본값 반환
                        return {
                            "turn": turn,
                            "score": 0,
                            "final_reasoning": f"평가 실패: {str(e)}",
                            "rubrics": []
                        }
            
            # 모든 턴을 병렬로 평가 (Semaphore로 동시 실행 수 제한)
            try:
                results = await asyncio.gather(
                    *[_process_with_semaphore(turn_data) for turn_data in turns_to_evaluate],
                    return_exceptions=True
                )
                logger.info(f"[4. Eval Turn Guard] 모든 턴 평가 완료 - session_id: {session_id}, 총 {len(results)}개 결과")
            except Exception as e:
                logger.error(
                    f"[4. Eval Turn Guard] 병렬 평가 실패 - "
                    f"session_id: {session_id}, error: {str(e)}",
                    exc_info=True
                )
                results = []
        else:
            logger.warning(f"[4. Eval Turn Guard] 평가할 턴이 없음 - session_id: {session_id}, current_turn: {current_turn}")
            results = []
        
        # 직접 반환값에서 점수 및 평가 근거 추출 (Redis 재조회 불필요)
        # 6b 노드에서 {"turn_score": ...} 형식을 기대하므로 딕셔너리로 저장
        turn_scores = {}
        turn_evaluations = {}  # 평가 근거 저장 (그래프 내부 사용)
        valid_results = []
        
        for result in results:
            if isinstance(result, dict) and "turn" in result and "score" in result:
                turn = result["turn"]
                score = result["score"]
                turn_scores[f"turn_{turn}"] = {
                    "turn_score": score  # 6b 노드가 기대하는 형식
                }
                # 평가 근거도 저장 (그래프 내부에서 사용 가능)
                turn_evaluations[f"turn_{turn}"] = {
                    "final_reasoning": result.get("final_reasoning", ""),
                    "rubrics": result.get("rubrics", [])
                }
                valid_results.append(result)
            elif isinstance(result, Exception):
                logger.error(
                    f"[4. Eval Turn Guard] 턴 평가 중 예외 발생 - "
                    f"session_id: {session_id}, error: {str(result)}"
                )
        
        logger.info(
            f"[4. Eval Turn Guard] 완료 - session_id: {session_id}, "
            f"평가 완료 턴: {len(valid_results)}, "
            f"turn_scores: {turn_scores}"
        )
        
        return {
            "turn_scores": turn_scores,
            "turn_evaluations": turn_evaluations,  # 평가 근거 포함 (그래프 내부 사용)
            "updated_at": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"[4. Eval Turn Guard] 오류 - session_id: {session_id}, error: {str(e)}", exc_info=True)
        return {
            "error_message": f"턴 평가 가드 오류: {str(e)}",
            "updated_at": datetime.utcnow().isoformat(),
        }


async def _process_single_turn(
    session_id: str,
    turn: int,
    human_message: str,
    ai_message: str,
    previous_context: Optional[str] = None,
    problem_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    프롬프트 품질 평가 (Claude Prompt 기준)
    
    [평가 내용]
    - Intent 분석 (단일 의도 파악)
    - 의도별 전용 평가 함수 호출 (Claude Prompt 기준)
      - SYSTEM_PROMPT -> eval_system_prompt()
      - RULE_SETTING -> eval_rule_setting()
      - GENERATION -> eval_generation()
      - 등등...
    - Chaining 평가는 제외 (6.a에서 수행)
    
    [Claude Prompt 기준]
    - 명확성 (Clarity)
    - 문제 적절성 (Problem Relevance)
    - 예시 (Examples)
    - 규칙 (Rules)
    - 문맥 (Context)
    
    [Previous Context]
    - 직전 턴(turn-1)의 AI 답변을 previous_context로 전달
    - 첫 번째 턴(turn=1)은 previous_context=None
    - 평가 시 문맥(Context) 평가에 활용 가능
    
    [병렬 처리]
    - 여러 Turn을 동시에 평가 가능
    - User/AI 메시지를 한번에 가져가서 평가
    
    Args:
        session_id: 세션 ID
        turn: 턴 번호
        human_message: 사용자 메시지
        ai_message: AI 응답 메시지
        previous_context: 직전 턴의 AI 답변 (선택)
        problem_context: 문제 정보 (선택)
    """
    try:
        from app.domain.langgraph.nodes.turn_evaluator.analysis import intent_analysis
        from app.domain.langgraph.nodes.turn_evaluator.evaluators import _evaluate_turn
        from app.domain.langgraph.states import EvalTurnState
        from app.infrastructure.persistence.session import get_db_context
        from app.application.services.evaluation_storage_service import EvaluationStorageService
        
        logger.info(f"[Prompt Eval] 턴 {turn} 프롬프트 평가 시작 - session_id: {session_id}")
        
        # EvalTurnState 준비
        turn_state: EvalTurnState = {
            "session_id": session_id,
            "turn": turn,
            "human_message": human_message,
            "ai_message": ai_message,
            "problem_context": problem_context,
            "is_guardrail_failed": False,
            "guardrail_message": None,
            "intent_types": None,
            "intent_confidence": 0.0,
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
        
        # 1. Intent 분석 (단일 의도 파악)
        intent_result = await intent_analysis(turn_state)
        intent_type = intent_result.get("intent_types", ["UNKNOWN"])[0] if intent_result.get("intent_types") else "UNKNOWN"
        turn_state["intent_types"] = intent_result.get("intent_types", [intent_type])
        
        # 2. 의도별 전용 평가 함수 호출 (Claude Prompt 기준)
        # 각 의도에 맞는 전용 평가 함수를 호출하여 Claude Prompt 기준 점수 계산
        from app.domain.langgraph.nodes.turn_evaluator.evaluators import (
            eval_system_prompt,
            eval_rule_setting,
            eval_generation,
            eval_optimization,
            eval_debugging,
            eval_test_case,
            eval_hint_query,
            eval_follow_up,
        )
        from app.infrastructure.persistence.models.enums import CodeIntentType
        
        # 의도별 평가 함수 매핑
        intent_eval_map = {
            CodeIntentType.SYSTEM_PROMPT.value: eval_system_prompt,
            CodeIntentType.RULE_SETTING.value: eval_rule_setting,
            CodeIntentType.GENERATION.value: eval_generation,
            CodeIntentType.OPTIMIZATION.value: eval_optimization,
            CodeIntentType.DEBUGGING.value: eval_debugging,
            CodeIntentType.TEST_CASE.value: eval_test_case,
            CodeIntentType.HINT_OR_QUERY.value: eval_hint_query,
            CodeIntentType.FOLLOW_UP.value: eval_follow_up,
        }
        
        # 해당 의도의 평가 함수 호출
        eval_func = intent_eval_map.get(intent_type, eval_hint_query)  # 기본값: hint_query
        eval_state_result = await eval_func(turn_state)
        
        # 평가 결과 추출 (의도별로 필드명이 다름)
        eval_result = None
        if CodeIntentType.SYSTEM_PROMPT.value == intent_type:
            eval_result = eval_state_result.get("system_prompt_eval", {})
        elif CodeIntentType.RULE_SETTING.value == intent_type:
            eval_result = eval_state_result.get("rule_setting_eval", {})
        elif CodeIntentType.GENERATION.value == intent_type:
            eval_result = eval_state_result.get("generation_eval", {})
        elif CodeIntentType.OPTIMIZATION.value == intent_type:
            eval_result = eval_state_result.get("optimization_eval", {})
        elif CodeIntentType.DEBUGGING.value == intent_type:
            eval_result = eval_state_result.get("debugging_eval", {})
        elif CodeIntentType.TEST_CASE.value == intent_type:
            eval_result = eval_state_result.get("test_case_eval", {})
        elif CodeIntentType.HINT_OR_QUERY.value == intent_type:
            eval_result = eval_state_result.get("hint_query_eval", {})
        elif CodeIntentType.FOLLOW_UP.value == intent_type:
            eval_result = eval_state_result.get("follow_up_eval", {})
        
        # 3. 점수 계산 (Claude Prompt 기준 점수)
        turn_score = eval_result.get("score", 0) if isinstance(eval_result, dict) else 0
        
        # 4. turn_log 구조 생성 (Claude Prompt 기준 평가 결과 포함)
        detailed_turn_log = {
            "turn_number": turn,
            "user_prompt_summary": human_message[:200] + "..." if len(human_message) > 200 else human_message,
            "prompt_evaluation_details": {
                "intent": intent_type,
                "score": turn_score,
                "rubrics": eval_result.get("rubrics", []) if isinstance(eval_result, dict) else [{
                    "criterion": f"{intent_type} 프롬프트 품질",
                    "score": turn_score,
                    "reason": "평가 완료"
                }],
                "final_reasoning": eval_result.get("final_reasoning", "프롬프트 평가 완료") if isinstance(eval_result, dict) else "프롬프트 평가 완료"
            },
            "llm_answer_summary": ai_message[:200] + "..." if len(ai_message) > 200 else ai_message,
            "llm_answer_reasoning": eval_result.get("final_reasoning", "") if isinstance(eval_result, dict) else "",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # 5. Redis에 저장
        await redis_client.save_turn_log(session_id, turn, detailed_turn_log)
        
        # 6. PostgreSQL에 저장
        postgres_session_id = int(session_id.replace("session_", "")) if session_id.startswith("session_") else None
        
        if postgres_session_id:
            try:
                async with get_db_context() as db:
                    storage_service = EvaluationStorageService(db)
                    
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
                        f"[Prompt Eval] PostgreSQL 저장 완료 - "
                        f"session_id: {postgres_session_id}, turn: {turn}, score: {turn_score}"
                    )
            except Exception as pg_error:
                logger.warning(
                    f"[Prompt Eval] PostgreSQL 저장 실패 (Redis는 저장됨) - "
                    f"session_id: {session_id}, turn: {turn}, error: {str(pg_error)}"
                )
        
        logger.info(f"[Prompt Eval] 턴 {turn} 평가 완료 - session_id: {session_id}, score: {turn_score}")
        
        # 반환값: 점수 및 평가 근거 포함 (그래프 내부 사용)
        return {
            "turn": turn,
            "score": turn_score,
            "final_reasoning": eval_result.get("final_reasoning", "") if isinstance(eval_result, dict) else "",
            "rubrics": eval_result.get("rubrics", []) if isinstance(eval_result, dict) else []
        }
        
    except Exception as e:
        logger.error(
            f"[Prompt Eval] 턴 {turn} 평가 실패 - session_id: {session_id}, error: {str(e)}",
            exc_info=True
        )
        # 에러 발생 시 기본값 반환
        return {
            "turn": turn,
            "score": 0,
            "final_reasoning": f"평가 실패: {str(e)}",
            "rubrics": []
        }



