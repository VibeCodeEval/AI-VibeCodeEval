"""
큐 시스템 테스트
"""
import pytest
import asyncio
from app.domain.queue.factory import create_queue_adapter
from app.domain.queue.adapters.base import JudgeTask, JudgeResult
from app.core.config import settings


@pytest.mark.asyncio
async def test_memory_queue_adapter():
    """메모리 큐 어댑터 테스트"""
    # 메모리 모드로 설정
    original_value = settings.USE_REDIS_QUEUE
    settings.USE_REDIS_QUEUE = False
    
    try:
        queue = create_queue_adapter()
        
        # 작업 추가
        task = JudgeTask(
            task_id="test_task_1",
            code="print('hello')",
            language="python",
            test_cases=[],
            timeout=5,
            memory_limit=128
        )
        
        task_id = await queue.enqueue(task)
        assert task_id == "test_task_1"
        
        # 상태 확인
        status = await queue.get_status(task_id)
        assert status == "pending"
        
        # 작업 가져오기
        dequeued_task = await queue.dequeue()
        assert dequeued_task is not None
        assert dequeued_task.task_id == "test_task_1"
        assert dequeued_task.code == "print('hello')"
        
        # 상태가 processing으로 변경되었는지 확인
        status = await queue.get_status(task_id)
        assert status == "processing"
        
        # 결과 저장
        result = JudgeResult(
            task_id=task_id,
            status="success",
            output="hello\n",
            execution_time=0.1,
            memory_used=1024,
            exit_code=0
        )
        
        await queue.save_result(task_id, result)
        
        # 결과 조회
        retrieved_result = await queue.get_result(task_id)
        assert retrieved_result is not None
        assert retrieved_result.status == "success"
        assert retrieved_result.output == "hello\n"
        assert retrieved_result.execution_time == 0.1
        
        # 상태가 completed로 변경되었는지 확인
        status = await queue.get_status(task_id)
        assert status == "completed"
        
    finally:
        settings.USE_REDIS_QUEUE = original_value


@pytest.mark.asyncio
async def test_redis_queue_adapter():
    """Redis 큐 어댑터 테스트 (Redis 연결 필요)"""
    # Redis 모드로 설정
    original_value = settings.USE_REDIS_QUEUE
    settings.USE_REDIS_QUEUE = True
    
    try:
        from app.infrastructure.cache.redis_client import redis_client
        
        # Redis 연결 확인
        try:
            await redis_client.connect()
        except Exception as e:
            pytest.skip(f"Redis 연결 실패: {e}")
        
        queue = create_queue_adapter()
        
        # 작업 추가
        task = JudgeTask(
            task_id="test_redis_task_1",
            code="print('hello redis')",
            language="python",
            test_cases=[],
            timeout=5,
            memory_limit=128
        )
        
        task_id = await queue.enqueue(task)
        assert task_id == "test_redis_task_1"
        
        # 상태 확인
        status = await queue.get_status(task_id)
        assert status == "pending"
        
        # 작업 가져오기
        dequeued_task = await queue.dequeue()
        assert dequeued_task is not None
        assert dequeued_task.task_id == "test_redis_task_1"
        
        # 결과 저장
        result = JudgeResult(
            task_id=task_id,
            status="success",
            output="hello redis\n",
            execution_time=0.2,
            memory_used=2048,
            exit_code=0
        )
        
        await queue.save_result(task_id, result)
        
        # 결과 조회
        retrieved_result = await queue.get_result(task_id)
        assert retrieved_result is not None
        assert retrieved_result.status == "success"
        assert retrieved_result.output == "hello redis\n"
        
    finally:
        settings.USE_REDIS_QUEUE = original_value
        try:
            await redis_client.close()
        except:
            pass

