"""
채팅 API 라우터

[목적]
- 사용자와 AI 어시스턴트 간의 대화 처리
- 코드 제출 및 최종 평가 실행
- WebSocket 스트리밍 지원

[주요 엔드포인트]
1. POST/api/chat/message
   - 일반 채팅 메시지 전송
   - AI 응답 생성 및 턴별 평가 (백그라운드)
   
2. POST/api/chat/submit
   - 최종 코드 제출
   - 전체 평가 실행 (Holistic Flow, 성능, 정확성)
   - 최종 점수 산출

3. WS /api/chat/ws
   - WebSocket 스트리밍 채팅
   - Delta 스트리밍, 취소 기능, turnId 전달
   - LangGraph 사용 (Intent Analyzer, Writer LLM, Eval Turn 포함)

[처리 흐름]
1. 요청 수신 → 2. EvalService 호출 → 3. LangGraph 실행 → 4. 응답 반환

[에러 처리]
- Timeout: 60초 초과 시 타임아웃 응답
- Exception: 모든 예외 캡처 및 에러 응답 반환
"""
import asyncio
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Query

from app.presentation.schemas.chat import (
    ChatRequest, ChatResponse, SubmitRequest, SubmitResponse,
    SaveChatMessageRequest, SaveChatMessageResponse,
    ChatMessagesRequest, ChatMessagesResponse, AIMessageInfo
)
from app.presentation.schemas.common import ErrorResponse
from app.application.services.eval_service import EvalService
from app.infrastructure.cache.redis_client import redis_client, get_redis
from app.core.config import settings
from app.domain.langgraph.utils.problem_info import get_problem_info_sync
from app.application.services.message_storage_service import MessageStorageService
from app.infrastructure.persistence.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession
import json


router = APIRouter(prefix="/chat", tags=["Chat"])


async def get_eval_service() -> EvalService:
    """
    EvalService 의존성 주입
    
    [역할]
    - FastAPI의 Depends 메커니즘을 사용한 의존성 주입
    - 각 API 요청마다 EvalService 인스턴스 생성
    - Redis 클라이언트를 EvalService에 전달
    
    [반환값]
    EvalService: 평가 서비스 인스턴스
    """
    return EvalService(redis_client)


