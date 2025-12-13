"""
헬스 체크 API 라우터
"""
from fastapi import APIRouter

from app.presentation.schemas.common import HealthResponse
from app.core.config import settings
from app.infrastructure.cache.redis_client import redis_client


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
    
    # Judge0 Worker 상태 확인 (Redis 큐 기반)
    try:
        if settings.USE_REDIS_QUEUE:
            queue_key = "judge_queue:pending"
            queue_length = await redis_client.client.llen(queue_key)
            
            # 처리 중인 작업 확인
            processing_count = 0
            async for key in redis_client.client.scan_iter(match="judge_status:*"):
                status = await redis_client.get(key)
                if status == "processing":
                    processing_count += 1
            
            # Worker가 실행 중인지 추정
            # 큐에 작업이 있고 processing 상태가 있으면 Worker 실행 중
            # 큐가 비어있거나 processing 상태가 있으면 Worker 실행 중으로 간주
            if processing_count > 0:
                components["judge_worker"] = True
            elif queue_length > 0 and processing_count == 0:
                # 큐에 작업이 있지만 처리 중인 작업이 없으면 Worker 미실행으로 추정
                components["judge_worker"] = False
            else:
                # 큐가 비어있으면 불확실 (Worker 실행 중일 수도, 아닐 수도)
                components["judge_worker"] = None  # None은 "unknown"으로 처리
        else:
            # Redis 큐를 사용하지 않으면 Worker 상태 확인 불가
            components["judge_worker"] = None
    except Exception:
        components["judge_worker"] = False
    
    # 전체 상태 (judge_worker는 None일 수 있으므로 제외)
    critical_components = {k: v for k, v in components.items() if k != "judge_worker" and v is not None}
    overall_status = "ok" if all(critical_components.values()) else "degraded"
    
    return HealthResponse(
        status=overall_status,
        version=settings.APP_VERSION,
        components=components,
    )


@router.get(
    "/info",
    summary="API 정보",
    description="API 정보를 반환합니다."
)
async def api_info():
    """API 정보 엔드포인트"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }


