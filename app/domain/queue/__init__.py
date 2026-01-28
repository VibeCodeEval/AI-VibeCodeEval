"""
큐 시스템 모듈
Judge0 코드 실행을 위한 큐 어댑터
"""

from app.domain.queue.adapters.base import JudgeResult, JudgeTask, QueueAdapter
from app.domain.queue.factory import create_queue_adapter

__all__ = [
    "create_queue_adapter",
    "JudgeTask",
    "JudgeResult",
    "QueueAdapter",
]
