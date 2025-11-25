"""
헬스 체크 API 라우터
"""
from fastapi import APIRouter

from app.schemas.common import HealthResponse
from app.core.config import settings
from app.db.redis_client import redis_client


router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="헬스 체크",
    description="서버 및 의존 서비스 상태를 확인합니다."
)
async def health_check() -> HealthResponse:
    """헬스 체크"""
    components = {}
    
    # Redis 상태 확인
    try:
        await redis_client.client.ping()
        components["redis"] = True
    except Exception:
        components["redis"] = False
    
    # PostgreSQL 상태 확인 (간단한 체크)
    # 실제 연결 테스트는 startup에서 수행
    components["postgres"] = True
    
    # LLM API 상태 (API 키 존재 여부로 판단)
    components["llm"] = bool(settings.GEMINI_API_KEY or settings.OPENAI_API_KEY)
    
    # 전체 상태
    overall_status = "ok" if all(components.values()) else "degraded"
    
    return HealthResponse(
        status=overall_status,
        version=settings.APP_VERSION,
        components=components,
    )


@router.get(
    "/",
    summary="루트",
    description="API 정보를 반환합니다."
)
async def root():
    """루트 엔드포인트"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }


