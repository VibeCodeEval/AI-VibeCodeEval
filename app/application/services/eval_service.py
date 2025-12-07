"""
평가 서비스 (Evaluation Service)

[목적]
- LangGraph 메인 플로우의 실행을 관리하는 핵심 서비스
- Redis를 통한 상태 관리
- 제출 시 모든 턴 평가 실행

[주요 역할]
1. process_message(): 일반 채팅 메시지 처리
   - LangGraph 메인 플로우 실행
   - Redis 상태 로드/저장
   - 평가 실행하지 않음 (응답만 반환)
   
2. submit_code(): 코드 제출 및 최종 평가
   - is_submission=True로 설정
   - Eval Turn Guard에서 모든 턴 평가
   - 전체 평가 플로우 실행
   - 최종 점수 산출

[아키텍처]
API 요청 → EvalService → LangGraph → Redis
                     ↓ (제출 시)
            Eval Turn Guard → Eval Turn SubGraph (동기 실행)
"""
from typing import Optional, Dict, Any, AsyncIterator
from datetime import datetime
import logging

from langgraph.checkpoint.memory import MemorySaver

from app.domain.langgraph.graph import create_main_graph, get_initial_state
from app.domain.langgraph.states import MainGraphState
from app.domain.langgraph.utils.token_tracking import get_token_summary
from app.infrastructure.cache.redis_client import RedisClient
from app.infrastructure.repositories.state_repository import StateRepository
from app.infrastructure.repositories.session_repository import SessionRepository
from app.infrastructure.persistence.session import get_db_context
from app.core.config import settings


logger = logging.getLogger(__name__)


class EvalService:
    """
    AI 평가 서비스
    
    [구성 요소]
    - redis: Redis 클라이언트 (세션 상태 관리)
    - state_repo: 상태 저장소 (Redis 래퍼)
    - checkpointer: LangGraph 체크포인트 (메모리 기반)
    - graph: LangGraph 메인 플로우
    
    [생명주기]
    1. __init__(): 초기화
       - Redis 클라이언트 주입
       - LangGraph 컴파일
    2. process_message() / submit_code(): 요청 처리
       - 일반 채팅: 평가 없이 응답만 반환
       - 제출: Eval Turn Guard에서 모든 턴 평가 후 최종 평가 진행
    """
    
    def __init__(self, redis: RedisClient):
        """
        EvalService 초기화
        
        Args:
            redis: Redis 클라이언트 인스턴스
        """
        self.redis = redis
        self.state_repo = StateRepository(redis)
        self.checkpointer = MemorySaver()  # LangGraph 체크포인트 (in-memory)
        self.graph = create_main_graph(self.checkpointer)  # 메인 그래프 컴파일
    
    async def process_message(
        self,
        session_id: str,
        exam_id: int,
        participant_id: int,
        spec_id: int,
        human_message: str,
        is_submission: bool = False,
        code_content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        메시지 처리 및 평가 실행
        
        [처리 흐름]
        1. Redis에서 기존 상태 로드 (또는 초기 상태 생성)
        2. LangGraph 메인 플로우 실행
           - 일반 채팅: Handle Request → Intent Analyzer → Writer LLM → END
           - 제출: Intent Analyzer → Eval Turn Guard (모든 턴 평가) → 평가 노드들 → END
        3. 결과를 Redis에 저장
        4. 응답 반환
        
        [평가 실행 시점]
        - 일반 채팅(is_submission=False): 평가 실행하지 않음 (응답만 반환)
        - 제출(is_submission=True): Eval Turn Guard에서 모든 턴을 동기적으로 평가
        
        Args:
            session_id: 세션 ID (고유)
            exam_id: 시험 ID
            participant_id: 참가자 ID
            spec_id: 문제 스펙 ID
            human_message: 사용자 메시지
            is_submission: 제출 여부 (False: 일반 채팅, True: 코드 제출)
            code_content: 제출 코드 (제출 시만 필요)
        
        Returns:
            Dict[str, Any]: 처리 결과
                - session_id: 세션 ID
                - turn: 현재 턴 번호
                - ai_message: AI 응답 메시지
                - is_submitted: 제출 완료 여부
                - error_message: 에러 메시지 (에러 시)
                - final_scores: 최종 점수 (제출 시)
                - turn_scores: 턴별 점수 (제출 시)
        """
        try:
            # 기존 상태 로드 또는 초기 상태 생성
            existing_state = await self.state_repo.get_state(session_id)
            
            if existing_state:
                # 기존 상태 업데이트
                state = existing_state
                state["human_message"] = human_message
                state["is_submitted"] = is_submission
                if code_content:
                    state["code_content"] = code_content
            else:
                # 초기 상태 생성
                state = get_initial_state(
                    session_id=session_id,
                    exam_id=exam_id,
                    participant_id=participant_id,
                    spec_id=spec_id,
                    human_message=human_message,
                )
                if is_submission:
                    state["is_submitted"] = True
                if code_content:
                    state["code_content"] = code_content
            
            # 그래프 실행
            config = {
                "configurable": {
                    "thread_id": session_id,
                }
            }
            
            logger.info(f"LangGraph 실행 시작 - session_id: {session_id}, is_submission: {is_submission}")
            result = await self.graph.ainvoke(state, config)
            logger.info(f"LangGraph 실행 완료 - session_id: {session_id}")
            
            # 디버깅: 결과 로깅
            logger.info(f"LangGraph 결과 - session_id: {session_id}, keys: {list(result.keys())}")
            logger.info(f"ai_message: {result.get('ai_message')}, messages count: {len(result.get('messages', []))}")
            if result.get('messages'):
                logger.info(f"마지막 메시지: {result.get('messages')[-1] if result.get('messages') else 'None'}")
            
            # ⚠️ 일반 채팅에서는 Eval Turn SubGraph를 실행하지 않음
            # 평가는 제출 시 Eval Turn Guard에서 모든 턴을 동기적으로 실행
            
            # 상태 저장
            await self.state_repo.save_state(session_id, result)
            
            # 응답 구성
            # ai_message가 없으면 messages 리스트에서 마지막 assistant 메시지 추출
            ai_message = result.get("ai_message")
            if not ai_message:
                messages = result.get("messages", [])
                # messages 리스트를 역순으로 검색하여 마지막 assistant 메시지 찾기
                for msg in reversed(messages):
                    if hasattr(msg, 'type') and msg.type == 'ai':
                        ai_message = msg.content
                        break
                    elif isinstance(msg, dict) and msg.get('role') == 'assistant':
                        ai_message = msg.get('content')
                        break
                    elif hasattr(msg, 'content'):
                        # 기본적으로 마지막 메시지가 AI 응답일 가능성이 높음
                        ai_message = msg.content
                        break
            
            # 토큰 사용량 추출
            token_summary = get_token_summary(result)
            
            # 토큰 사용량이 비어있으면 빈 dict 대신 None 또는 기본값 설정
            chat_tokens = token_summary.get("chat_tokens") or result.get("chat_tokens")
            eval_tokens = token_summary.get("eval_tokens") or result.get("eval_tokens")
            
            # 빈 dict가 아닌 경우에만 포함
            if chat_tokens and isinstance(chat_tokens, dict) and any(chat_tokens.values()):
                logger.info(f"[EvalService] ✅ chat_tokens 발견: {chat_tokens}")
            else:
                logger.warning(f"[EvalService] ⚠️ chat_tokens 없음 - token_summary: {token_summary.get('chat_tokens')}, result: {result.get('chat_tokens')}")
                chat_tokens = chat_tokens or {}
            
            if eval_tokens and isinstance(eval_tokens, dict) and any(eval_tokens.values()):
                logger.info(f"[EvalService] ✅ eval_tokens 발견: {eval_tokens}")
            else:
                logger.debug(f"[EvalService] eval_tokens 없음 (백그라운드 평가는 아직 완료되지 않았을 수 있음)")
                eval_tokens = eval_tokens or {}
            
            response = {
                "session_id": session_id,
                "turn": result.get("current_turn", 0),
                "ai_message": ai_message,
                "is_submitted": result.get("is_submitted", False),
                "error_message": result.get("error_message"),
                "chat_tokens": chat_tokens,
                "eval_tokens": eval_tokens,
            }
            
            # 제출된 경우 최종 점수 포함
            if result.get("is_submitted") and result.get("final_scores"):
                response["final_scores"] = result.get("final_scores")
                response["turn_scores"] = result.get("turn_scores")
            
            return response
            
        except Exception as e:
            logger.error(f"[EvalService] 메시지 처리 중 오류 발생 - session_id: {session_id}", exc_info=True)
            logger.error(f"[EvalService] 에러 타입: {type(e).__name__}, 메시지: {str(e)}")
            
            # 에러 상세 정보 수집
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "session_id": session_id,
            }
            
            # 에러가 발생한 위치 추적
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"[EvalService] 에러 스택 트레이스:\n{error_trace}")
            
            return {
                "session_id": session_id,
                "error": True,
                "error_message": f"처리 중 오류가 발생했습니다: {str(e)}",
                "error_details": error_details,
            }
    
    async def process_message_stream(
        self,
        session_id: str,
        exam_id: int,
        participant_id: int,
        spec_id: int,
        human_message: str,
        is_submission: bool = False,
        code_content: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """
        메시지 처리 및 스트리밍 (WebSocket용)
        
        [처리 흐름]
        1. Redis에서 기존 상태 로드 (또는 초기 상태 생성)
        2. LangGraph 메인 플로우 스트리밍 실행
           - Writer LLM의 토큰 단위 스트리밍
           - Intent Analyzer, Writer LLM 등 모든 노드 실행
        3. 결과를 Redis에 저장
        
        [스트리밍 방식]
        - LangGraph의 `astream_events()` 사용
        - Writer LLM 노드의 delta 이벤트만 필터링
        - 토큰 단위로 yield
        
        [평가 실행 시점]
        - 일반 채팅(is_submission=False): 평가 실행하지 않음 (스트리밍만 수행)
        - 제출(is_submission=True): Eval Turn Guard에서 모든 턴을 동기적으로 평가
        
        Args:
            session_id: 세션 ID (고유)
            exam_id: 시험 ID
            participant_id: 참가자 ID
            spec_id: 문제 스펙 ID
            human_message: 사용자 메시지
            is_submission: 제출 여부 (False: 일반 채팅, True: 코드 제출)
            code_content: 제출 코드 (제출 시만 필요)
        
        Yields:
            str: Writer LLM의 토큰 청크
        """
        try:
            # 기존 상태 로드 또는 초기 상태 생성
            existing_state = await self.state_repo.get_state(session_id)
            
            if existing_state:
                # 기존 상태 업데이트
                state = existing_state
                state["human_message"] = human_message
                state["is_submitted"] = is_submission
                if code_content:
                    state["code_content"] = code_content
            else:
                # 초기 상태 생성
                state = get_initial_state(
                    session_id=session_id,
                    exam_id=exam_id,
                    participant_id=participant_id,
                    spec_id=spec_id,
                    human_message=human_message,
                )
                if is_submission:
                    state["is_submitted"] = True
                if code_content:
                    state["code_content"] = code_content
            
            # 그래프 실행 설정
            config = {
                "configurable": {
                    "thread_id": session_id,
                }
            }
            
            logger.info(f"LangGraph 스트리밍 시작 - session_id: {session_id}, is_submission: {is_submission}")
            
            # Writer LLM 노드의 토큰만 스트리밍
            async for event in self.graph.astream_events(state, config, version="v2"):
                # Writer LLM 노드의 스트림 이벤트만 필터링
                if (
                    event.get("event") == "on_chat_model_stream"
                    and event.get("name") == "writer"
                ):
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        yield chunk.content
            
            logger.info(f"LangGraph 스트리밍 완료 - session_id: {session_id}")
            
            # 스트리밍 완료 후 최종 결과를 얻기 위해 상태를 다시 로드
            # (스트리밍 중 상태가 업데이트되었을 수 있음)
            final_result = await self.state_repo.get_state(session_id)
            
            # 최종 결과가 없거나 불완전한 경우 전체 그래프 재실행
            if not final_result or not final_result.get("ai_message"):
                logger.warning(f"스트리밍 후 상태가 불완전함 - 전체 실행으로 대체 - session_id: {session_id}")
                # 상태를 다시 준비
                if existing_state:
                    state = existing_state
                    state["human_message"] = human_message
                    state["is_submitted"] = is_submission
                    if code_content:
                        state["code_content"] = code_content
                else:
                    state = get_initial_state(
                        session_id=session_id,
                        exam_id=exam_id,
                        participant_id=participant_id,
                        spec_id=spec_id,
                        human_message=human_message,
                    )
                    if is_submission:
                        state["is_submitted"] = True
                    if code_content:
                        state["code_content"] = code_content
                
                final_result = await self.graph.ainvoke(state, config)
            
            # 디버깅: 결과 로깅
            logger.info(f"LangGraph 결과 - session_id: {session_id}, keys: {list(final_result.keys()) if final_result else 'None'}")
            
            # ⚠️ 일반 채팅에서는 Eval Turn SubGraph를 실행하지 않음
            # 평가는 제출 시 Eval Turn Guard에서 모든 턴을 동기적으로 실행
            
            # 상태 저장
            if final_result:
                await self.state_repo.save_state(session_id, final_result)
            
        except Exception as e:
            logger.error(f"[EvalService] 스트리밍 처리 중 오류 발생 - session_id: {session_id}", exc_info=True)
            logger.error(f"[EvalService] 에러 타입: {type(e).__name__}, 메시지: {str(e)}")
            # 스트리밍 중 에러는 yield로 전달할 수 없으므로 로깅만 수행
            raise
    
    async def submit_code(
        self,
        session_id: str,
        exam_id: int,
        participant_id: int,
        spec_id: int,
        code_content: str,
        lang: str = "python",
    ) -> Dict[str, Any]:
        """
        코드 제출 및 최종 평가
        
        Args:
            session_id: 세션 ID
            exam_id: 시험 ID
            participant_id: 참가자 ID
            spec_id: 문제 스펙 ID
            code_content: 제출 코드
            lang: 프로그래밍 언어
        
        Returns:
            평가 결과
        """
        # 기존 상태 로드 또는 초기 상태 생성
        existing_state = await self.state_repo.get_state(session_id)
        
        if existing_state:
            # 기존 상태 업데이트
            existing_state["human_message"] = "코드를 제출합니다."
            existing_state["is_submitted"] = True
            existing_state["code_content"] = code_content
            existing_state["lang"] = lang
        else:
            # 초기 상태 생성
            state = get_initial_state(
                session_id=session_id,
                exam_id=exam_id,
                participant_id=participant_id,
                spec_id=spec_id,
                human_message="코드를 제출합니다.",
            )
            state["is_submitted"] = True
            state["code_content"] = code_content
            state["lang"] = lang
            existing_state = state
        
        # 그래프 실행
        config = {
            "configurable": {
                "thread_id": session_id,
            }
        }
        
        logger.info(f"[SubmitCode] ===== LangGraph 실행 시작 (제출) =====")
        logger.info(f"[SubmitCode] session_id: {session_id}, exam_id: {exam_id}, participant_id: {participant_id}")
        logger.info(f"[SubmitCode] spec_id: {spec_id}, lang: {lang}, code_length: {len(code_content)}")
        # f-string 내부에서 backslash 사용 불가하므로 변수로 분리
        code_preview = code_content[:200].replace('\n', '\\n')
        logger.info(f"[SubmitCode] 코드 미리보기 (처음 200자): {code_preview}")
        
        result = await self.graph.ainvoke(existing_state, config)
        
        logger.info(f"[SubmitCode] ===== LangGraph 실행 완료 (제출) =====")
        logger.info(f"[SubmitCode] session_id: {session_id}")
        logger.info(f"[SubmitCode] is_submitted: {result.get('is_submitted', False)}")
        logger.info(f"[SubmitCode] final_scores: {result.get('final_scores')}")
        logger.info(f"[SubmitCode] submission_id: {result.get('submission_id')}")
        
        # 상태 저장
        await self.state_repo.save_state(session_id, result)
        
        # 응답 구성
        ai_message = result.get("ai_message")
        if not ai_message and result.get("messages"):
            # messages 리스트에서 마지막 assistant 메시지 추출
            messages = result.get("messages", [])
            for msg in reversed(messages):
                if hasattr(msg, "content") and hasattr(msg, "type") and msg.type == "ai":
                    ai_message = msg.content
                    break
        
        # 토큰 사용량 추출
        token_summary = get_token_summary(result)
        chat_tokens = token_summary.get("chat_tokens")
        eval_tokens = token_summary.get("eval_tokens")
        
        response = {
            "session_id": session_id,
            "turn": result.get("current_turn", 0),
            "ai_message": ai_message,
            "is_submitted": result.get("is_submitted", False),
            "error_message": result.get("error_message"),
            "chat_tokens": chat_tokens,
            "eval_tokens": eval_tokens,
        }
        
        # 제출된 경우 최종 점수 포함
        if result.get("is_submitted") and result.get("final_scores"):
            response["final_scores"] = result.get("final_scores")
            response["turn_scores"] = result.get("turn_scores")
            response["submission_id"] = result.get("submission_id")
        
        return response
    
    async def get_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """세션 상태 조회"""
        return await self.state_repo.get_state(session_id)
    
    async def get_session_scores(self, session_id: str) -> Optional[Dict[str, Any]]:
        """세션 점수 조회"""
        return await self.state_repo.get_all_turn_scores(session_id)
    
    async def clear_session(self, session_id: str) -> bool:
        """세션 상태 삭제"""
        return await self.state_repo.delete_state(session_id)
    
    async def get_conversation_history(
        self, 
        session_id: str
    ) -> Optional[list]:
        """대화 히스토리 조회"""
        state = await self.state_repo.get_state(session_id)
        if state:
            messages = state.get("messages", [])
            return [
                {
                    "role": getattr(msg, 'type', 'user') if hasattr(msg, 'type') else msg.get('role', 'user'),
                    "content": getattr(msg, 'content', '') if hasattr(msg, 'content') else msg.get('content', ''),
                }
                for msg in messages
            ]
        return None
    
    async def _run_eval_turn_background(
        self,
        session_id: str,
        main_state: Dict[str, Any]
    ) -> None:
        """
        4번 노드(Eval Turn SubGraph)를 백그라운드에서 실행
        
        [목적]
        - 일반 채팅의 각 턴마다 비동기로 평가 수행
        - 사용자 응답 지연 없이 실시간 평가
        
        [처리 과정]
        1. Eval Turn SubGraph 생성
        2. EvalTurnState 준비 (session_id, turn, messages, guardrail_info)
        3. SubGraph 실행
           - 4.0 Intent Analysis: 의도 분석
           - 4.R/G/O/D/T/H/F: 의도별 평가
           - 4.X Answer Summary: 답변 요약
           - 4.4 Turn Log Aggregation: 턴 로그 집계
        4. Redis에 turn_logs 저장
        5. 메인 state의 turn_scores 업데이트
        
        [저장 데이터]
        - turn_logs:{session_id}:{turn}: 상세 평가 로그
        - graph_state:{session_id}: turn_scores 업데이트
        
        [에러 처리]
        - 모든 예외 캡처 및 로깅
        - 에러 발생 시에도 메인 플로우에 영향 없음 (백그라운드)
        
        Args:
            session_id: 세션 ID
            main_state: 메인 그래프의 현재 상태
        """
        try:
            from app.domain.langgraph.subgraph_eval_turn import create_eval_turn_subgraph
            from app.domain.langgraph.states import EvalTurnState
            
            logger.info(f"[EvalService] 4번 노드 백그라운드 실행 시작 - session_id: {session_id}")
            
            # Eval Turn SubGraph 생성
            eval_turn_subgraph = create_eval_turn_subgraph()
            
            # SubGraph 입력 준비
            turn_state: EvalTurnState = {
                "session_id": session_id,
                "turn": main_state.get("current_turn", 0),
                "human_message": main_state.get("human_message", ""),
                "ai_message": main_state.get("ai_message", ""),
                "problem_context": main_state.get("problem_context"),  # 문제 정보 전달
                "is_guardrail_failed": main_state.get("is_guardrail_failed", False),
                "guardrail_message": main_state.get("guardrail_message"),
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
            
            # SubGraph 실행 (비동기)
            result = await eval_turn_subgraph.ainvoke(turn_state)
            
            current_turn = main_state.get("current_turn", 0)
            
            # intent_type은 turn_log에서 가져오거나, intent_types의 첫 번째 값 사용
            turn_log = result.get("turn_log", {})
            intent_types = turn_log.get("intent_types", [])
            intent_type = turn_log.get("intent_type") or (intent_types[0] if intent_types else "UNKNOWN")
            
            turn_score = result.get("turn_score", 0)
            
            # 개별 평가 결과에서 rubrics 생성 (상세 피드백 포함)
            evaluations = []
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
            detailed_evaluations = []
            for eval_key, criterion_name in eval_mapping.items():
                eval_result = result.get(eval_key)
                if eval_result and isinstance(eval_result, dict):
                    # 기본 정보
                    score = eval_result.get("score", eval_result.get("average", 0))
                    final_reasoning = eval_result.get("final_reasoning", "평가 없음")
                    eval_rubrics = eval_result.get("rubrics", [])
                    
                    # Rubrics 생성 (간단한 형태)
                    rubrics.append({
                        "criterion": criterion_name,
                        "score": score,
                        "reason": final_reasoning[:200] + "..." if len(final_reasoning) > 200 else final_reasoning
                    })
                    
                    # 상세 평가 정보 (전체 rubrics와 final_reasoning 포함)
                    detailed_evaluations.append({
                        "criterion": criterion_name,
                        "score": score,
                        "final_reasoning": final_reasoning,
                        "rubrics": [
                            {
                                "criterion": r.get("criterion", ""),
                                "score": r.get("score", 0),
                                "reason": r.get("reason", "")
                            }
                            for r in eval_rubrics
                        ] if isinstance(eval_rubrics, list) else []
                    })
            
            # 전체 턴에 대한 종합 평가 근거 생성
            # 모든 평가의 final_reasoning을 종합하여 전체 평가 의견 생성
            all_reasonings = [e.get("final_reasoning", "") for e in detailed_evaluations if e.get("final_reasoning")]
            comprehensive_reasoning = "\n\n".join([
                f"[{e.get('criterion')}] {e.get('final_reasoning', '')}"
                for e in detailed_evaluations
            ]) if detailed_evaluations else "평가 완료"
            
            # turn_log에서 상세 피드백 정보 가져오기
            turn_log_data = result.get("turn_log", {})
            detailed_feedback_from_log = turn_log_data.get("detailed_feedback", [])
            comprehensive_reasoning_from_log = turn_log_data.get("comprehensive_reasoning", comprehensive_reasoning)
            
            # detailed_feedback이 없으면 detailed_evaluations에서 생성
            if not detailed_feedback_from_log and detailed_evaluations:
                detailed_feedback_from_log = detailed_evaluations
            
            # 상세 turn_log 구조 생성 (사용자 정의 형식)
            detailed_turn_log = {
                "turn_number": current_turn,
                "user_prompt_summary": main_state.get("human_message", "")[:200] + "..." if len(main_state.get("human_message", "")) > 200 else main_state.get("human_message", ""),
                "prompt_evaluation_details": {
                    "intent": intent_type,
                    "score": turn_score,
                    "rubrics": rubrics,  # 간단한 형태 (요약)
                    "final_reasoning": comprehensive_reasoning_from_log,  # 전체 평가 근거 (LLM의 의견)
                    "detailed_evaluations": detailed_evaluations,  # 상세 평가 정보 (전체 rubrics 포함)
                    "detailed_feedback": detailed_feedback_from_log  # 상세 피드백 (각 Intent별 rubrics와 final_reasoning)
                },
                "llm_answer_summary": result.get("answer_summary", ""),
                "llm_answer_reasoning": comprehensive_reasoning_from_log[:500] + "..." if len(comprehensive_reasoning_from_log) > 500 else comprehensive_reasoning_from_log,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Redis에 상세 turn_log 저장
            await self.redis.save_turn_log(session_id, current_turn, detailed_turn_log)
            
            # PostgreSQL에 평가 결과 저장 (백그라운드)
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
                            "evaluations": detailed_turn_log.get("prompt_evaluation_details", {}).get("detailed_evaluations", {}),
                            "detailed_feedback": detailed_turn_log.get("prompt_evaluation_details", {}).get("detailed_feedback", []),
                            "turn_score": turn_score,
                            "is_guardrail_failed": main_state.get("is_guardrail_failed", False),
                            "guardrail_message": main_state.get("guardrail_message"),
                        }
                        
                        await storage_service.save_turn_evaluation(
                            session_id=postgres_session_id,
                            turn=current_turn,
                            turn_log=turn_log_for_storage
                        )
                        await db.commit()
                        logger.info(
                            f"[EvalService] PostgreSQL 턴 평가 저장 완료 - "
                            f"session_id: {postgres_session_id}, turn: {current_turn}"
                        )
            except Exception as pg_error:
                # PostgreSQL 저장 실패해도 Redis는 저장되었으므로 경고만
                logger.warning(
                    f"[EvalService] PostgreSQL 턴 평가 저장 실패 (Redis는 저장됨) - "
                    f"session_id: {session_id}, turn: {current_turn}, error: {str(pg_error)}"
                )
            
            # 기존 turn_scores도 업데이트 (호환성)
            turn_scores = main_state.get("turn_scores", {})
            turn_scores[str(current_turn)] = {
                "turn_score": turn_score,
                "turn_log": result.get("turn_log"),
                "intent_type": intent_type,
            }
            
            # EvalTurnState의 eval_tokens를 MainGraphState의 eval_tokens에 합산
            eval_tokens_from_turn = result.get("eval_tokens", {})
            if eval_tokens_from_turn:
                main_eval_tokens = main_state.get("eval_tokens", {}) or {}
                accumulated_eval_tokens = {
                    "prompt_tokens": main_eval_tokens.get("prompt_tokens", 0) + eval_tokens_from_turn.get("prompt_tokens", 0),
                    "completion_tokens": main_eval_tokens.get("completion_tokens", 0) + eval_tokens_from_turn.get("completion_tokens", 0),
                    "total_tokens": main_eval_tokens.get("total_tokens", 0) + eval_tokens_from_turn.get("total_tokens", 0),
                }
                main_state["eval_tokens"] = accumulated_eval_tokens
                logger.debug(f"[EvalService] Eval Turn 토큰 합산 - session_id: {session_id}, turn: {current_turn}, eval_tokens: {accumulated_eval_tokens}")
            
            # 업데이트된 turn_scores와 eval_tokens를 상태에 저장
            updated_state = {**main_state, "turn_scores": turn_scores}
            await self.state_repo.save_state(session_id, updated_state)
            
            logger.info(f"[EvalService] 4번 노드 백그라운드 실행 완료 - session_id: {session_id}, turn: {current_turn}, score: {turn_score}, intent: {intent_type}")
            
        except Exception as e:
            logger.error(f"[EvalService] 4번 노드 백그라운드 실행 중 오류 - session_id: {session_id}, error: {str(e)}", exc_info=True)



