"""
제출 평가 E2E 타임아웃 추적 (contextvars).

백그라운드 submit 평가에서 현재 LangGraph 노드명을 기록하고,
전역 타임아웃 시 ai-evaluation-timeout[노드] 로그에 사용한다.
"""

from __future__ import annotations

import contextvars
import logging
from typing import Any, Awaitable, Callable, Optional, TypeVar

from app.core.config import settings

logger = logging.getLogger(__name__)

_eval_current_node: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "eval_current_node", default=None
)
_eval_submission_id: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar(
    "eval_submission_id", default=None
)

StateT = TypeVar("StateT")


def begin_eval_tracking(
    *,
    submission_id: Optional[int] = None,
    session_id: Optional[str] = None,
) -> None:
    _eval_submission_id.set(submission_id)
    _eval_current_node.set("eval_process_start")
    logger.info(
        "[EvalTimeout] 추적 시작 submission_id=%s session_id=%s limit_sec=%s",
        submission_id,
        session_id,
        settings.EVAL_SUBMISSION_TIMEOUT_SEC,
    )


def end_eval_tracking() -> None:
    _eval_current_node.set(None)
    _eval_submission_id.set(None)


def set_eval_current_node(node_name: str) -> None:
    _eval_current_node.set(node_name)


def get_eval_current_node() -> str:
    return _eval_current_node.get() or "unknown"


def get_eval_submission_id() -> Optional[int]:
    return _eval_submission_id.get()


def log_evaluation_timeout(submission_id: Optional[int] = None) -> str:
    """타임아웃 시점 노드명을 로그하고 반환."""
    node = get_eval_current_node()
    sid = submission_id if submission_id is not None else get_eval_submission_id()
    limit = settings.EVAL_SUBMISSION_TIMEOUT_SEC
    logger.error(
        "ai-evaluation-timeout[%s] submission_id=%s timeout_sec=%s",
        node,
        sid,
        limit,
    )
    return node


def wrap_eval_node_tracking(
    node_name: str,
    impl: Callable[[StateT], Awaitable[Any]],
) -> Callable[[StateT], Awaitable[Any]]:
    """LangGraph 노드 진입 시 현재 노드명 갱신."""

    async def wrapped(state: StateT) -> Any:
        set_eval_current_node(node_name)
        return await impl(state)

    wrapped.__name__ = getattr(impl, "__name__", node_name)
    wrapped.__qualname__ = getattr(impl, "__qualname__", node_name)
    return wrapped
