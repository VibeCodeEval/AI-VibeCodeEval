"""
DB 조회용 API 라우터 (백엔드용)

[목적]
- PostgreSQL에 저장된 데이터를 조회하는 API
- 백엔드(Spring Boot)에서 사용할 수 있는 Endpoint 제공
- 세션, 메시지, 평가, 제출, 점수 정보 조회

[주요 엔드포인트]
1. GET /api/db/sessions/{session_id} - 세션 정보 조회
2. GET /api/db/sessions/{session_id}/messages - 메시지 조회
3. GET /api/db/sessions/{session_id}/evaluations - 평가 결과 조회
4. GET /api/db/submissions/{submission_id} - 제출 정보 조회
5. GET /api/db/submissions/{submission_id}/score - 점수 조회
6. GET /api/db/exams/{exam_id}/participants/{participant_id}/sessions - 참가자의 모든 세션 조회
7. GET /api/db/exams/{exam_id}/participants/{participant_id}/submissions - 참가자의 모든 제출 조회
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.session import get_db_context
from app.infrastructure.repositories.session_repository import \
    SessionRepository
from app.infrastructure.repositories.submission_repository import \
    SubmissionRepository
from app.presentation.schemas.common import ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/db", tags=["Database"])


@router.get(
    "/sessions/{session_id}",
    summary="세션 정보 조회",
    description="PostgreSQL에서 세션 정보를 조회합니다.",
)
async def get_session_info(session_id: int, db: AsyncSession = Depends(get_db_context)):
    """세션 정보 조회"""
    try:
        session_repo = SessionRepository(db)
        session = await session_repo.get_session_by_id(session_id)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": True,
                    "error_code": "SESSION_NOT_FOUND",
                    "error_message": f"세션을 찾을 수 없습니다. (session_id: {session_id})",
                },
            )

        return {
            "error": False,
            "session": {
                "id": session.id,
                "exam_id": session.exam_id,
                "participant_id": session.participant_id,
                "spec_id": session.spec_id,
                "started_at": (
                    session.started_at.isoformat() if session.started_at else None
                ),
                "ended_at": session.ended_at.isoformat() if session.ended_at else None,
                "total_tokens": session.total_tokens,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"세션 정보 조회 실패: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": True,
                "error_code": "INTERNAL_ERROR",
                "error_message": f"세션 정보 조회 중 오류가 발생했습니다: {str(e)}",
            },
        )


@router.get(
    "/sessions/{session_id}/messages",
    summary="세션 메시지 조회",
    description="PostgreSQL에서 세션의 모든 메시지를 조회합니다.",
)
async def get_session_messages(
    session_id: int, db: AsyncSession = Depends(get_db_context)
):
    """세션 메시지 조회"""
    try:
        session_repo = SessionRepository(db)
        messages = await session_repo.get_messages_by_session(session_id)

        return {
            "error": False,
            "session_id": session_id,
            "messages": [
                {
                    "id": msg.id,
                    "turn": msg.turn,
                    "role": msg.role.value if msg.role else None,
                    "content": msg.content,
                    "token_count": msg.token_count,
                    "meta": msg.meta,
                    "created_at": (
                        msg.created_at.isoformat() if msg.created_at else None
                    ),
                }
                for msg in messages
            ],
            "total_messages": len(messages),
        }
    except Exception as e:
        logger.error(f"세션 메시지 조회 실패: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": True,
                "error_code": "INTERNAL_ERROR",
                "error_message": f"세션 메시지 조회 중 오류가 발생했습니다: {str(e)}",
            },
        )


@router.get(
    "/sessions/{session_id}/evaluations",
    summary="세션 평가 결과 조회",
    description="PostgreSQL에서 세션의 모든 평가 결과를 조회합니다.",
)
async def get_session_evaluations(
    session_id: int, db: AsyncSession = Depends(get_db_context)
):
    """세션 평가 결과 조회"""
    try:
        from sqlalchemy import select

        from app.infrastructure.persistence.models.sessions import \
            PromptEvaluation
        from app.infrastructure.repositories.session_repository import \
            SessionRepository

        session_repo = SessionRepository(db)

        # 세션 존재 확인
        session = await session_repo.get_session_by_id(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": True,
                    "error_code": "SESSION_NOT_FOUND",
                    "error_message": f"세션을 찾을 수 없습니다. (session_id: {session_id})",
                },
            )

        # 평가 결과 조회
        query = (
            select(PromptEvaluation)
            .where(PromptEvaluation.session_id == session_id)
            .order_by(PromptEvaluation.turn.nulls_last(), PromptEvaluation.created_at)
        )

        result = await db.execute(query)
        evaluations = list(result.scalars().all())

        return {
            "error": False,
            "session_id": session_id,
            "evaluations": [
                {
                    "id": eval.id,
                    "turn": eval.turn,
                    "evaluation_type": eval.evaluation_type,
                    "node_name": eval.node_name,
                    "score": float(eval.score) if eval.score else None,
                    "analysis": eval.analysis,
                    "details": eval.details,
                    "created_at": (
                        eval.created_at.isoformat() if eval.created_at else None
                    ),
                }
                for eval in evaluations
            ],
            "total_evaluations": len(evaluations),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"세션 평가 결과 조회 실패: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": True,
                "error_code": "INTERNAL_ERROR",
                "error_message": f"세션 평가 결과 조회 중 오류가 발생했습니다: {str(e)}",
            },
        )


@router.get(
    "/submissions/{submission_id}",
    summary="제출 정보 조회",
    description="PostgreSQL에서 제출 정보를 조회합니다.",
)
async def get_submission_info(
    submission_id: int,
    include_runs: bool = Query(False, description="실행 결과 포함 여부"),
    include_score: bool = Query(True, description="점수 정보 포함 여부"),
    db: AsyncSession = Depends(get_db_context),
):
    """제출 정보 조회"""
    try:
        submission_repo = SubmissionRepository(db)
        submission = await submission_repo.get_submission_by_id(
            submission_id, include_runs=include_runs, include_score=include_score
        )

        if not submission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": True,
                    "error_code": "SUBMISSION_NOT_FOUND",
                    "error_message": f"제출 정보를 찾을 수 없습니다. (submission_id: {submission_id})",
                },
            )

        result = {
            "error": False,
            "submission": {
                "id": submission.id,
                "exam_id": submission.exam_id,
                "participant_id": submission.participant_id,
                "spec_id": submission.spec_id,
                "lang": submission.lang,
                "status": submission.status.value if submission.status else None,
                "code_inline": submission.code_inline,
                "code_sha256": submission.code_sha256,
                "code_bytes": submission.code_bytes,
                "code_loc": submission.code_loc,
                "created_at": (
                    submission.created_at.isoformat() if submission.created_at else None
                ),
                "updated_at": (
                    submission.updated_at.isoformat() if submission.updated_at else None
                ),
            },
        }

        if include_runs and submission.runs:
            result["submission"]["runs"] = [
                {
                    "id": run.id,
                    "case_index": run.case_index,
                    "grp": run.grp.value if run.grp else None,
                    "verdict": run.verdict.value if run.verdict else None,
                    "time_ms": run.time_ms,
                    "mem_kb": run.mem_kb,
                    "stdout_bytes": run.stdout_bytes,
                    "stderr_bytes": run.stderr_bytes,
                    "created_at": (
                        run.created_at.isoformat() if run.created_at else None
                    ),
                }
                for run in submission.runs
            ]

        if include_score and submission.score:
            result["submission"]["score"] = {
                "prompt_score": (
                    float(submission.score.prompt_score)
                    if submission.score.prompt_score
                    else None
                ),
                "perf_score": (
                    float(submission.score.perf_score)
                    if submission.score.perf_score
                    else None
                ),
                "correctness_score": (
                    float(submission.score.correctness_score)
                    if submission.score.correctness_score
                    else None
                ),
                "total_score": (
                    float(submission.score.total_score)
                    if submission.score.total_score
                    else None
                ),
                "rubric_json": submission.score.rubric_json,
                "created_at": (
                    submission.score.created_at.isoformat()
                    if submission.score.created_at
                    else None
                ),
            }

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"제출 정보 조회 실패: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": True,
                "error_code": "INTERNAL_ERROR",
                "error_message": f"제출 정보 조회 중 오류가 발생했습니다: {str(e)}",
            },
        )


@router.get(
    "/exams/{exam_id}/participants/{participant_id}/sessions",
    summary="참가자의 모든 세션 조회",
    description="PostgreSQL에서 특정 참가자의 모든 세션을 조회합니다.",
)
async def get_participant_sessions(
    exam_id: int, participant_id: int, db: AsyncSession = Depends(get_db_context)
):
    """참가자의 모든 세션 조회"""
    try:
        session_repo = SessionRepository(db)
        sessions = await session_repo.get_sessions_by_exam_participant(
            exam_id=exam_id, participant_id=participant_id
        )

        return {
            "error": False,
            "exam_id": exam_id,
            "participant_id": participant_id,
            "sessions": [
                {
                    "id": session.id,
                    "spec_id": session.spec_id,
                    "started_at": (
                        session.started_at.isoformat() if session.started_at else None
                    ),
                    "ended_at": (
                        session.ended_at.isoformat() if session.ended_at else None
                    ),
                    "total_tokens": session.total_tokens,
                }
                for session in sessions
            ],
            "total_sessions": len(sessions),
        }
    except Exception as e:
        logger.error(f"참가자 세션 조회 실패: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": True,
                "error_code": "INTERNAL_ERROR",
                "error_message": f"참가자 세션 조회 중 오류가 발생했습니다: {str(e)}",
            },
        )


@router.get(
    "/exams/{exam_id}/participants/{participant_id}/submissions",
    summary="참가자의 모든 제출 조회",
    description="PostgreSQL에서 특정 참가자의 모든 제출을 조회합니다.",
)
async def get_participant_submissions(
    exam_id: int, participant_id: int, db: AsyncSession = Depends(get_db_context)
):
    """참가자의 모든 제출 조회"""
    try:
        submission_repo = SubmissionRepository(db)
        submissions = await submission_repo.get_participant_submissions(
            exam_id=exam_id, participant_id=participant_id
        )

        return {
            "error": False,
            "exam_id": exam_id,
            "participant_id": participant_id,
            "submissions": [
                {
                    "id": submission.id,
                    "spec_id": submission.spec_id,
                    "lang": submission.lang,
                    "status": submission.status.value if submission.status else None,
                    "code_bytes": submission.code_bytes,
                    "code_loc": submission.code_loc,
                    "created_at": (
                        submission.created_at.isoformat()
                        if submission.created_at
                        else None
                    ),
                    "updated_at": (
                        submission.updated_at.isoformat()
                        if submission.updated_at
                        else None
                    ),
                }
                for submission in submissions
            ],
            "total_submissions": len(submissions),
        }
    except Exception as e:
        logger.error(f"참가자 제출 조회 실패: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": True,
                "error_code": "INTERNAL_ERROR",
                "error_message": f"참가자 제출 조회 중 오류가 발생했습니다: {str(e)}",
            },
        )
