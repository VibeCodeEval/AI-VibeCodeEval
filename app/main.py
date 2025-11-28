"""
FastAPI 메인 애플리케이션
AI Vibe Coding Test Worker

[목적]
- FastAPI 기반 AI 코딩 테스트 평가 시스템의 진입점
- Spring Boot 백엔드와 통합되어 동작
- LangGraph를 사용하여 복잡한 AI 평가 플로우 구현

[주요 역할]
1. 애플리케이션 초기화 (lifespan 이벤트)
   - Redis 연결 (세션 상태 관리)
   - PostgreSQL 연결 (영구 데이터 저장)
   
2. API 라우터 등록
   - /api/chat: 채팅 및 제출 API
   - /api/session: 세션 관리 API
   - /health: 헬스 체크 API
   
3. CORS 설정 및 미들웨어 구성

[실행 방법]
1. 직접 실행: python app/main.py
2. uvicorn: uvicorn app.main:app --reload
3. 스크립트: python scripts/run_dev.py
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
# DEBUG 모드에서는 상세 로그, 프로덕션에서는 INFO 레벨로 설정
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
    
    [Startup 단계]
    1. Redis 연결 초기화
       - 세션 상태 (graph_state) 저장/로드
       - 턴 평가 로그 (turn_logs) 저장
       - 턴 메시지 매핑 (turn_mapping) 저장
    
    2. PostgreSQL 연결 초기화 (Spring Boot와 공유 DB)
       - 시험 정보 (exams)
       - 참가자 정보 (participants)
       - 제출 내역 (submissions)
    
    [Shutdown 단계]
    - 모든 DB 연결 정리
    - 리소스 해제
    
    [에러 처리]
    - Redis 연결 실패 시: 애플리케이션 시작 중단 (Redis는 필수)
    - PostgreSQL 연결 실패 시: 경고 로그만 출력 (읽기 전용으로 계속)
    """
    # ===== Startup =====
    logger.info("Starting AI Vibe Coding Test Worker...")
    
    # Redis 연결 (필수)
    try:
        await redis_client.connect()
        logger.info("Redis 연결 성공")
    except Exception as e:
        logger.error(f"Redis 연결 실패: {str(e)}")
        raise  # Redis는 필수이므로 실패 시 서버 시작 중단
    
    # PostgreSQL 연결 테스트 (선택)
    try:
        await init_db()
        logger.info("PostgreSQL 연결 성공")
    except Exception as e:
        # PostgreSQL은 선택 사항 (Spring Boot가 관리)
        logger.warning(f"PostgreSQL 연결 실패 (읽기 전용 모드로 계속): {str(e)}")
    
    logger.info(f"서버 시작 완료: http://{settings.API_HOST}:{settings.API_PORT}")
    
    yield  # 애플리케이션 실행
    
    # ===== Shutdown =====
    logger.info("Shutting down...")
    
    # 모든 연결 정리
    await redis_client.close()
    await close_db()
    
    logger.info("서버 종료 완료")


# ===== FastAPI 앱 생성 =====
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
- 프롬프트 활용 점수 (25%): 턴별 품질 + Chaining 전략
- 코드 성능 점수 (25%): 시간/공간 복잡도
- 코드 정확성 점수 (50%): 테스트 케이스 통과율
""",
    lifespan=lifespan,  # 라이프사이클 이벤트 핸들러
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc
    openapi_url="/openapi.json",  # OpenAPI 스키마
)


# ===== CORS 설정 =====
# Cross-Origin Resource Sharing 허용
# 프론트엔드가 다른 도메인에서 실행될 경우 필요
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: 프로덕션에서는 특정 도메인만 허용 (예: ["http://localhost:3000"])
    allow_credentials=True,  # 쿠키 허용
    allow_methods=["*"],  # 모든 HTTP 메소드 허용
    allow_headers=["*"],  # 모든 헤더 허용
)


# ===== 라우터 등록 =====
# 각 라우터는 특정 기능을 담당하는 API 엔드포인트 그룹
app.include_router(health_router)  # /health: 헬스 체크
app.include_router(chat_router, prefix="/api")  # /api/chat/*: 채팅 및 제출
app.include_router(session_router, prefix="/api")  # /api/session/*: 세션 관리


if __name__ == "__main__":
    """
    메인 실행 블록
    
    [사용법]
    python app/main.py
    
    [동작]
    - uvicorn 서버 시작
    - DEBUG 모드에서는 auto-reload 활성화 (코드 변경 시 자동 재시작)
    - 프로덕션 모드에서는 reload=False로 안정적 운영
    
    [대안]
    - scripts/run_dev.py: 개발용 스크립트 (권장)
    - uvicorn app.main:app --reload: 직접 uvicorn 실행
    """
    import uvicorn
    
    uvicorn.run(
        "app.main:app",  # 앱 경로 (모듈:변수명)
        host=settings.API_HOST,  # 바인딩 호스트 (기본: 0.0.0.0)
        port=settings.API_PORT,  # 포트 (기본: 8000)
        reload=settings.DEBUG,  # 코드 변경 시 자동 재시작 (개발 모드에서만)
        log_level="debug" if settings.DEBUG else "info",  # 로그 레벨
    )

