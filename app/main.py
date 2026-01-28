"""
FastAPI 메인 애플리케이션
AI Vibe Coding Test Worker
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.infrastructure.cache.redis_client import redis_client
from app.infrastructure.persistence.session import close_db, init_db
from app.presentation.api.routes import chat_router, health_router, session_router

# Judge0 Worker 태스크 (전역 변수로 관리)
_judge_worker_task: Optional[asyncio.Task] = None

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def _start_judge_worker():
    """Judge0 Worker를 백그라운드에서 실행"""
    try:
        from app.application.workers.judge_worker import JudgeWorker

        worker = JudgeWorker()
        await worker.start()
    except asyncio.CancelledError:
        logger.info("[JudgeWorker] Worker 취소됨")
    except Exception as e:
        logger.error(f"[JudgeWorker] Worker 오류: {str(e)}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    애플리케이션 라이프사이클 관리
    - startup: Redis, PostgreSQL 연결, Judge0 Worker 시작
    - shutdown: 연결 종료, Worker 중지
    """
    global _judge_worker_task

    # Startup
    logger.info("Starting AI Vibe Coding Test Worker...")

    # Redis 연결
    try:
        await redis_client.connect()
        logger.info("Redis 연결 성공")
    except Exception as e:
        logger.error(f"Redis 연결 실패: {str(e)}")
        raise

    # PostgreSQL 연결 테스트
    try:
        await init_db()
        logger.info("PostgreSQL 연결 성공")
    except Exception as e:
        logger.warning(f"PostgreSQL 연결 실패 (읽기 전용 모드로 계속): {str(e)}")

    # Judge0 Worker 백그라운드 실행
    if settings.ENABLE_JUDGE_WORKER:
        _judge_worker_task = asyncio.create_task(_start_judge_worker())
        logger.info("[JudgeWorker] Worker 백그라운드 시작")
    else:
        logger.info("[JudgeWorker] Worker 비활성화 (ENABLE_JUDGE_WORKER=false)")

    logger.info(f"서버 시작 완료: http://{settings.API_HOST}:{settings.API_PORT}")

    yield

    # Shutdown
    logger.info("Shutting down...")

    # Judge0 Worker 중지
    if _judge_worker_task and not _judge_worker_task.done():
        _judge_worker_task.cancel()
        try:
            await _judge_worker_task
        except asyncio.CancelledError:
            pass
        logger.info("[JudgeWorker] Worker 중지됨")

    await redis_client.close()
    await close_db()

    logger.info("서버 종료 완료")


# FastAPI 앱 생성
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## AI Vibe Coding Test Worker

LangGraph 기반 AI 코딩 테스트 평가 시스템

### 기능
- 🤖 AI 코딩 어시스턴트와 대화
- 📝 코드 제출 및 평가
- 📊 실시간 턴별 평가
- 🏆 최종 점수 산출

### 평가 항목
- 프롬프트 활용 점수
- 코드 성능 점수  
- 코드 정확성 점수
""",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인만 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 정적 파일 서빙 (웹 인터페이스) - 라우터 등록 전에 먼저 처리
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
logger.info(
    f"정적 파일 디렉토리: {static_dir}, 존재 여부: {os.path.exists(static_dir)}"
)

if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    async def read_root():
        """웹 인터페이스 홈페이지"""
        index_path = os.path.join(static_dir, "index.html")
        logger.info(
            f"인덱스 파일 경로: {index_path}, 존재 여부: {os.path.exists(index_path)}"
        )
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {
            "message": "웹 인터페이스 파일을 찾을 수 없습니다.",
            "static_dir": static_dir,
            "index_path": index_path,
        }


# 라우터 등록
app.include_router(health_router)
app.include_router(chat_router, prefix="/api")
app.include_router(session_router, prefix="/api")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )
