"""
세션 API 라우터
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.presentation.schemas.session import (
    SessionState, SessionScores, ConversationHistory, Message,
    StartSessionRequest, StartSessionResponse, SendMessageRequest,
    SubmitCodeRequest
)
from app.presentation.schemas.chat import (
    SendMessageResponse, MessageInfo, SessionInfo, SubmitResponse
)
from app.presentation.schemas.common import ErrorResponse
from app.application.services.eval_service import EvalService
from app.infrastructure.cache.redis_client import redis_client
from app.infrastructure.persistence.session import get_db
from app.infrastructure.repositories.session_repository import SessionRepository
from app.application.services.message_storage_service import MessageStorageService


router = APIRouter(prefix="/session", tags=["Session"])
logger = logging.getLogger(__name__)


async def get_eval_service() -> EvalService:
    """EvalService 의존성 주입"""
    return EvalService(redis_client)


@router.post(
    "/start",
    response_model=StartSessionResponse,
    summary="응시자 채팅 세션 시작",
    description="""
    응시자의 채팅 세션을 시작합니다.
    
    **처리 과정:**
    1. exam_participants 조회 (참가자 확인)
    2. 진행 중인 세션 조회 (ended_at IS NULL)
    3. 없으면 새 세션 생성
    4. 세션 정보 반환
    
    **참고:**
    - 프롬프트 세션은 이 API에서 생성됩니다.
    - 세션이 이미 존재하면 기존 세션을 반환합니다.
    """
)
async def start_session(
    request: StartSessionRequest,
    db: AsyncSession = Depends(get_db)
) -> StartSessionResponse:
    """응시자 채팅 세션 시작"""
    try:
        session_repo = SessionRepository(db)
        
        # 세션 조회 또는 생성
        session = await session_repo.get_or_create_session(
            exam_id=request.examId,
            participant_id=request.participantId
        )
        
        # 세션 생성 후 커밋 (새로 생성된 경우)
        await db.commit()
        
        # spec_id 확인 (요청의 specId와 일치하는지 확인)
        if session.spec_id != request.specId:
            logger.warning(
                f"[StartSession] spec_id 불일치 - "
                f"session.spec_id: {session.spec_id}, request.specId: {request.specId}"
            )
            # spec_id 업데이트 (요청의 specId로)
            session.spec_id = request.specId
            await db.commit()
        
        return StartSessionResponse(
            id=session.id,
            examId=session.exam_id,
            participantId=session.participant_id,
            specId=session.spec_id,
            startedAt=session.started_at.isoformat() if session.started_at else None,
            endedAt=session.ended_at.isoformat() if session.ended_at else None,
            totalTokens=session.total_tokens or 0
        )
        
    except ValueError as e:
        logger.error(f"[StartSession] 세션 시작 실패: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": True,
                "error_code": "SESSION_START_FAILED",
                "error_message": str(e)
            }
        )
    except Exception as e:
        logger.error(f"[StartSession] 세션 시작 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": True,
                "error_code": "INTERNAL_ERROR",
                "error_message": f"세션 시작 중 오류가 발생했습니다: {str(e)}"
            }
        )


@router.get(
    "/{session_id}/state",
    response_model=SessionState,
    responses={
        404: {"model": ErrorResponse, "description": "세션을 찾을 수 없음"}
    },
    summary="세션 상태 조회",
    description="세션의 현재 상태를 조회합니다."
)
async def get_session_state(
    session_id: str,
    eval_service: EvalService = Depends(get_eval_service)
) -> SessionState:
    """세션 상태 조회"""
    state = await eval_service.get_session_state(session_id)
    
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": True,
                "error_code": "SESSION_NOT_FOUND",
                "error_message": "세션을 찾을 수 없습니다.",
                "details": {"session_id": session_id}
            }
        )
    
    return SessionState(
        session_id=state.get("session_id", session_id),
        exam_id=state.get("exam_id", 0),
        participant_id=state.get("participant_id", 0),
        spec_id=state.get("spec_id", 0),
        current_turn=state.get("current_turn", 0),
        is_submitted=state.get("is_submitted", False),
        memory_summary=state.get("memory_summary"),
        created_at=state.get("created_at", ""),
        updated_at=state.get("updated_at", ""),
    )


@router.get(
    "/{session_id}/scores",
    response_model=SessionScores,
    responses={
        404: {"model": ErrorResponse, "description": "세션을 찾을 수 없음"}
    },
    summary="세션 점수 조회",
    description="세션의 평가 점수를 조회합니다."
)
async def get_session_scores(
    session_id: str,
    eval_service: EvalService = Depends(get_eval_service)
) -> SessionScores:
    """세션 점수 조회"""
    scores = await eval_service.get_session_scores(session_id)
    
    if not scores:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": True,
                "error_code": "SCORES_NOT_FOUND",
                "error_message": "점수 정보를 찾을 수 없습니다.",
                "details": {"session_id": session_id}
            }
        )
    
    return SessionScores(
        session_id=session_id,
        turns=scores.get("turns", {}),
        final=scores.get("final"),
        updated_at=scores.get("updated_at"),
        completed_at=scores.get("completed_at"),
    )


@router.get(
    "/{session_id}/history",
    response_model=ConversationHistory,
    responses={
        404: {"model": ErrorResponse, "description": "세션을 찾을 수 없음"}
    },
    summary="대화 히스토리 조회",
    description="세션의 대화 히스토리를 조회합니다."
)
async def get_conversation_history(
    session_id: str,
    eval_service: EvalService = Depends(get_eval_service)
) -> ConversationHistory:
    """대화 히스토리 조회"""
    history = await eval_service.get_conversation_history(session_id)
    
    if history is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": True,
                "error_code": "SESSION_NOT_FOUND",
                "error_message": "세션을 찾을 수 없습니다.",
                "details": {"session_id": session_id}
            }
        )
    
    messages = [Message(role=m["role"], content=m["content"]) for m in history]
    
    return ConversationHistory(
        session_id=session_id,
        messages=messages,
        total_messages=len(messages),
    )


@router.post(
    "/{session_id}/messages",
    response_model=SendMessageResponse,
    summary="사용자 메시지 전송 & AI 응답",
    description="""
    사용자 메시지를 전송하고 AI 응답을 받습니다.
    
    **처리 과정:**
    1. 사용자 메시지 저장 (PostgreSQL)
    2. LangGraph 실행 (Intent Analyzer → Writer LLM)
    3. AI 응답 저장 (PostgreSQL)
    4. 세션 토큰 업데이트
    
    **응답 형식:**
    - userMessage: 저장된 사용자 메시지 정보
    - aiMessage: 저장된 AI 응답 메시지 정보
    - session: 업데이트된 세션 정보
    """
)
async def send_message(
    session_id: int,
    request: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
    eval_service: EvalService = Depends(get_eval_service)
) -> SendMessageResponse:
    """사용자 메시지 전송 & AI 응답"""
    import asyncio
    import json
    
    try:
        # 세션 조회
        session_repo = SessionRepository(db)
        session = await session_repo.get_session_by_id(session_id)
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": True,
                    "error_code": "SESSION_NOT_FOUND",
                    "error_message": f"세션을 찾을 수 없습니다. (session_id: {session_id})"
                }
            )
        
        # MessageStorageService 생성
        storage_service = MessageStorageService(db, redis_client)
        
        # 1. 사용자 메시지 저장
        user_msg_result = await storage_service.save_message(
            exam_id=session.exam_id,
            participant_id=session.participant_id,
            turn=None,  # DB에서 자동 계산
            role=request.role.lower(),
            content=request.content
        )
        await db.commit()
        
        user_message = MessageInfo(
            id=user_msg_result["message_id"],
            turn=user_msg_result["turn"],
            role=request.role.upper(),
            content=request.content,
            tokenCount=None  # 사용자 메시지는 토큰 카운트 없음
        )
        
        # 2. LangGraph 실행 (AI 응답 생성)
        redis_session_id = f"session_{session_id}"
        
        result = await asyncio.wait_for(
            eval_service.process_message(
                session_id=redis_session_id,
                exam_id=session.exam_id,
                participant_id=session.participant_id,
                spec_id=session.spec_id,
                human_message=request.content,
            ),
            timeout=120.0  # 2분 (LLM 응답 시간 고려)
        )
        
        ai_message = None
        if result.get("ai_message") and not result.get("error"):
            # 3. AI 응답 저장
            chat_tokens = result.get("chat_tokens", {})
            total_tokens = chat_tokens.get("total_tokens", 0) if isinstance(chat_tokens, dict) else 0
            
            ai_msg_result = await storage_service.save_message(
                exam_id=session.exam_id,
                participant_id=session.participant_id,
                turn=None,  # DB에서 자동 계산
                role="assistant",
                content=result.get("ai_message"),
                token_count=total_tokens
            )
            await db.commit()
            
            ai_message = MessageInfo(
                id=ai_msg_result["message_id"],
                turn=ai_msg_result["turn"],
                role="AI",
                content=result.get("ai_message"),
                tokenCount=total_tokens
            )
        
        # 4. 세션 정보 업데이트 (토큰 합계)
        # 세션을 다시 조회하여 최신 정보 가져오기
        await db.refresh(session)
        updated_session = await session_repo.get_session_by_id(session_id)
        
        if not updated_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": True,
                    "error_code": "SESSION_NOT_FOUND",
                    "error_message": f"세션을 찾을 수 없습니다. (session_id: {session_id})"
                }
            )
        
        session_info = SessionInfo(
            id=updated_session.id,
            totalTokens=updated_session.total_tokens or 0
        )
        
        return SendMessageResponse(
            userMessage=user_message,
            aiMessage=ai_message,
            session=session_info
        )
        
    except asyncio.TimeoutError:
        logger.error(f"[SendMessage] 타임아웃 - session_id: {session_id}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "error": True,
                "error_code": "TIMEOUT",
                "error_message": "요청 처리 시간이 초과되었습니다. (2분 타임아웃) - LLM API 응답 지연 또는 Quota 제한 가능"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SendMessage] 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": True,
                "error_code": "INTERNAL_ERROR",
                "error_message": f"메시지 전송 중 오류가 발생했습니다: {str(e)}"
            }
        )


@router.post(
    "/{session_id}/submit",
    response_model=SubmitResponse,
    summary="응시자 코드 제출",
    description="""
    응시자가 코드를 제출하고 평가 결과를 받습니다.
    
    **처리 과정:**
    1. 세션 정보 조회 (exam_id, participant_id, spec_id)
    2. EvalService.submit_code() 호출
       - Intent Analyzer: 제출 의도 감지 (PASSED_SUBMIT)
       - Eval Turn Guard: 모든 턴 평가 완료 대기 & 누락 턴 재평가
       - Main Router: 제출 확인 및 평가 플로우 진입
       - 평가 노드 실행:
         * 6a. Holistic Flow Evaluation (Chaining 전략)
         * 6b. Aggregate Turn Scores (턴별 점수 집계)
         * 6c. Code Performance (성능 평가)
         * 6d. Code Correctness (정확성 평가)
       * 7. Final Score Aggregation (최종 점수 산출)
    3. 최종 점수 반환
    
    **제한사항:**
    - Timeout: 300초 (5분, 평가 시간 고려)
    - 제출은 세션당 1회만 가능
    """
)
async def submit_code(
    session_id: int,
    request: SubmitCodeRequest,
    db: AsyncSession = Depends(get_db),
    eval_service: EvalService = Depends(get_eval_service)
) -> SubmitResponse:
    """응시자 코드 제출"""
    import asyncio
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # 1. 세션 정보 조회
        session_repo = SessionRepository(db)
        session = await session_repo.get_session_by_id(session_id)
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": True,
                    "error_code": "SESSION_NOT_FOUND",
                    "error_message": f"세션을 찾을 수 없습니다. (session_id: {session_id})"
                }
            )
        
        # 2. Redis session_id 형식으로 변환
        redis_session_id = f"session_{session_id}"
        
        logger.info(
            f"[SubmitCode] 코드 제출 수신 - "
            f"session_id: {session_id}, exam_id: {session.exam_id}, "
            f"participant_id: {session.participant_id}, spec_id: {session.spec_id}"
        )
        
        # 3. EvalService.submit_code() 호출 (5분 타임아웃)
        result = await asyncio.wait_for(
            eval_service.submit_code(
                session_id=redis_session_id,
                exam_id=session.exam_id,
                participant_id=session.participant_id,
                spec_id=session.spec_id,
                code_content=request.code,
                lang=request.lang,
            ),
            timeout=300.0  # 5분
        )
        
        # 4. 에러 발생 시
        if result.get("error"):
            return SubmitResponse(
                session_id=redis_session_id,
                submission=None,
                is_submitted=False,
                final_scores=None,
                turn_scores=None,
                error=True,
                error_message=result.get("error_message"),
            )
        
        # 5. Submission 정보 조회 (submission_id가 있으면)
        submission_info = None
        submission_id = result.get("submission_id")
        if submission_id:
            try:
                from app.infrastructure.repositories.submission_repository import SubmissionRepository
                submission_repo = SubmissionRepository(db)
                submission = await submission_repo.get_submission_by_id(submission_id)
                
                if submission:
                    from app.presentation.schemas.chat import SubmissionInfo
                    submission_info = SubmissionInfo(
                        id=submission.id,
                        examId=submission.exam_id,
                        participantId=submission.participant_id,
                        specId=submission.spec_id,
                        lang=submission.lang,
                        status=submission.status.value if submission.status else "UNKNOWN",
                        codeSha256=submission.code_sha256,
                        codeBytes=submission.code_bytes,
                        codeLoc=submission.code_loc,
                        createdAt=submission.created_at.isoformat() if submission.created_at else ""
                    )
            except Exception as e:
                logger.warning(f"[SubmitCode] Submission 정보 조회 실패 - submission_id: {submission_id}, error: {str(e)}")
        
        # 6. 피드백 정보 추출
        feedback_data = result.get("feedback", {})
        from app.presentation.schemas.chat import EvaluationFeedback
        feedback = None
        if feedback_data:
            feedback = EvaluationFeedback(
                holistic_flow_analysis=feedback_data.get("holistic_flow_analysis")
            )
        
        # 7. 토큰 사용량을 Core 전달 형식으로 변환
        from app.domain.langgraph.utils.token_tracking import format_tokens_for_core
        core_tokens = format_tokens_for_core(
            chat_tokens=result.get("chat_tokens"),
            eval_tokens=result.get("eval_tokens")
        )
        
        # 8. 정상 응답
        return SubmitResponse(
            session_id=redis_session_id,
            submission=submission_info,
            is_submitted=True,
            final_scores=result.get("final_scores"),
            turn_scores=result.get("turn_scores"),
            feedback=feedback,
            chat_tokens=core_tokens.get("chat_tokens"),
            eval_tokens=core_tokens.get("eval_tokens"),
            error=False,
            error_message=None,
        )
        
    except asyncio.TimeoutError:
        logger.error(f"[SubmitCode] 코드 제출 타임아웃 - session_id: {session_id}")
        return SubmitResponse(
            session_id=f"session_{session_id}",
            submission=None,
            is_submitted=False,
            final_scores=None,
            turn_scores=None,
            error=True,
            error_message="요청 처리 시간이 초과되었습니다. (5분 타임아웃)",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SubmitCode] 코드 제출 중 예외 발생: {str(e)}", exc_info=True)
        return SubmitResponse(
            session_id=f"session_{session_id}",
            submission=None,
            is_submitted=False,
            final_scores=None,
            turn_scores=None,
            error=True,
            error_message=f"코드 제출 중 오류가 발생했습니다: {str(e)}",
        )


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="세션 삭제",
    description="세션과 관련된 모든 상태를 삭제합니다."
)
async def delete_session(
    session_id: str,
    eval_service: EvalService = Depends(get_eval_service)
):
    """세션 삭제"""
    await eval_service.clear_session(session_id)
    return None


