"""
보안 관련 유틸리티
API 키 검증, Spring Boot 통신 인증 등
"""

from typing import Optional

from fastapi import Header, HTTPException, status

from app.core.config import settings


async def verify_spring_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> bool:
    """Spring Boot에서 오는 요청의 API 키 검증"""
    if settings.SPRING_API_KEY is None:
        # API 키가 설정되지 않은 경우 검증 스킵 (개발 환경)
        return True

    if x_api_key is None or x_api_key != settings.SPRING_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return True


async def verify_internal_request(
    x_internal_token: Optional[str] = Header(None, alias="X-Internal-Token")
) -> bool:
    """내부 서비스 간 통신 검증"""
    # 개발 환경에서는 검증 스킵
    if settings.DEBUG:
        return True

    # 프로덕션에서는 토큰 검증 로직 추가
    return True
