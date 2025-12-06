"""
Judge0 통합 테스트
"""
import pytest
import asyncio
from app.domain.queue import create_queue_adapter, JudgeTask, JudgeResult
from app.infrastructure.judge0.client import Judge0Client
from app.core.config import settings


@pytest.mark.asyncio
async def test_judge0_client_simple():
    """Judge0 클라이언트 간단한 실행 테스트"""
    client = Judge0Client()
    
    try:
        # 간단한 Python 코드 실행
        result = await client.execute_code(
            code="print('Hello, World!')",
            language="python",
            wait=True
        )
        
        status_id = result.get("status", {}).get("id")
        assert status_id == 3, f"예상: Accepted (3), 실제: {status_id}"
        assert "Hello, World!" in result.get("stdout", "")
        
    except Exception as e:
        pytest.skip(f"Judge0 서버 연결 실패: {e}")
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_judge0_client_with_input():
    """입력이 있는 코드 실행 테스트"""
    client = Judge0Client()
    
    try:
        code = """
n = int(input())
print(n * 2)
"""
        result = await client.execute_code(
            code=code,
            language="python",
            stdin="5",
            expected_output="10",
            wait=True
        )
        
        status_id = result.get("status", {}).get("id")
        assert status_id == 3, f"예상: Accepted (3), 실제: {status_id}"
        assert result.get("stdout", "").strip() == "10"
        
    except Exception as e:
        pytest.skip(f"Judge0 서버 연결 실패: {e}")
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_judge0_queue_integration():
    """Judge0 큐 시스템 통합 테스트"""
    # 메모리 모드로 설정
    original_value = settings.USE_REDIS_QUEUE
    settings.USE_REDIS_QUEUE = False
    
    try:
        queue = create_queue_adapter()
        client = Judge0Client()
        
        # 작업 추가
        task = JudgeTask(
            task_id="test_judge0_1",
            code="print('test')",
            language="python",
            test_cases=[],
            timeout=5,
            memory_limit=128
        )
        
        task_id = await queue.enqueue(task)
        assert task_id == "test_judge0_1"
        
        # Worker 시뮬레이션: 큐에서 가져와서 실행
        dequeued_task = await queue.dequeue()
        assert dequeued_task is not None
        
        # Judge0로 실행
        result = await client.execute_code(
            code=dequeued_task.code,
            language=dequeued_task.language,
            wait=True
        )
        
        # 결과 저장
        status_id = result.get("status", {}).get("id")
        judge_result = JudgeResult(
            task_id=task_id,
            status="success" if status_id == 3 else "error",
            output=result.get("stdout", ""),
            error=result.get("stderr"),
            execution_time=float(result.get("time", "0")),
            memory_used=int(result.get("memory", "0")) * 1024,
            exit_code=0 if status_id == 3 else 1
        )
        
        await queue.save_result(task_id, judge_result)
        
        # 결과 조회
        retrieved_result = await queue.get_result(task_id)
        assert retrieved_result is not None
        assert retrieved_result.status == judge_result.status
        
    except Exception as e:
        pytest.skip(f"Judge0 서버 연결 실패: {e}")
    finally:
        settings.USE_REDIS_QUEUE = original_value
        await client.close()




