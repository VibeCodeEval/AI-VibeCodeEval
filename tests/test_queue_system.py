"""
큐 시스템 테스트
"""
import asyncio
from unittest.mock import MagicMock

import pytest

from app.core.config import settings
from app.domain.queue.adapters.base import JudgeResult, JudgeTask
from app.domain.queue.adapters.redis import RedisQueueAdapter
from app.domain.queue.factory import create_queue_adapter


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
        assert retrieved_result.passed_test_cases is None
        assert retrieved_result.total_test_cases is None

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
        assert retrieved_result.passed_test_cases is None
        assert retrieved_result.total_test_cases is None

        # JudgeResult 다중 TC 필드 Redis JSON round-trip
        task_tc = JudgeTask(
            task_id="test_redis_task_tc_fields",
            code="print(1)",
            language="python",
            test_cases=[],
            timeout=5,
            memory_limit=128,
        )
        await queue.enqueue(task_tc)
        deq_tc = await queue.dequeue()
        assert deq_tc is not None
        result_tc = JudgeResult(
            task_id=task_tc.task_id,
            status="success",
            output="ok\n",
            execution_time=0.05,
            memory_used=512,
            exit_code=0,
            passed_test_cases=3,
            total_test_cases=5,
        )
        await queue.save_result(task_tc.task_id, result_tc)
        out_tc = await queue.get_result(task_tc.task_id)
        assert out_tc is not None
        assert out_tc.passed_test_cases == 3
        assert out_tc.total_test_cases == 5

        task_none = JudgeTask(
            task_id="test_redis_task_tc_none",
            code="print(2)",
            language="python",
            test_cases=[],
            timeout=5,
            memory_limit=128,
        )
        await queue.enqueue(task_none)
        await queue.dequeue()
        result_none = JudgeResult(
            task_id=task_none.task_id,
            status="error",
            output="",
            passed_test_cases=None,
            total_test_cases=None,
        )
        await queue.save_result(task_none.task_id, result_none)
        out_none = await queue.get_result(task_none.task_id)
        assert out_none is not None
        assert out_none.passed_test_cases is None
        assert out_none.total_test_cases is None

    finally:
        settings.USE_REDIS_QUEUE = original_value
        try:
            await redis_client.close()
        except Exception:
            pass


def test_redis_adapter_judge_result_serialization_roundtrip_and_legacy():
    """Redis 직렬화 헬퍼: 정수 TC 필드·None·레거시 JSON(키 없음) 역직렬화."""
    adapter = RedisQueueAdapter(MagicMock())

    r_full = JudgeResult(
        task_id="t1",
        status="success",
        output="out",
        passed_test_cases=7,
        total_test_cases=10,
    )
    d_full = adapter._result_to_dict(r_full)
    assert d_full["passed_test_cases"] == 7
    assert d_full["total_test_cases"] == 10
    r_back = adapter._dict_to_result(d_full)
    assert r_back.passed_test_cases == 7
    assert r_back.total_test_cases == 10

    r_nulls = JudgeResult(
        task_id="t2",
        status="success",
        output="",
        passed_test_cases=None,
        total_test_cases=None,
    )
    d_nulls = adapter._result_to_dict(r_nulls)
    r_back_nulls = adapter._dict_to_result(d_nulls)
    assert r_back_nulls.passed_test_cases is None
    assert r_back_nulls.total_test_cases is None

    legacy = {
        "task_id": "legacy",
        "status": "success",
        "output": "x",
    }
    r_legacy = adapter._dict_to_result(legacy)
    assert r_legacy.passed_test_cases is None
    assert r_legacy.total_test_cases is None

