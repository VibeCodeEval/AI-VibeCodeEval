"""
Judge0 Worker 상태 확인 스크립트

[확인 사항]
1. Worker 프로세스 실행 여부
2. 큐 시스템 설정 (Redis/Memory)
3. 큐 연결 상태
4. 테스트 작업 추가 및 처리 확인
"""
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
from app.domain.queue import create_queue_adapter, JudgeTask
from app.core.config import settings
from app.infrastructure.cache.redis_client import redis_client

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def check_judge0_worker():
    """Judge0 Worker 상태 확인"""
    logger.info("=" * 80)
    logger.info("Judge0 Worker 상태 확인")
    logger.info("=" * 80)
    
    try:
        # ========================================================================
        # 1단계: 큐 시스템 설정 확인
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("[1단계] 큐 시스템 설정 확인")
        logger.info("=" * 80)
        
        use_redis_queue = settings.USE_REDIS_QUEUE
        logger.info(f"   - USE_REDIS_QUEUE: {use_redis_queue}")
        
        if use_redis_queue:
            logger.info("   - 큐 타입: Redis Queue (프로덕션)")
            logger.info("   - 특징: 프로세스 간 공유 가능, Worker 별도 프로세스 필요")
        else:
            logger.info("   - 큐 타입: Memory Queue (개발/테스트)")
            logger.warning("   - ⚠️ 주의: Memory Queue는 프로세스 간 공유 불가!")
            logger.warning("   - Worker는 FastAPI 서버와 같은 프로세스에서 실행되어야 함")
        
        # ========================================================================
        # 2단계: Redis 연결 확인 (Redis Queue 사용 시)
        # ========================================================================
        if use_redis_queue:
            logger.info("\n" + "=" * 80)
            logger.info("[2단계] Redis 연결 확인")
            logger.info("=" * 80)
            
            try:
                await redis_client.connect()
                logger.info("   ✅ Redis 연결 성공")
                
                # Redis ping 테스트
                pong = await redis_client.client.ping()
                if pong:
                    logger.info("   ✅ Redis ping 성공")
                else:
                    logger.error("   ❌ Redis ping 실패")
                    return False
                
            except Exception as e:
                logger.error(f"   ❌ Redis 연결 실패: {str(e)}")
                logger.error("   → Worker 실행 전에 Redis가 실행 중인지 확인하세요")
                return False
        
        # ========================================================================
        # 3단계: 큐 어댑터 생성 및 테스트
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("[3단계] 큐 어댑터 테스트")
        logger.info("=" * 80)
        
        queue = create_queue_adapter()
        queue_type = type(queue).__name__
        logger.info(f"   - 큐 어댑터 타입: {queue_type}")
        
        # 테스트 작업 생성
        test_task = JudgeTask(
            task_id="test_worker_check",
            code="print('Worker Test')",
            language="python",
            test_cases=[],
            timeout=5,
            memory_limit=128
        )
        
        # 작업 추가
        task_id = await queue.enqueue(test_task)
        logger.info(f"   ✅ 테스트 작업 추가 완료 - task_id: {task_id}")
        
        # 상태 확인
        status = await queue.get_status(task_id)
        logger.info(f"   - 작업 상태: {status}")
        
        # ========================================================================
        # 4단계: Worker 처리 확인
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("[4단계] Worker 처리 확인")
        logger.info("=" * 80)
        
        logger.info("   - Worker가 실행 중인지 확인 중...")
        logger.info("   - 최대 5초 대기...")
        
        # 5초 동안 상태 변화 확인
        max_wait = 5
        poll_interval = 0.5
        start_time = asyncio.get_event_loop().time()
        
        last_status = status
        while asyncio.get_event_loop().time() - start_time < max_wait:
            current_status = await queue.get_status(task_id)
            
            if current_status != last_status:
                logger.info(f"   - 상태 변화: {last_status} → {current_status}")
                last_status = current_status
            
            # 작업이 완료되었는지 확인
            if current_status in ["completed", "failed"]:
                logger.info(f"   ✅ Worker가 작업을 처리했습니다! - 최종 상태: {current_status}")
                
                # 결과 확인
                from app.domain.queue import JudgeResult
                result = await queue.get_result(task_id)
                if result:
                    logger.info(f"   - 결과 상태: {result.status}")
                    logger.info(f"   - 실행 시간: {result.execution_time}초")
                    logger.info(f"   - 메모리 사용량: {result.memory_used / 1024 / 1024:.2f}MB")
                break
            
            await asyncio.sleep(poll_interval)
        else:
            # 타임아웃
            final_status = await queue.get_status(task_id)
            if final_status == "pending":
                logger.error("   ❌ Worker가 작업을 처리하지 않았습니다!")
                logger.error("   → Worker가 실행 중인지 확인하세요")
                logger.error("")
                logger.error("   [Worker 실행 방법]")
                if use_redis_queue:
                    logger.error("   터미널에서 다음 명령 실행:")
                    logger.error("   uv run python -m app.application.workers.judge_worker")
                else:
                    logger.error("   ⚠️ Memory Queue는 Worker를 별도 프로세스로 실행할 수 없습니다")
                    logger.error("   → USE_REDIS_QUEUE=True로 설정하거나")
                    logger.error("   → Worker를 FastAPI 서버와 같은 프로세스에서 실행해야 합니다")
                return False
            else:
                logger.warning(f"   ⚠️ 작업이 아직 처리 중입니다 - 상태: {final_status}")
        
        # ========================================================================
        # 5단계: 최종 요약
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("[5단계] 최종 요약")
        logger.info("=" * 80)
        
        logger.info("✅ Judge0 Worker 상태 확인 완료!")
        logger.info(f"   - 큐 타입: {queue_type}")
        logger.info(f"   - Redis Queue 사용: {use_redis_queue}")
        logger.info(f"   - Worker 상태: {'정상 작동' if last_status in ['completed', 'failed'] else '확인 필요'}")
        
        if use_redis_queue:
            logger.info("")
            logger.info("   [Worker 실행 방법]")
            logger.info("   터미널에서 다음 명령 실행:")
            logger.info("   uv run python -m app.application.workers.judge_worker")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 확인 중 오류: {str(e)}", exc_info=True)
        return False
    finally:
        if use_redis_queue:
            try:
                await redis_client.close()
            except:
                pass


if __name__ == "__main__":
    success = asyncio.run(check_judge0_worker())
    sys.exit(0 if success else 1)