@router.post(
    "/messages",
    response_model=ChatMessagesResponse,
    responses={
        404: {"model": ErrorResponse, "description": "세션을 찾을 수 없음"},
        504: {"model": ErrorResponse, "description": "요청 처리 시간 초과"},
        500: {"model": ErrorResponse, "description": "서버 에러"}
    },
    summary="메시지 전송 (신규)",
    description="""
    사용자 메시지를 전송하고 AI 응답을 받습니다.
    
    **처리 과정:**
    1. 세션 존재 확인
    2. LangGraph 실행 (Intent Analyzer → Writer LLM)
    3. AI 응답 생성
    4. 토큰 계산 (이전 토큰 + 현재 토큰)
    5. Response 반환 (aiMessage만 반환)
    
    **참고:**
    - 메시지 저장은 백엔드에서 처리합니다.
    - Worker는 AI 응답 생성만 담당합니다.
    """
)
async def send_messages(
    request: ChatMessagesRequest,
    db: AsyncSession = Depends(get_db),
    eval_service: EvalService = Depends(get_eval_service)
) -> ChatMessagesResponse:
    """
    메시지 전송 및 AI 응답 받기 (신규 API)
    
    [처리 흐름]
    1. 세션 존재 확인 (get_session_by_id) - 없으면 404
    2. LangGraph 실행 (AI 응답 생성)
    3. 토큰 계산 (이전 토큰 + 현재 토큰)
    4. Response 반환 (aiMessage만 반환)
    
    [에러 처리]
    - 세션 없음 (404): SESSION_NOT_FOUND
    - Timeout (120초): TIMEOUT
    - LangGraph 실행 실패: INTERNAL_ERROR
    
    [반환값]
    ChatMessagesResponse: AI 응답 메시지 (aiMessage만 포함)
    """
    import asyncio
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(
            f"[SendMessages] 메시지 수신 - "
            f"sessionId: {request.sessionId}, turnId: {request.turnId}, "
            f"content: {request.content[:50]}..."
        )
        
        # [1] 세션 존재 확인
        # 세션은 BE에서 생성하므로, 여기서는 조회만 수행
        from app.infrastructure.repositories.session_repository import SessionRepository
        session_repo = SessionRepository(db)
        
        session = await session_repo.get_session_by_id(request.sessionId)
        
        if not session:
            logger.error(
                f"[SendMessages] 세션을 찾을 수 없음 - "
                f"sessionId: {request.sessionId}, participantId: {request.participantId}. "
                f"BE에서 세션을 생성했는지 확인하세요."
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": True,
                    "error_code": "SESSION_NOT_FOUND",
                    "error_message": f"세션을 찾을 수 없습니다. (session_id: {request.sessionId}). BE에서 세션을 먼저 생성해야 합니다."
                }
            )
        
        logger.info(
            f"[SendMessages] 세션 확인 완료 - "
            f"session_id: {session.id}, exam_id: {session.exam_id}, "
            f"participant_id: {session.participant_id}, spec_id: {session.spec_id}"
        )
        
        # [2] 사용자 메시지 토큰 계산 함수 (LLM 응답 생성과 병렬 처리)
        import tiktoken
        
        async def calculate_user_tokens():
            """사용자 메시지 토큰 계산 (비동기)"""
            try:
                # Gemini 모델의 인코딩 사용 (cl100k_base는 GPT-3.5/4와 호환)
                encoding = tiktoken.get_encoding("cl100k_base")
                return len(encoding.encode(request.content))
            except Exception as e:
                logger.warning(f"[SendMessages] 사용자 메시지 토큰 계산 실패: {str(e)}, 대략적 추정 사용")
                # 대략적 추정: 한글은 약 1.5자당 1토큰, 영문은 약 4자당 1토큰
                return len(request.content) // 3
        
        # LLM 응답 생성과 사용자 메시지 토큰 계산을 병렬 처리
        redis_session_id = f"session_{session.id}"
        
        # LangGraph 실행 전 State의 chat_tokens 저장 (누적된 값)
        # 현재 Turn의 토큰만 계산하기 위해 필요
        from app.infrastructure.cache.redis_client import redis_client
        state_before = await redis_client.get_graph_state(redis_session_id)
        previous_chat_tokens_before = state_before.get("chat_tokens", {}) if state_before else {}
        previous_total_before = previous_chat_tokens_before.get("total_tokens", 0) if isinstance(previous_chat_tokens_before, dict) else 0
        
        langgraph_task = asyncio.create_task(
            eval_service.process_message(
                session_id=redis_session_id,
                exam_id=session.exam_id,
                participant_id=session.participant_id,
                spec_id=session.spec_id or request.context.specVersion,
                human_message=request.content,
            )
        )
        user_tokens_task = asyncio.create_task(calculate_user_tokens())
        
        # 두 작업 모두 완료 대기
        result, user_message_tokens = await asyncio.gather(
            asyncio.wait_for(langgraph_task, timeout=120.0),
            user_tokens_task
        )
        
        # [3] AI 응답 및 토큰 추출
        if result.get("error"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": True,
                    "error_code": "LANGGRAPH_ERROR",
                    "error_message": result.get("error_message", "LangGraph 실행 중 오류가 발생했습니다.")
                }
            )
        
        ai_content = result.get("ai_message", "")
        if not ai_content:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": True,
                    "error_code": "NO_AI_RESPONSE",
                    "error_message": "AI 응답을 생성할 수 없습니다."
                }
            )
        
        # [4] 토큰 계산
        # chat_tokens는 누적된 값이므로, 현재 Turn의 토큰만 추출
        chat_tokens = result.get("chat_tokens", {})
        total_tokens_after = chat_tokens.get("total_tokens", 0) if isinstance(chat_tokens, dict) else 0
        
        # 현재 Turn의 AI 응답 토큰 = 실행 후 누적값 - 실행 전 누적값
        ai_response_tokens = total_tokens_after - previous_total_before
        
        # tokenCount = 현재 턴 대화 토큰 (사용자 메시지 + AI 응답)
        # 현재 턴에서만 사용된 토큰 수
        current_turn_tokens = user_message_tokens + ai_response_tokens
        
        # 이전 턴들의 누적 토큰 조회 (Redis 우선, 없으면 PostgreSQL Fallback)
        # totalToken = 한 세션의 모든 대화 token_count의 합
        # 주의: 첫 Turn (turnId=1)일 때는 previous_tokens = 0
        previous_tokens = 0
        
        # 첫 Turn이 아니면 이전 턴들의 토큰 조회
        if request.turnId > 1:
            try:
                # Redis에서 조회 시도
                previous_tokens_redis = await redis_client.get(f"session_token:{session.id}")
                if previous_tokens_redis:
                    previous_tokens = int(previous_tokens_redis)
                else:
                    # Redis에 없으면 PostgreSQL에서 조회 (Fallback)
                    # prompt_messages 테이블의 현재 turnId보다 작은 턴들의 token_count 합계
                    from app.infrastructure.persistence.models.sessions import PromptMessage
                    from sqlalchemy import select, func
                    
                    previous_tokens_query = select(func.coalesce(func.sum(PromptMessage.token_count), 0)).where(
                        PromptMessage.session_id == session.id,
                        PromptMessage.turn < request.turnId  # 현재 Turn보다 작은 턴들만
                    )
                    previous_tokens_result = await db.execute(previous_tokens_query)
                    previous_tokens = previous_tokens_result.scalar() or 0
                    
                    # Redis에 저장 (다음 요청을 위해)
                    await redis_client.set(f"session_token:{session.id}", str(previous_tokens))
            except Exception as e:
                logger.warning(f"[SendMessages] 이전 토큰 조회 실패: {str(e)}, 0으로 시작")
                previous_tokens = 0
        else:
            # 첫 Turn이면 이전 토큰은 0
            logger.debug(f"[SendMessages] 첫 Turn (turnId={request.turnId}), previous_tokens=0")
        
        # totalToken = 한 세션의 모든 대화 token_count의 합
        # (이전 모든 턴들의 token_count 합계 + 현재 턴의 token_count)
        total_tokens = previous_tokens + current_turn_tokens
        
        # Redis에 업데이트된 totalToken 저장 (다음 요청을 위해)
        try:
            await redis_client.set(f"session_token:{session.id}", str(total_tokens))
        except Exception as e:
            logger.warning(f"[SendMessages] Redis 토큰 저장 실패: {str(e)}")
        
        # [5] Turn 계산 (이전 Turn + 1)
        ai_turn = request.turnId + 1  # 사용자 턴 다음이 AI 턴
        
        # [6] Response 생성
        ai_message = AIMessageInfo(
            sessionId=session.id,
            turn=ai_turn,
            role="AI",
            content=ai_content,
            tokenCount=current_turn_tokens,  # 현재 턴 대화 토큰 (사용자 메시지 + AI 응답)
            totalToken=total_tokens  # 한 세션의 모든 대화 token_count의 합
        )
        
        # [7] 메시지 DB 저장 (테스트 환경에서는 비활성화)
        # 웹 채팅 Flow 테스트 시 DB 저장은 진행하지 않음
        # USER 메시지 저장 (한 turn에 하나의 메시지만 저장 가능하므로 USER만 저장)
        # try:
        #     from app.infrastructure.persistence.models.sessions import PromptMessage
        #     from app.infrastructure.persistence.models.enums import PromptRoleEnum
        #     from sqlalchemy import select
        #     
        #     # 해당 turn의 메시지가 이미 존재하는지 확인
        #     message_query = select(PromptMessage).where(
        #         PromptMessage.session_id == session.id,
        #         PromptMessage.turn == request.turnId
        #     )
        #     existing_message = await db.execute(message_query)
        #     message = existing_message.scalar_one_or_none()
        #     
        #     if not message:
        #         # USER 메시지 저장 (Foreign Key 제약 조건 충족)
        #         user_message = PromptMessage(
        #             session_id=session.id,
        #             turn=request.turnId,
        #             role=PromptRoleEnum.USER,
        #             content=request.content[:10000] if len(request.content) > 10000 else request.content,  # TEXT 필드 길이 제한 고려
        #             token_count=user_message_tokens
        #         )
        #         db.add(user_message)
        #         await db.commit()
        #         logger.info(
        #             f"[SendMessages] USER 메시지 저장 완료 - "
        #             f"session_id: {session.id}, turn: {request.turnId}"
        #         )
        #     else:
        #         logger.debug(
        #             f"[SendMessages] 메시지 이미 존재 - "
        #             f"session_id: {session.id}, turn: {request.turnId}"
        #         )
        # except Exception as msg_error:
        #     # 메시지 저장 실패해도 응답은 반환 (경고만)
        #     logger.warning(
        #         f"[SendMessages] 메시지 저장 실패 (응답은 반환) - "
        #         f"session_id: {session.id}, turn: {request.turnId}, error: {str(msg_error)}"
        #     )
        
        logger.debug(
            f"[SendMessages] DB 저장 건너뜀 (테스트 모드) - "
            f"session_id: {session.id}, turn: {request.turnId}"
        )
        
        logger.info(
            f"[SendMessages] 완료 - "
            f"session_id: {session.id}, turn: {ai_turn}, "
            f"user_tokens: {user_message_tokens}, ai_tokens: {ai_response_tokens}, "
            f"tokenCount (현재 턴): {current_turn_tokens}, totalToken (전체 누적): {total_tokens}"
        )
        
        return ChatMessagesResponse(aiMessage=ai_message)
        
    except HTTPException:
        raise
    except asyncio.TimeoutError:
        logger.error(f"[SendMessages] 타임아웃 - sessionId: {request.sessionId}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "error": True,
                "error_code": "TIMEOUT",
                "error_message": "요청 처리 시간이 초과되었습니다. (2분 타임아웃) - LLM API 응답 지연 또는 Quota 제한 가능"
            }
        )
    except Exception as e:
        logger.error(f"[SendMessages] 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": True,
                "error_code": "INTERNAL_ERROR",
                "error_message": f"메시지 전송 중 오류가 발생했습니다: {str(e)}"
            }
        )


