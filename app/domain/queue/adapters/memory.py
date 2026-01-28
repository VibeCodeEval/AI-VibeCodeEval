"""
메모리 기반 큐 어댑터 (개발/테스트용)
"""

import asyncio
from collections import deque
from typing import Dict, Optional

from app.domain.queue.adapters.base import JudgeResult, JudgeTask, QueueAdapter


class MemoryQueueAdapter(QueueAdapter):
    """메모리 기반 큐 (개발/테스트용)"""

    def __init__(self):
        self.queue: deque = deque()
        self.results: Dict[str, JudgeResult] = {}
        self.status: Dict[str, str] = {}
        self.lock = asyncio.Lock()

    async def enqueue(self, task: JudgeTask) -> str:
        """큐에 태스크 추가"""
        async with self.lock:
            self.queue.append(task)
            self.status[task.task_id] = "pending"
        return task.task_id

    async def dequeue(self) -> Optional[JudgeTask]:
        """큐에서 태스크 가져오기"""
        async with self.lock:
            if self.queue:
                task = self.queue.popleft()
                self.status[task.task_id] = "processing"
                return task
        return None

    async def get_result(self, task_id: str) -> Optional[JudgeResult]:
        """결과 조회"""
        return self.results.get(task_id)

    async def get_status(self, task_id: str) -> str:
        """상태 조회"""
        return self.status.get(task_id, "unknown")

    async def save_result(self, task_id: str, result: JudgeResult) -> bool:
        """결과 저장"""
        async with self.lock:
            self.results[task_id] = result
            self.status[task_id] = (
                "completed" if result.status == "success" else "failed"
            )
        return True

    async def set_status(self, task_id: str, status: str) -> bool:
        """상태 설정"""
        async with self.lock:
            self.status[task_id] = status
        return True
