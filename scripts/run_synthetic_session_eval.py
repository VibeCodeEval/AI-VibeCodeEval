#!/usr/bin/env python
"""
가상 세션 1건에 대해 평가(EvalService.submit_code) 실행

[전제]
- DB에 이미 가상 데이터가 저장되어 있음 (generate_synthetic_v21_data.py --save-one-to-db)
- prompt_messages에는 USER 메시지만 있으므로, 턴별 placeholder AI 메시지를 넣어 State 구성

[흐름]
1. DB에서 세션 1건 조회 (--session-id 미지정 시 최신 세션)
2. 해당 세션의 prompt_messages, submission 조회
3. LangGraph State 구성 (messages = Human + placeholder AI per turn, problem_context, current_turn 등)
4. Redis에 상태 저장 (langgraph:state:session_{id})
5. EvalService.submit_code() 호출 → 평가 실행
6. 최종 점수·등급 출력

사용법:
    uv run python scripts/run_synthetic_session_eval.py
    uv run python scripts/run_synthetic_session_eval.py --session-id 123
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from sqlalchemy import select

from app.application.services.eval_service import EvalService
from app.domain.langgraph.graph import get_initial_state
from app.domain.langgraph.utils.problem_info import get_problem_info_sync
from app.infrastructure.cache.redis_client import redis_client
from app.infrastructure.persistence.models.sessions import PromptSession
from app.infrastructure.persistence.session import get_db_context
from app.infrastructure.repositories.session_repository import SessionRepository
from app.infrastructure.repositories.submission_repository import SubmissionRepository
from app.infrastructure.repositories.state_repository import StateRepository

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)


# 가상 데이터는 USER 메시지만 있으므로, Eval Turn Guard가 턴별 human+ai를 요구하므로 placeholder 사용
PLACEHOLDER_AI = "요청을 반영했습니다. (가상 데이터: AI 응답 placeholder)"


def build_messages_from_db_messages(db_messages: list) -> list:
    """
    DB의 prompt_messages(USER만 있을 수 있음)를 LangGraph messages로 변환.
    각 턴에 대해 HumanMessage + AIMessage(placeholder) 쌍을 만든다.
    """
    from langchain_core.messages import AIMessage, HumanMessage

    result = []
    for msg in db_messages:
        turn = msg.turn
        role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
        content = msg.content or ""

        if role in ("USER", "user"):
            result.append(
                HumanMessage(content=content)
            )
            # LangChain 메시지에 turn/role 속성 추가 (eval_turn_guard가 사용)
            result[-1].turn = turn
            result[-1].role = "user"
            result.append(AIMessage(content=PLACEHOLDER_AI))
            result[-1].turn = turn
            result[-1].role = "ai"
        elif role in ("ASSISTANT", "assistant"):
            # 이미 AI 메시지가 있으면 그대로 사용 (placeholder 덮어쓰지 않음)
            result.append(AIMessage(content=content))
            result[-1].turn = turn
            result[-1].role = "ai"
    return result


async def run_eval(session_id: int) -> dict | None:
    """
    세션 1건에 대해 Redis 상태를 구성하고 submit_code로 평가 실행.
    """
    async with get_db_context() as db:
        session_repo = SessionRepository(db)
        submission_repo = SubmissionRepository(db)

        # 세션 조회
        session = await session_repo.get_session_by_id(session_id, include_messages=True)
        if not session:
            logger.error(f"세션을 찾을 수 없음: session_id={session_id}")
            return None

        exam_id = session.exam_id
        participant_id = session.participant_id
        spec_id = session.spec_id or 20  # 스마트 게이트 기본

        # 메시지: include_messages=True면 session.messages에 로드됨 (턴 순)
        db_messages = getattr(session, "messages", None) or await session_repo.get_session_messages(session_id)
        if not db_messages:
            logger.warning("해당 세션에 메시지가 없습니다. 평가할 턴이 없을 수 있습니다.")

        # 제출 코드 조회
        submission = await submission_repo.get_latest_submission(exam_id, participant_id)
        if not submission or not submission.code_inline:
            logger.error("해당 세션의 제출 코드를 찾을 수 없습니다.")
            return None

        code_content = submission.code_inline
        submission_id = submission.id

    # problem_context (동기)
    problem_context = get_problem_info_sync(spec_id)
    if not problem_context:
        logger.warning("spec_id=%s 문제 정보 없음. 하드코딩/DB 확인.", spec_id)

    # 메시지 리스트 구성 (Human + AI placeholder per turn)
    messages = build_messages_from_db_messages(db_messages)
    max_turn = max((m.turn for m in db_messages), default=0)
    current_turn = max_turn + 1  # 제출은 다음 턴으로 간주

    # 초기 상태 골격
    state = get_initial_state(
        session_id=f"session_{session_id}",
        exam_id=exam_id,
        participant_id=participant_id,
        spec_id=spec_id,
        human_message="코드를 제출합니다.",
    )
    state["messages"] = messages
    state["current_turn"] = current_turn
    state["is_submitted"] = True
    state["code_content"] = code_content
    state["lang"] = "python"
    state["submission_id"] = submission_id
    state["problem_context"] = problem_context

    redis_session_id = f"session_{session_id}"

    # Redis에 상태 저장
    state_repo = StateRepository(redis_client)
    ok = await state_repo.save_state(redis_session_id, state)
    if not ok:
        logger.error("Redis 상태 저장 실패")
        return None
    logger.info("Redis 상태 저장 완료: %s", redis_session_id)

    # 평가 실행
    eval_service = EvalService(redis_client)
    result = await eval_service.submit_code(
        session_id=redis_session_id,
        exam_id=exam_id,
        participant_id=participant_id,
        spec_id=spec_id,
        code_content=code_content,
        lang="python",
        submission_id=submission_id,
    )
    return result


async def get_latest_session_id() -> int | None:
    """가장 최근 prompt_session id 한 건 반환."""
    async with get_db_context() as db:
        r = await db.execute(
            select(PromptSession).order_by(PromptSession.id.desc()).limit(1)
        )
        session = r.scalar_one_or_none()
        return session.id if session else None


def main():
    parser = argparse.ArgumentParser(description="가상 세션 1건 평가 실행")
    parser.add_argument(
        "--session-id",
        type=int,
        default=None,
        help="평가할 prompt_session id (미지정 시 최신 세션)",
    )
    args = parser.parse_args()

    async def _main():
        await redis_client.connect()
        try:
            session_id = args.session_id
            if session_id is None:
                session_id = await get_latest_session_id()
                if session_id is None:
                    logger.error("DB에 prompt_session이 없습니다. 먼저 generate_synthetic_v21_data.py --save-one-to-db 를 실행하세요.")
                    return 1
                logger.info("최신 세션 사용: session_id=%s", session_id)
            result = await run_eval(session_id)
            if result is None:
                return 1
            logger.info("")
            logger.info("========== 평가 결과 ==========")
            logger.info("session_id: %s", result.get("session_id"))
            logger.info("turn: %s", result.get("turn"))
            logger.info("is_submitted: %s", result.get("is_submitted"))
            if result.get("final_scores"):
                logger.info("final_scores: %s", result.get("final_scores"))
            if result.get("turn_scores"):
                logger.info("turn_scores: %s", result.get("turn_scores"))
            logger.info("================================")
            return 0
        finally:
            await redis_client.close()

    return asyncio.run(_main())


if __name__ == "__main__":
    sys.exit(main())