# ===== [DEPRECATED] 레거시 API - 주석처리됨 (2024-12-07) =====
# 신규 API: POST /api/chat/messages 사용
# ============================================================

# @router.post(
#     "/message",
#     response_model=ChatResponse,
#     responses={
#         500: {"model": ErrorResponse, "description": "서버 에러"}
#     },
#     summary="메시지 전송",
#     description="""
#     AI 어시스턴트에게 메시지를 전송하고 응답을 받습니다.
#     
#     **처리 과정:**
#     1. Intent Analyzer: 의도 분석 및 가드레일 체크
#     2. Writer LLM: AI 답변 생성 (Socratic 방식)
#     3. Eval Turn SubGraph: 턴별 평가 (백그라운드)
#     4. Redis 상태 저장
#     
#     **제한사항:**
#     - Timeout: 60초
#     - 가드레일 위반 시: 교육적 피드백 반환
#     """
# )
# async def send_message(
#     request: ChatRequest,
#     eval_service: EvalService = Depends(get_eval_service),
#     db: AsyncSession = Depends(get_db)
# ) -> ChatResponse:
#     """
#     메시지 전송 및 AI 응답 받기
#     
#     [처리 흐름]
#     1. 세션 생성/조회 (get_or_create_session)
#     2. 다음 턴 번호 계산 (get_next_turn_number)
#     3. 사용자 메시지 저장 (PostgreSQL)
#     4. EvalService.process_message() 호출
#        - LangGraph 메인 플로우 실행
#        - Redis에서 기존 상태 로드
#        - Intent Analyzer → Writer LLM → 응답 반환
#        - Eval Turn SubGraph는 백그라운드로 비동기 실행
#     5. AI 응답 저장 (PostgreSQL)
#     6. 결과를 ChatResponse로 변환
#     
#     [에러 처리]
#     - Timeout (60초): 타임아웃 응답 반환
#     - LangGraph 실행 실패: 에러 메시지 포함한 응답 반환
#     - 가드레일 위반: is_guardrail_failed=True, 교육적 피드백 반환
#     
#     [반환값]
#     ChatResponse: AI 응답, 턴 번호, 에러 정보 등
#     """
#     import logging
#     logger = logging.getLogger(__name__)
#     
#     # 변수 초기화 (에러 처리에서 사용)
#     session = None
#     session_id_int = None  # 에러 처리에서 사용할 session.id (int)
#     next_turn = 0
#     redis_session_id = request.session_id
#     
#     try:
#         logger.info(f"메시지 수신 - session_id: {request.session_id}, message: {request.message[:50]}...")
#         
#         # [1] 세션 생성/조회 및 다음 턴 번호 계산
#         from app.infrastructure.repositories.session_repository import SessionRepository
#         session_repo = SessionRepository(db)
#         
#         # 세션 조회 또는 생성
#         session = await session_repo.get_or_create_session(
#             exam_id=request.exam_id,
#             participant_id=request.participant_id
#         )
#         
#         # 에러 처리에서 사용할 session.id를 미리 저장 (MissingGreenlet 방지)
#         session_id_int = session.id
#         
#         logger.info(
#             f"[SendMessage] 세션 확인 완료 - "
#             f"session_id: {session_id_int}, "
#             f"exam_id: {request.exam_id}, participant_id: {request.participant_id}"
#         )
#         
#         # [Step 1] 사용자 메시지 선저장 (Save First)
#         # turn=None을 넘겨서 DB가 자동으로 순차 번호를 할당하도록 함
#         from app.application.services.message_storage_service import MessageStorageService
#         from app.infrastructure.persistence.models.enums import PromptRoleEnum
#         
#         storage_service = MessageStorageService(db, redis_client)
#         
#         user_msg_result = await storage_service.save_message(
#             exam_id=request.exam_id,
#             participant_id=request.participant_id,
#             turn=None,  # DB에서 자동으로 MAX(turn) + 1 계산
#             role="user",
#             content=request.message
#         )
#         
#         await db.commit()  # 사용자 메시지 즉시 커밋
#         
#         # DB에서 할당된 실제 turn 번호 확인
#         user_turn = user_msg_result.get('turn')
#         
#         logger.info(
#             f"[SendMessage] 사용자 메시지 저장 완료 - "
#             f"session_id: {session_id_int}, message_id: {user_msg_result['message_id']}, turn: {user_turn}"
#         )
#         
#         # [Step 2] PostgreSQL session_id를 Redis session_id로 변환
#         # PostgreSQL: session.id (int) → Redis: "session_{id}" (str)
#         redis_session_id = f"session_{session_id_int}"
#         
#         # [Step 3] AI 응답 생성 (Generate)
#         # 1분 타임아웃 설정 (LLM 응답 시간 고려)
#         result = await asyncio.wait_for(
#             eval_service.process_message(
#                 session_id=redis_session_id,  # PostgreSQL ID 기반 Redis session_id
#                 exam_id=request.exam_id,
#                 participant_id=request.participant_id,
#                 spec_id=request.spec_id,
#                 human_message=request.message,
#             ),
#             timeout=60.0  # 1분
#         )
#         
#         logger.info(
#             f"[SendMessage] AI 응답 생성 완료 - session_id: {redis_session_id}, "
#             f"has_ai_message: {bool(result.get('ai_message'))}, "
#             f"error: {result.get('error')}"
#         )
#         
#         # [Step 4] AI 메시지 저장 (Save Second)
#         # turn=None을 넘겨서 DB가 자동으로 다음 순차 번호를 할당하도록 함
#         ai_turn = None
#         if result.get("ai_message") and not result.get("error"):
#             try:
#                 # 토큰 사용량 추출
#                 chat_tokens = result.get("chat_tokens", {})
#                 total_tokens = chat_tokens.get("total_tokens", 0) if isinstance(chat_tokens, dict) else 0
#                 
#                 # turn=None을 넘겨서 DB에서 자동으로 MAX(turn) + 1 계산
#                 ai_msg_result = await storage_service.save_message(
#                     exam_id=request.exam_id,
#                     participant_id=request.participant_id,
#                     turn=None,  # DB에서 자동으로 다음 turn 번호 계산
#                     role="assistant",
#                     content=result.get("ai_message"),
#                     token_count=total_tokens
#                 )
#                 await db.commit()
#                 
#                 # DB에서 할당된 실제 turn 번호 확인
#                 ai_turn = ai_msg_result.get('turn')
#                 
#                 logger.info(
#                     f"[SendMessage] AI 응답 저장 완료 - "
#                     f"session_id: {session_id_int}, message_id: {ai_msg_result['message_id']}, turn: {ai_turn}"
#                 )
#             except Exception as save_error:
#                 # AI 응답 저장 실패해도 사용자 메시지는 이미 저장되어 있음
#                 logger.error(
#                     f"[SendMessage] AI 응답 저장 실패 (사용자 메시지는 저장됨) - "
#                     f"session_id: {session_id_int}, error: {str(save_error)}",
#                     exc_info=True
#                 )
#         
#         # [Step 5] 응답 반환 (Return Last)
#         # 저장이 완료된 후 확정된 정보를 반환
#         # AI 메시지가 저장된 경우 ai_turn 사용, 아니면 user_turn 사용
#         final_turn = ai_turn if ai_turn is not None else user_turn
#         
#         # 에러 발생 시
#         if result.get("error"):
#             return ChatResponse(
#                 session_id=redis_session_id,
#                 turn=user_turn,  # 사용자 메시지의 turn 사용
#                 ai_message=None,
#                 is_submitted=False,
#                 error=True,
#                 error_message=result.get("error_message"),
#             )
#         
#         # 토큰 사용량을 Core 전달 형식으로 변환
#         from app.domain.langgraph.utils.token_tracking import format_tokens_for_core
#         core_tokens = format_tokens_for_core(
#             chat_tokens=result.get("chat_tokens"),
#             eval_tokens=result.get("eval_tokens")
#         )
#         
#         # 정상 응답 (저장이 완료된 후 반환)
#         return ChatResponse(
#             session_id=redis_session_id,
#             turn=final_turn,  # AI 메시지가 저장된 경우 ai_turn, 아니면 user_turn
#             ai_message=result.get("ai_message"),
#             is_submitted=result.get("is_submitted", False),
#             error=False,
#             error_message=None,
#             chat_tokens=core_tokens.get("chat_tokens"),
#             eval_tokens=core_tokens.get("eval_tokens"),
#             total_tokens=core_tokens.get("total_tokens"),
#         )
#     except asyncio.TimeoutError:
#         # LLM 응답이 60초 이내에 완료되지 않은 경우
#         # 원인: LLM API 지연, 네트워크 문제, Rate Limit 초과 등
#         # 사용자 메시지는 이미 저장되어 있음
#         if session_id_int:
#             redis_session_id = f"session_{session_id_int}"
#         logger.error(f"메시지 처리 타임아웃 - session_id: {redis_session_id}")
#         
#         # 사용자 메시지의 turn 번호 조회 (저장된 경우)
#         user_turn_for_error = 0
#         try:
#             if session_id_int:
#                 from sqlalchemy import select, func
#                 from app.infrastructure.persistence.models.sessions import PromptMessage
#                 from app.infrastructure.persistence.models.enums import PromptRoleEnum
#                 max_turn_query = select(func.max(PromptMessage.turn)).where(
#                     PromptMessage.session_id == session_id_int,
#                     PromptMessage.role == PromptRoleEnum.USER
#                 )
#                 max_result = await db.execute(max_turn_query)
#                 user_turn_for_error = max_result.scalar_one_or_none() or 0
#         except:
#             pass
#         
#         return ChatResponse(
#             session_id=redis_session_id,
#             turn=user_turn_for_error,
#             ai_message=None,
#             is_submitted=False,
#             error=True,
#             error_message="요청 처리 시간이 초과되었습니다. (1분 타임아웃)",
#         )
#     except Exception as e:
#         # 예상치 못한 모든 예외 처리
#         # 예: Redis 연결 실패, LLM API 에러, 상태 직렬화 오류 등
#         # 사용자 메시지는 이미 저장되어 있음 (세션 생성 성공 시)
#         if session_id_int:
#             redis_session_id = f"session_{session_id_int}"
#         logger.error(f"메시지 처리 중 예외 발생: {str(e)}", exc_info=True)
#         
#         # 사용자 메시지의 turn 번호 조회 (저장된 경우)
#         user_turn_for_error = 0
#         try:
#             if session_id_int:
#                 from sqlalchemy import select, func
#                 from app.infrastructure.persistence.models.sessions import PromptMessage
#                 from app.infrastructure.persistence.models.enums import PromptRoleEnum
#                 max_turn_query = select(func.max(PromptMessage.turn)).where(
#                     PromptMessage.session_id == session_id_int,
#                     PromptMessage.role == PromptRoleEnum.USER
#                 )
#                 max_result = await db.execute(max_turn_query)
#                 user_turn_for_error = max_result.scalar_one_or_none() or 0
#         except:
#             pass
#         
#         return ChatResponse(
#             session_id=redis_session_id,
#             turn=user_turn_for_error,
#             ai_message=None,
#             is_submitted=False,
#             error=True,
#             error_message=f"서버 오류: {str(e)}",
#         )


