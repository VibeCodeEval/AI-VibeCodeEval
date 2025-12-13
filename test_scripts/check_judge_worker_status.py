"""
Judge0 Worker 실행 상태 확인 스크립트

확인 방법:
1. Redis 큐 상태 확인 (큐 길이, 처리 중인 작업)
2. 프로세스 확인 (ps, docker ps)
3. 테스트 작업 전송 및 결과 확인
"""
import asyncio
import sys
import logging
from datetime import datetime

from app.domain.queue import create_queue_adapter, JudgeTask
from app.infrastructure.cache.redis_client import redis_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def check_redis_queue_status():
    """Redis 큐 상태 확인"""
    try:
        await redis_client.connect()
        
        # 큐 길이 확인
        queue_key = "judge_queue:pending"
        queue_length = await redis_client.client.llen(queue_key)
        
        logger.info(f"[Queue Status] 큐 길이: {queue_length}개 작업 대기 중")
        
        # 처리 중인 작업 확인 (judge_status:* 패턴)
        status_keys = []
        async for key in redis_client.client.scan_iter(match="judge_status:*"):
            status_keys.append(key)
        
        processing_count = 0
        pending_count = 0
        completed_count = 0
        failed_count = 0
        
        for key in status_keys:
            status = await redis_client.get(key)
            if status:
                if status == "processing":
                    processing_count += 1
                elif status == "pending":
                    pending_count += 1
                elif status == "completed":
                    completed_count += 1
                elif status == "failed":
                    failed_count += 1
        
        logger.info(f"[Queue Status] 처리 중: {processing_count}개")
        logger.info(f"[Queue Status] 대기 중: {pending_count}개")
        logger.info(f"[Queue Status] 완료: {completed_count}개")
        logger.info(f"[Queue Status] 실패: {failed_count}개")
        
        # Worker가 실행 중인지 추정
        # 큐에 작업이 있고 processing 상태가 없으면 Worker가 멈춘 것으로 추정
        if queue_length > 0 and processing_count == 0:
            logger.warning("[Worker Status] ⚠️ 큐에 작업이 있지만 처리 중인 작업이 없습니다. Worker가 실행 중이지 않을 수 있습니다.")
            return False
        elif queue_length == 0 and processing_count == 0:
            logger.info("[Worker Status] ✅ 큐가 비어있고 처리 중인 작업이 없습니다. (정상 또는 Worker 미실행)")
            return None  # 불확실
        else:
            logger.info("[Worker Status] ✅ Worker가 실행 중인 것으로 보입니다.")
            return True
        
    except Exception as e:
        logger.error(f"[Queue Status] Redis 연결 실패: {str(e)}")
        return False
    finally:
        await redis_client.close()


async def send_test_task():
    """테스트 작업 전송하여 Worker 응답 확인"""
    try:
        queue = create_queue_adapter()
        
        # 간단한 테스트 작업 생성
        test_task = JudgeTask(
            task_id=f"test_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            code="print('Hello, World!')",
            language="python",
            test_cases=[],
            timeout=5,
            memory_limit=128,
            meta={"test": True}
        )
        
        logger.info(f"[Test Task] 테스트 작업 전송 - task_id: {test_task.task_id}")
        await queue.enqueue(test_task)
        
        # 결과 대기 (최대 10초)
        max_wait = 10
        start_time = datetime.now().timestamp()
        poll_interval = 0.5
        
        while datetime.now().timestamp() - start_time < max_wait:
            status = await queue.get_status(test_task.task_id)
            
            if status == "completed":
                result = await queue.get_result(test_task.task_id)
                if result:
                    logger.info(f"[Test Task] ✅ Worker 응답 확인 - task_id: {test_task.task_id}, status: {result.status}")
                    return True
                break
            elif status == "failed":
                logger.warning(f"[Test Task] ⚠️ Worker가 작업을 처리했지만 실패 - task_id: {test_task.task_id}")
                return True  # Worker는 실행 중이지만 작업 실패
            elif status == "processing":
                logger.info(f"[Test Task] 작업 처리 중... - task_id: {test_task.task_id}")
            
            await asyncio.sleep(poll_interval)
        
        # 타임아웃
        final_status = await queue.get_status(test_task.task_id)
        if final_status == "pending":
            logger.error(f"[Test Task] ❌ Worker가 작업을 처리하지 못했습니다. (타임아웃) - task_id: {test_task.task_id}")
            return False
        else:
            logger.warning(f"[Test Task] ⚠️ 작업 상태 불명확 - task_id: {test_task.task_id}, status: {final_status}")
            return None
        
    except Exception as e:
        logger.error(f"[Test Task] 테스트 작업 전송 실패: {str(e)}")
        return False


async def main():
    """메인 함수"""
    logger.info("=" * 60)
    logger.info("Judge0 Worker 상태 확인")
    logger.info("=" * 60)
    
    # 1. Redis 큐 상태 확인
    logger.info("\n[1단계] Redis 큐 상태 확인")
    queue_status = await check_redis_queue_status()
    
    # 2. 테스트 작업 전송
    logger.info("\n[2단계] 테스트 작업 전송 및 응답 확인")
    test_result = await send_test_task()
    
    # 3. 종합 판단
    logger.info("\n" + "=" * 60)
    logger.info("종합 결과")
    logger.info("=" * 60)
    
    if test_result is True:
        logger.info("✅ Judge0 Worker가 실행 중입니다.")
        sys.exit(0)
    elif test_result is False:
        logger.error("❌ Judge0 Worker가 실행 중이지 않습니다.")
        logger.error("   다음 명령어로 Worker를 실행하세요:")
        logger.error("   uv run python -m app.application.workers.judge_worker")
        sys.exit(1)
    else:
        logger.warning("⚠️ Worker 상태를 확인할 수 없습니다.")
        if queue_status is False:
            logger.error("   큐 상태를 보면 Worker가 실행 중이지 않을 수 있습니다.")
            sys.exit(1)
        else:
            logger.info("   수동으로 프로세스를 확인하세요:")
            logger.info("   - Docker: docker ps | grep judge_worker")
            logger.info("   - 로컬: ps aux | grep judge_worker")
            sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())



