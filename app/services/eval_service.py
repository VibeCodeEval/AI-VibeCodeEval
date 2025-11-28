"""
평가 서비스 (Evaluation Service)

[목적]
- LangGraph 메인 플로우의 실행을 관리하는 핵심 서비스
- Redis를 통한 상태 관리
- 백그라운드 평가 (Eval Turn SubGraph) 실행

[주요 역할]
1. process_message(): 일반 채팅 메시지 처리
   - LangGraph 메인 플로우 실행
   - Redis 상태 로드/저장
   - 백그라운드 턴 평가 시작 (비동기)
   
2. submit_code(): 코드 제출 및 최종 평가
   - is_submission=True로 설정
   - 전체 평가 플로우 실행
   - 최종 점수 산출

3. _run_eval_turn_background(): 백그라운드 평가
   - Eval Turn SubGraph 실행
   - 턴별 평가 로그 생성
   - Redis에 turn_logs 저장

[아키텍처]
API 요청 → EvalService → LangGraph → Redis
                     ↓
            Eval Turn SubGraph (백그라운드)
"""
from typing import Optional, Dict, Any
from datetime import datetime
import logging

from langgraph.checkpoint.memory import MemorySaver

from app.langgraph.graph import create_main_graph, get_initial_state
from app.langgraph.states import MainGraphState
from app.db.redis_client import RedisClient
from app.db.repositories.state_repo import StateRepository
from app.db.repositories.session_repo import SessionRepository
from app.db.session import get_db_context
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
    3. _run_eval_turn_background(): 백그라운드 평가 (일반 채팅만)
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
           - Handle Request → Intent Analyzer → Writer LLM → END
           - 또는 제출 시: Intent Analyzer → Eval Turn Guard → 평가 노드들 → END
        3. 일반 채팅: Eval Turn SubGraph를 백그라운드로 실행
        4. 결과를 Redis에 저장
        5. 응답 반환
        
        [백그라운드 평가]
        - 일반 채팅(is_submission=False): _run_eval_turn_background() 비동기 실행
        - 제출(is_submission=True): 백그라운드 없음 (동기적으로 모든 평가 완료)
        
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
            
            # 일반 채팅인 경우 4번 노드(Eval Turn)를 백그라운드로 실행
            if not is_submission and result.get("ai_message"):
                logger.info(f"[EvalService] 일반 채팅 - 4번 노드(Eval Turn) 백그라운드 실행 시작")
                # 백그라운드 태스크로 4번 노드 실행
                import asyncio
                asyncio.create_task(self._run_eval_turn_background(session_id, result))
            
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
            
            response = {
                "session_id": session_id,
                "turn": result.get("current_turn", 0),
                "ai_message": ai_message,
                "is_submitted": result.get("is_submitted", False),
                "error_message": result.get("error_message"),
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
        return await self.process_message(
            session_id=session_id,
            exam_id=exam_id,
            participant_id=participant_id,
            spec_id=spec_id,
            human_message="코드를 제출합니다.",
            is_submission=True,
            code_content=code_content,
        )
    
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
            from app.langgraph.subgraph_eval_turn import create_eval_turn_subgraph
            from app.langgraph.states import EvalTurnState
            
            logger.info(f"[EvalService] 4번 노드 백그라운드 실행 시작 - session_id: {session_id}")
            
            # Eval Turn SubGraph 생성
            eval_turn_subgraph = create_eval_turn_subgraph()
            
            # SubGraph 입력 준비
            turn_state: EvalTurnState = {
                "session_id": session_id,
                "turn": main_state.get("current_turn", 0),
                "human_message": main_state.get("human_message", ""),
                "ai_message": main_state.get("ai_message", ""),
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
            intent_type = result.get("intent_type", "UNKNOWN")
            turn_score = result.get("turn_score", 0)
            
            # 개별 평가 결과에서 rubrics 생성
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
            for eval_key, criterion_name in eval_mapping.items():
                eval_result = result.get(eval_key)
                if eval_result and isinstance(eval_result, dict):
                    rubrics.append({
                        "criterion": criterion_name,
                        "score": eval_result.get("average", 0),
                        "reason": eval_result.get("feedback", "평가 없음")
                    })
            
            # 상세 turn_log 구조 생성 (사용자 정의 형식)
            detailed_turn_log = {
                "turn_number": current_turn,
                "user_prompt_summary": main_state.get("human_message", "")[:200] + "..." if len(main_state.get("human_message", "")) > 200 else main_state.get("human_message", ""),
                "prompt_evaluation_details": {
                    "intent": intent_type,
                    "score": turn_score,
                    "rubrics": rubrics,
                    "final_reasoning": result.get("answer_summary", "평가 완료")
                },
                "llm_answer_summary": result.get("answer_summary", ""),
                "llm_answer_reasoning": rubrics[0].get("reason", "") if rubrics else "평가 없음",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Redis에 상세 turn_log 저장
            await self.redis.save_turn_log(session_id, current_turn, detailed_turn_log)
            
            # 기존 turn_scores도 업데이트 (호환성)
            turn_scores = main_state.get("turn_scores", {})
            turn_scores[str(current_turn)] = {
                "turn_score": turn_score,
                "turn_log": result.get("turn_log"),
                "intent_type": intent_type,
            }
            
            # 업데이트된 turn_scores를 상태에 저장
            updated_state = {**main_state, "turn_scores": turn_scores}
            await self.state_repo.save_state(session_id, updated_state)
            
            logger.info(f"[EvalService] 4번 노드 백그라운드 실행 완료 - session_id: {session_id}, turn: {current_turn}, score: {turn_score}, intent: {intent_type}")
            
        except Exception as e:
            logger.error(f"[EvalService] 4번 노드 백그라운드 실행 중 오류 - session_id: {session_id}, error: {str(e)}", exc_info=True)



