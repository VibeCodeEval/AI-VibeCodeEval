#!/usr/bin/env python
"""
개발 서버 실행 스크립트
FastAPI 서버와 Judge0 Worker를 함께 실행
"""
import os
import sys
import asyncio
import logging
from threading import Thread

# 프로젝트 루트를 Python 경로에 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run_judge_worker():
    """Judge0 Worker를 별도 스레드에서 실행"""
    async def worker_main():
        try:
            from app.application.workers.judge_worker import main as judge_main
            await judge_main()
        except KeyboardInterrupt:
            logger.info("[JudgeWorker] Worker 중지 요청 수신")
        except Exception as e:
            logger.error(f"[JudgeWorker] Worker 오류: {str(e)}", exc_info=True)
    
    try:
        # 스레드에서 새로운 이벤트 루프 생성
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(worker_main())
    except Exception as e:
        logger.error(f"[JudgeWorker] Worker 실행 실패: {str(e)}", exc_info=True)


def run_uvicorn():
    """Uvicorn 서버 실행"""
    import uvicorn
    from dotenv import load_dotenv
    
    # 환경 변수 로드
    load_dotenv()
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="debug",
        # 개발 중 생성되는 산출물 변경으로 인한 과도한 reload 방지
        reload_excludes=[
            "tmp/*",
            ".maestro/*",
            "data/*",
            "*.json",
            "*.jsonl",
            "*.log",
        ],
    )


if __name__ == "__main__":
    # app.main(lifespan)에서도 Worker를 시작하므로,
    # 여기서는 중복 실행을 막기 위해 opt-in으로만 실행.
    run_worker_in_script = os.getenv("RUN_DEV_START_WORKER", "false").lower() in (
        "1",
        "true",
        "yes",
    )
    if run_worker_in_script:
        judge_worker_thread = Thread(target=run_judge_worker, daemon=True)
        judge_worker_thread.start()
        logger.info("[Dev Server] Judge0 Worker 시작됨 (run_dev.py)")
    else:
        logger.info(
            "[Dev Server] Judge0 Worker 스레드 시작 생략 "
            "(app.main의 ENABLE_JUDGE_WORKER 사용)"
        )
    
    # FastAPI 서버 실행 (메인 스레드)
    try:
        run_uvicorn()
    except KeyboardInterrupt:
        logger.info("[Dev Server] 서버 종료 요청 수신")
    except Exception as e:
        logger.error(f"[Dev Server] 서버 실행 오류: {str(e)}", exc_info=True)