# @router.post(
#     "/submit",
#     response_model=SubmitResponse,
#     responses={
#         500: {"model": ErrorResponse, "description": "서버 에러"}
#     },
#     summary="코드 제출",
#     description="""
#     최종 코드를 제출하고 평가 결과를 받습니다.
#     
#     **처리 과정:**
#     1. Intent Analyzer: 제출 의도 감지 (PASSED_SUBMIT)
#     2. Eval Turn Guard: 모든 턴 평가 완료 대기 & 누락 턴 재평가
#     3. Main Router: 제출 확인 및 평가 플로우 진입
#     4. 평가 노드 실행:
#        - 6a. Holistic Flow Evaluation (Chaining 전략)
#        - 6b. Aggregate Turn Scores (턴별 점수 집계)
#        - 6c. Code Performance (성능 평가)
#        - 6d. Code Correctness (정확성 평가)
#     5. Final Score Aggregation (최종 점수 산출)
#     
#     **제한사항:**
#     - Timeout: 120초 (평가 시간 고려)
#     - 제출은 세션당 1회만 가능
#     """
# )
# async def submit_code(
#     request: SubmitRequest,
#     eval_service: EvalService = Depends(get_eval_service)
# ) -> SubmitResponse:
#     """
#     코드 제출 및 평가
#     
#     [처리 흐름]
#     1. 요청 검증 (session_id, code, lang)
#     2. EvalService.submit_code() 호출
#        - is_submission=True로 설정
#        - human_message="코드를 제출합니다."
#     3. LangGraph 메인 플로우 실행
#        - Intent Analyzer: PASSED_SUBMIT 반환
#        - Eval Turn Guard: 모든 턴 평가 완료 확인
#          * 누락된 턴이 있으면 동기적으로 재평가
#        - Main Router: eval_holistic_flow로 분기
#        - 평가 노드들 순차 실행 (6a → 6b → 6c → 6d → 7)
#     4. 최종 점수를 SubmitResponse로 변환
#     
#     [최종 점수 구성]
#     - prompt_score (25%): 턴별 평균 + Holistic Flow
#     - performance_score (25%): 시간/공간 복잡도
#     - correctness_score (50%): 테스트 케이스 통과율
#     - total_score: 가중 평균
#     - grade: A/B/C/D/F
#     
#     [반환값]
#     SubmitResponse: 최종 점수, 턴별 점수, 제출 ID, 에러 정보 등
#     """
#     import logging
#     logger = logging.getLogger(__name__)
#     
#     try:
#         logger.info(f"코드 제출 수신 - session_id: {request.session_id}")
#         
#         # 2분 타임아웃 설정 (평가 시간 고려)
#         # 평가 노드들이 순차적으로 실행되므로 충분한 시간 필요
#         result = await asyncio.wait_for(
#             eval_service.submit_code(
#                 session_id=request.session_id,
#                 exam_id=request.exam_id,
#                 participant_id=request.participant_id,
#                 spec_id=request.spec_id,
#                 code_content=request.code,
#                 lang=request.lang,
#             ),
#             timeout=120.0  # 2분
#         )
#         
#         # 에러 발생 시
#         if result.get("error"):
#             return SubmitResponse(
#                 session_id=request.session_id,
#                 submission_id=None,
#                 is_submitted=False,
#                 final_scores=None,
#                 turn_scores=None,
#                 error=True,
#                 error_message=result.get("error_message"),
#             )
#         
#         final_scores = result.get("final_scores")
#         
#         # 피드백 정보 추출
#         feedback_data = result.get("feedback", {})
#         feedback = None
#         if feedback_data:
#             from app.presentation.schemas.chat import EvaluationFeedback
#             feedback = EvaluationFeedback(
#                 holistic_flow_analysis=feedback_data.get("holistic_flow_analysis")
#             )
#         
#         # 토큰 사용량을 Core 전달 형식으로 변환
#         from app.domain.langgraph.utils.token_tracking import format_tokens_for_core
#         core_tokens = format_tokens_for_core(
#             chat_tokens=result.get("chat_tokens"),
#             eval_tokens=result.get("eval_tokens")
#         )
#         
#         # 정상 응답
#         return SubmitResponse(
#             session_id=result.get("session_id", request.session_id),
#             submission_id=result.get("submission_id"),
#             is_submitted=True,
#             final_scores=final_scores,
#             turn_scores=result.get("turn_scores"),
#             feedback=feedback,
#             chat_tokens=core_tokens.get("chat_tokens"),
#             eval_tokens=core_tokens.get("eval_tokens"),
#             error=False,
#             error_message=None,
#         )
#     except asyncio.TimeoutError:
#         # 평가 프로세스가 2분 이내에 완료되지 않은 경우
#         # 원인: 
#         # - Eval Turn Guard의 백그라운드 평가 대기 시간 초과
#         # - LLM API 지연 (Holistic Flow, Performance, Correctness 평가)
#         # - Redis 작업 지연
#         logger.error(f"코드 제출 타임아웃 - session_id: {request.session_id}")
#         return SubmitResponse(
#             session_id=request.session_id,
#             submission_id=None,
#             is_submitted=False,
#             final_scores=None,
#             turn_scores=None,
#             error=True,
#             error_message="요청 처리 시간이 초과되었습니다. (2분 타임아웃)",
#         )
#     except Exception as e:
#         # 예상치 못한 모든 예외 처리
#         # 예: 
#         # - turn_scores 누락 (Eval Turn Guard 실패)
#         # - LLM API 에러 (429 Rate Limit, 500 Server Error 등)
#         # - Redis 연결 실패
#         # - 상태 직렬화 오류
#         logger.error(f"코드 제출 중 예외 발생: {str(e)}", exc_info=True)
#         return SubmitResponse(
#             session_id=request.session_id,
#             submission_id=None,
#             is_submitted=False,
#             final_scores=None,
#             turn_scores=None,
#             error=True,
#             error_message=f"서버 오류: {str(e)}",
#         )
# ===== [DEPRECATED] 레거시 API 끝 =====


