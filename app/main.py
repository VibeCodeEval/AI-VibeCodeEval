"""
FastAPI 메인 애플리케이션
AI Vibe Coding Test Worker
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.redis_client import redis_client
from app.db.session import init_db, close_db
from app.api.routes import chat_router, session_router, health_router


# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

import os
print(">>> DEBUG POSTGRES_PORT =", os.getenv("POSTGRES_PORT"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    애플리케이션 라이프사이클 관리
    - startup: Redis, PostgreSQL 연결
    - shutdown: 연결 종료
    """
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
    
    logger.info(f"서버 시작 완료: http://{settings.API_HOST}:{settings.API_PORT}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    
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

