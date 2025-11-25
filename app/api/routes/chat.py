"""
채팅 API 라우터
"""
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.chat import ChatRequest, ChatResponse, SubmitRequest, SubmitResponse
from app.schemas.common import ErrorResponse
from app.services.eval_service import EvalService
from app.db.redis_client import redis_client, get_redis


router = APIRouter(prefix="/chat", tags=["Chat"])


async def get_eval_service() -> EvalService:
    """EvalService 의존성 주입"""
    return EvalService(redis_client)


@router.post(
    "/message",
    response_model=ChatResponse,
    responses={
        500: {"model": ErrorResponse, "description": "서버 에러"}
    },
    summary="메시지 전송",
    description="AI 어시스턴트에게 메시지를 전송하고 응답을 받습니다."
)
async def send_message(
    request: ChatRequest,
    eval_service: EvalService = Depends(get_eval_service)
) -> ChatResponse:
    """메시지 전송 및 AI 응답 받기"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"메시지 수신 - session_id: {request.session_id}, message: {request.message[:50]}...")
        
        # 1분 타임아웃 설정
        result = await asyncio.wait_for(
            eval_service.process_message(
                session_id=request.session_id,
                exam_id=request.exam_id,
                participant_id=request.participant_id,
                spec_id=request.spec_id,
                human_message=request.message,
            ),
            timeout=60.0  # 1분
        )
        
        logger.info(f"처리 완료 - session_id: {request.session_id}, has_ai_message: {bool(result.get('ai_message'))}, error: {result.get('error')}")
        
        if result.get("error"):
            return ChatResponse(
                session_id=request.session_id,
                turn=result.get("turn", 0),
                ai_message=None,
                is_submitted=False,
                error=True,
                error_message=result.get("error_message"),
            )
        
        return ChatResponse(
            session_id=result.get("session_id", request.session_id),
            turn=result.get("turn", 0),
            ai_message=result.get("ai_message"),
            is_submitted=result.get("is_submitted", False),
            error=False,
            error_message=None,
        )
    except asyncio.TimeoutError:
        logger.error(f"메시지 처리 타임아웃 - session_id: {request.session_id}")
        return ChatResponse(
            session_id=request.session_id,
            turn=0,
            ai_message=None,
            is_submitted=False,
            error=True,
            error_message="요청 처리 시간이 초과되었습니다. (1분 타임아웃)",
        )
    except Exception as e:
        logger.error(f"메시지 처리 중 예외 발생: {str(e)}", exc_info=True)
        return ChatResponse(
            session_id=request.session_id,
            turn=0,
            ai_message=None,
            is_submitted=False,
            error=True,
            error_message=f"서버 오류: {str(e)}",
        )


@router.post(
    "/submit",
    response_model=SubmitResponse,
    responses={
        500: {"model": ErrorResponse, "description": "서버 에러"}
    },
    summary="코드 제출",
    description="최종 코드를 제출하고 평가 결과를 받습니다."
)
async def submit_code(
    request: SubmitRequest,
    eval_service: EvalService = Depends(get_eval_service)
) -> SubmitResponse:
    """코드 제출 및 평가"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"코드 제출 수신 - session_id: {request.session_id}")
        
        # 1분 타임아웃 설정
        result = await asyncio.wait_for(
            eval_service.submit_code(
                session_id=request.session_id,
                exam_id=request.exam_id,
                participant_id=request.participant_id,
                spec_id=request.spec_id,
                code_content=request.code,
                lang=request.lang,
            ),
            timeout=60.0  # 1분
        )
        
        if result.get("error"):
            return SubmitResponse(
                session_id=request.session_id,
                submission_id=None,
                is_submitted=False,
                final_scores=None,
                turn_scores=None,
                error=True,
                error_message=result.get("error_message"),
            )
        
        final_scores = result.get("final_scores")
        
        return SubmitResponse(
            session_id=result.get("session_id", request.session_id),
            submission_id=result.get("submission_id"),
            is_submitted=True,
            final_scores=final_scores,
            turn_scores=result.get("turn_scores"),
            error=False,
            error_message=None,
        )
    except asyncio.TimeoutError:
        logger.error(f"코드 제출 타임아웃 - session_id: {request.session_id}")
        return SubmitResponse(
            session_id=request.session_id,
            submission_id=None,
            is_submitted=False,
            final_scores=None,
            turn_scores=None,
            error=True,
            error_message="요청 처리 시간이 초과되었습니다. (1분 타임아웃)",
        )
    except Exception as e:
        logger.error(f"코드 제출 중 예외 발생: {str(e)}", exc_info=True)
        return SubmitResponse(
            session_id=request.session_id,
            submission_id=None,
            is_submitted=False,
            final_scores=None,
            turn_scores=None,
            error=True,
            error_message=f"서버 오류: {str(e)}",
        )