# ===== [DEPRECATED] WebSocket API - 주석처리됨 (2024-12-07) =====
# RESTful API만 사용 (WebSocket, SSE 미사용)
# ============================================================

# @router.websocket("/ws")
# async def websocket_chat(websocket: WebSocket):
#     """
#     WebSocket 스트리밍 채팅
#     
#     [특징]
#     - Delta 스트리밍 (토큰 단위)
#     - 취소 기능
#     - turnId 전달
#     - LangGraph 사용 (Intent Analyzer, Writer LLM, Eval Turn 포함)
#     
#     [메시지 형식]
#     수신:
#     {
#         "type": "message",
#         "session_id": "session-123",
#         "turn_id": 1,
#         "message": "사용자 메시지",
#         "exam_id": 1,
#         "participant_id": 100,
#         "spec_id": 10
#     }
#     
#     {
#         "type": "cancel",
#         "turn_id": 1
#     }
#     
#     송신:
#     {
#         "type": "delta",
#         "content": "토큰",
#         "turn_id": 1
#     }
#     
#     {
#         "type": "done",
#         "turn_id": 1,
#         "full_content": "전체 응답"
#     }
#     
#     {
#         "type": "error",
#         "turn_id": 1,
#         "error": "에러 메시지"
#     }
#     """
#     await websocket.accept()
#     logger = logging.getLogger(__name__)
#     
#     # 현재 스트리밍 중인 작업 추적
#     active_streams: dict[int, bool] = {}  # turn_id -> is_cancelled
#     
#     try:
#         while True:
#             # 클라이언트 메시지 수신
#             data = await websocket.receive_json()
#             msg_type = data.get("type")
#             
#             if msg_type == "message":
#                 session_id = data.get("session_id")
#                 turn_id = data.get("turn_id")
#                 message = data.get("message")
#                 exam_id = data.get("exam_id")
#                 participant_id = data.get("participant_id")
#                 spec_id = data.get("spec_id")
#                 
#                 if not all([session_id, turn_id, message]):
#                     await websocket.send_json({
#                         "type": "error",
#                         "turn_id": turn_id,
#                         "error": "필수 필드 누락: session_id, turn_id, message"
#                     })
#                     continue
#                 
#                 # 취소 플래그 초기화
#                 active_streams[turn_id] = False
#                 
#                 try:
#                     # EvalService 인스턴스 생성
#                     eval_service = EvalService(redis_client)
#                     
#                     # LangGraph 스트리밍 실행
#                     full_content = ""
#                     async for chunk in eval_service.process_message_stream(
#                         session_id=session_id,
#                         exam_id=exam_id,
#                         participant_id=participant_id,
#                         spec_id=spec_id,
#                         human_message=message,
#                     ):
#                         # 취소 확인
#                         if active_streams.get(turn_id, False):
#                             await websocket.send_json({
#                                 "type": "cancelled",
#                                 "turn_id": turn_id
#                             })
#                             break
#                         
#                         # Delta 전송
#                         if chunk:
#                             full_content += chunk
#                             await websocket.send_json({
#                                 "type": "delta",
#                                 "content": chunk,
#                                 "turn_id": turn_id
#                             })
#                     
#                     # 완료 신호 (토큰 사용량 포함)
#                     if not active_streams.get(turn_id, False):
#                         # 최종 결과에서 토큰 사용량 추출
#                         final_state = await eval_service.get_session_state(session_id)
#                         token_summary = {}
#                         if final_state:
#                             from app.domain.langgraph.utils.token_tracking import get_token_summary
#                             token_summary = get_token_summary(final_state)
#                         
#                         await websocket.send_json({
#                             "type": "done",
#                             "turn_id": turn_id,
#                             "full_content": full_content,
#                             "chat_tokens": token_summary.get("chat_tokens", {}),
#                             "eval_tokens": token_summary.get("eval_tokens", {}),
#                         })
#                     
#                     # 스트림 제거
#                     active_streams.pop(turn_id, None)
#                     
#                 except Exception as e:
#                     logger.error(f"WebSocket 스트리밍 오류: {str(e)}", exc_info=True)
#                     await websocket.send_json({
#                         "type": "error",
#                         "turn_id": turn_id,
#                         "error": f"스트리밍 오류: {str(e)}"
#                     })
#                     active_streams.pop(turn_id, None)
#             
#             elif msg_type == "cancel":
#                 # 취소 요청
#                 turn_id = data.get("turn_id")
#                 if turn_id:
#                     active_streams[turn_id] = True
#                     await websocket.send_json({
#                         "type": "cancelled",
#                         "turn_id": turn_id
#                     })
#             
#             else:
#                 await websocket.send_json({
#                     "type": "error",
#                     "turn_id": None,
#                     "error": f"알 수 없는 메시지 타입: {msg_type}"
#                 })
#                 
#     except WebSocketDisconnect:
#         logger.info("WebSocket 연결 종료")
#     except Exception as e:
#         logger.error(f"WebSocket 오류: {str(e)}", exc_info=True)
#     finally:
#         # 정리
#         active_streams.clear()
# ===== [DEPRECATED] WebSocket API 끝 =====


@router.get(
    "/problem-info",
    summary="문제 정보 조회",
    description="spec_id로 문제 정보를 DB에서 조회합니다."
)
async def get_problem_info(
    spec_id: int = Query(..., description="문제 스펙 ID"),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """문제 정보 조회 (DB에서)"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from app.domain.langgraph.utils.problem_info import get_problem_info as get_problem_info_async
        problem_info = await get_problem_info_async(spec_id, db)
        return {
            "spec_id": spec_id,
            "problem_info": problem_info,
            "error": False,
        }
    except Exception as e:
        logger.error(f"문제 정보 조회 오류: {str(e)}", exc_info=True)
        # Fallback: 동기 버전 사용
        try:
            problem_info = get_problem_info_sync(spec_id)
            return {
                "spec_id": spec_id,
                "problem_info": problem_info,
                "error": False,
            }
        except Exception as e2:
            logger.error(f"Fallback 문제 정보 조회도 실패: {str(e2)}", exc_info=True)
            return {
                "spec_id": spec_id,
                "problem_info": None,
                "error": True,
                "error_message": str(e),
            }


@router.get(
    "/turn-logs",
    summary="턴 로그 조회",
    description="""
    세션의 모든 턴 로그를 조회합니다.
    
    **반환 데이터:**
    - 각 턴별 평가 결과
    - 점수, 의도, 평가 항목 등
    """
)
async def get_turn_logs(
    session_id: str = Query(..., description="세션 ID")
) -> Dict[str, Any]:
    """
    턴 로그 조회
    
    [역할]
    - Redis에서 세션의 모든 턴 로그 조회
    - 백그라운드 평가 결과 확인용
    
    Args:
        session_id: 세션 ID
    
    Returns:
        {
            "session_id": "...",
            "turn_logs": {
                "1": {...},
                "2": {...}
            },
            "error": false
        }
    """
    try:
        turn_logs = await redis_client.get_all_turn_logs(session_id)
        
        return {
            "session_id": session_id,
            "turn_logs": turn_logs,
            "error": False,
        }
    except Exception as e:
        logger.error(f"턴 로그 조회 오류: {str(e)}", exc_info=True)
        return {
            "session_id": session_id,
            "turn_logs": {},
            "error": True,
            "error_message": str(e),
        }


@router.get(
    "/tokens",
    summary="토큰 사용량 조회",
    description="""
    세션의 토큰 사용량을 조회합니다.
    
    **반환 데이터:**
    - chat_tokens: 채팅 검사 토큰 (Intent Analyzer, Writer LLM)
    - eval_tokens: 평가 토큰 (Turn Evaluator, Holistic Evaluator)
    - total_tokens: 전체 토큰 합계
    
    **Core 백엔드 전달 형식:**
    - prompt_tokens: 프롬프트 토큰 수
    - completion_tokens: 컴플리션 토큰 수
    - total_tokens: 전체 토큰 수
    """
)
async def get_token_usage(
    session_id: str = Query(..., description="세션 ID"),
    eval_service: EvalService = Depends(get_eval_service)
) -> Dict[str, Any]:
    """
    토큰 사용량 조회 (Core 백엔드 전달용)
    
    [역할]
    - Redis에서 세션의 토큰 사용량 조회
    - chat_tokens와 eval_tokens를 분리하여 반환
    - Core 백엔드로 전달할 형식으로 변환
    
    Args:
        session_id: 세션 ID
    
    Returns:
        {
            "session_id": "...",
            "chat_tokens": {
                "prompt_tokens": int,
                "completion_tokens": int,
                "total_tokens": int
            },
            "eval_tokens": {
                "prompt_tokens": int,
                "completion_tokens": int,
                "total_tokens": int
            },
            "total_tokens": {
                "prompt_tokens": int,  # chat + eval 합계
                "completion_tokens": int,  # chat + eval 합계
                "total_tokens": int  # chat + eval 합계
            },
            "error": false
        }
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # 세션 상태 조회
        state = await eval_service.get_session_state(session_id)
        
        if not state:
            return {
                "session_id": session_id,
                "chat_tokens": None,
                "eval_tokens": None,
                "total_tokens": None,
                "error": True,
                "error_message": "세션을 찾을 수 없습니다.",
            }
        
        # 토큰 사용량 추출
        from app.domain.langgraph.utils.token_tracking import get_token_summary, format_tokens_for_core
        
        token_summary = get_token_summary(state)
        chat_tokens = token_summary.get("chat_tokens")
        eval_tokens = token_summary.get("eval_tokens")
        
        # Core 전달 형식으로 변환
        core_format = format_tokens_for_core(chat_tokens, eval_tokens)
        
        logger.info(f"[Token Usage API] 조회 완료 - session_id: {session_id}, chat: {chat_tokens}, eval: {eval_tokens}")
        
        return {
            "session_id": session_id,
            **core_format,  # chat_tokens, eval_tokens, total_tokens 포함
            "error": False,
        }
    except Exception as e:
        logger.error(f"토큰 사용량 조회 오류: {str(e)}", exc_info=True)
        return {
            "session_id": session_id,
            "chat_tokens": None,
            "eval_tokens": None,
            "total_tokens": None,
            "error": True,
            "error_message": str(e),
        }


logger = logging.getLogger(__name__)


@router.post(
    "/save-message",
    response_model=SaveChatMessageResponse,
    summary="메시지 저장 (Spring Boot용)",
    description="""
    Spring Boot에서 메시지를 받아서 PostgreSQL과 Redis에 저장합니다.
    
    **저장 순서:**
    1. PostgreSQL에 먼저 저장 (데이터 무결성)
    2. Redis 체크포인트 업데이트
    
    **호출 시점:**
    - Spring Boot에서 SaveChatMessageRequest 받을 때
    - 매 메시지마다 호출 (USER, ASSISTANT 모두)
    """
)
async def save_chat_message(
    request: SaveChatMessageRequest,
    db: AsyncSession = Depends(get_db)
) -> SaveChatMessageResponse:
    """
    메시지 저장 (Spring Boot용)
    
    [처리 흐름]
    1. exam_id, participant_id로 세션 조회/생성
    2. PostgreSQL에 메시지 저장
    3. Redis 체크포인트 업데이트
    
    [저장 순서]
    - PostgreSQL 먼저 저장 (데이터 무결성)
    - 성공하면 Redis 업데이트
    
    Args:
        request: SaveChatMessageRequest (examId, participantId, turn, role, content, ...)
        db: PostgreSQL 세션
    
    Returns:
        SaveChatMessageResponse (session_id, message_id, success)
    """
    try:
        # meta 파싱 (JSON 문자열 → dict)
        meta_dict = None
        if request.meta:
            try:
                meta_dict = json.loads(request.meta)
            except json.JSONDecodeError:
                logger.warning(f"[SaveMessage] meta JSON 파싱 실패: {request.meta}")
                meta_dict = {"raw": request.meta}
        
        # MessageStorageService 생성
        storage_service = MessageStorageService(db, redis_client)
        
        # 메시지 저장 (PostgreSQL 먼저 → Redis 업데이트)
        result = await storage_service.save_message(
            exam_id=request.examId,
            participant_id=request.participantId,
            turn=request.turn,
            role=request.role,
            content=request.content,
            token_count=request.tokenCount,
            meta=meta_dict
        )
        
        logger.info(
            f"[SaveMessage] 저장 완료 - "
            f"session_id: {result['session_id']}, message_id: {result['message_id']}, "
            f"turn: {request.turn}, role: {request.role}"
        )
        
        return SaveChatMessageResponse(
            session_id=result["session_id"],
            message_id=result["message_id"],
            success=True,
            error_message=None
        )
        
    except ValueError as e:
        # exam_participants 없음 등 비즈니스 로직 오류
        logger.error(f"[SaveMessage] 저장 실패: {str(e)}")
        return SaveChatMessageResponse(
            session_id=0,
            message_id=0,
            success=False,
            error_message=str(e)
        )
    except Exception as e:
        # 기타 오류
        logger.error(f"[SaveMessage] 저장 오류: {str(e)}", exc_info=True)
        return SaveChatMessageResponse(
            session_id=0,
            message_id=0,
            success=False,
            error_message=f"메시지 저장 실패: {str(e)}"
        )


