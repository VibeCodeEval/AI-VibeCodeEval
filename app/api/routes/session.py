"""
세션 API 라우터
"""
from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.session import SessionState, SessionScores, ConversationHistory, Message
from app.schemas.common import ErrorResponse
from app.services.eval_service import EvalService
from app.db.redis_client import redis_client


router = APIRouter(prefix="/session", tags=["Session"])


async def get_eval_service() -> EvalService:
    """EvalService 의존성 주입"""
    return EvalService(redis_client)


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


