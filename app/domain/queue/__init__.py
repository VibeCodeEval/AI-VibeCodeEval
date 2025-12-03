"""
큐 시스템 모듈
Judge0 코드 실행을 위한 큐 어댑터
"""
from app.domain.queue.factory import create_queue_adapter
from app.domain.queue.adapters.base import JudgeTask, JudgeResult, QueueAdapter

__all__ = [
    "create_queue_adapter",
    "JudgeTask",
    "JudgeResult",
    "QueueAdapter",
]

