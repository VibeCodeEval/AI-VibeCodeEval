"""
공통 스키마
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class HealthResponse(BaseModel):
    """헬스 체크 응답"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "ok",
                "version": "0.1.0",
                "components": {
                    "redis": True,
                    "postgres": True,
                    "llm": True
                }
            }
        }
    )
    
    status: str = Field("ok", description="상태")
    version: str = Field(..., description="버전")
    components: Dict[str, bool] = Field(
        default_factory=dict, 
        description="컴포넌트 상태"
    )


class ErrorResponse(BaseModel):
    """에러 응답"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": True,
                "error_code": "INVALID_SESSION",
                "error_message": "세션을 찾을 수 없습니다.",
                "details": {
                    "session_id": "invalid-session-id"
                }
            }
        }
    )
    
    error: bool = Field(True, description="에러 여부")
    error_code: str = Field(..., description="에러 코드")
    error_message: str = Field(..., description="에러 메시지")
    details: Optional[Dict[str, Any]] = Field(None, description="상세 정보")



