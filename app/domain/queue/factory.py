"""
큐 어댑터 팩토리
환경에 따라 적절한 어댑터 생성
"""

from app.core.config import settings
from app.domain.queue.adapters.base import QueueAdapter
from app.domain.queue.adapters.memory import MemoryQueueAdapter
from app.domain.queue.adapters.redis import RedisQueueAdapter
from app.infrastructure.cache.redis_client import redis_client


def create_queue_adapter() -> QueueAdapter:
    """
    환경에 따라 적절한 큐 어댑터 생성

    설정:
    - USE_REDIS_QUEUE=True: Redis 어댑터 사용 (프로덕션)
    - USE_REDIS_QUEUE=False: 메모리 어댑터 사용 (개발/테스트)

    Returns:
        QueueAdapter 인스턴스
    """
    if settings.USE_REDIS_QUEUE:
        return RedisQueueAdapter(redis_client)
    else:
        return MemoryQueueAdapter()
