"""
토큰 사용량 관련 스키마
"""
from typing import Optional, Dict
from pydantic import BaseModel, Field, ConfigDict


class TokenUsage(BaseModel):
    """토큰 사용량 (Core 전달용)"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "prompt_tokens": 1500,
                "completion_tokens": 2000,
                "total_tokens": 3500
            }
        }
    )
    
    prompt_tokens: int = Field(..., description="프롬프트 토큰 수", ge=0)
    completion_tokens: int = Field(..., description="컴플리션 토큰 수", ge=0)
    total_tokens: int = Field(..., description="전체 토큰 수", ge=0)


class TokenUsageResponse(BaseModel):
    """토큰 사용량 조회 응답"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "session-123",
                "chat_tokens": {
                    "prompt_tokens": 1500,
                    "completion_tokens": 2000,
                    "total_tokens": 3500
                },
                "eval_tokens": {
                    "prompt_tokens": 3000,
                    "completion_tokens": 4000,
                    "total_tokens": 7000
                },
                "total_tokens": {
                    "prompt_tokens": 4500,
                    "completion_tokens": 6000,
                    "total_tokens": 10500
                },
                "error": False
            }
        }
    )
    
    session_id: str = Field(..., description="세션 ID")
    chat_tokens: Optional[TokenUsage] = Field(None, description="채팅 검사 토큰 사용량 (Intent Analyzer, Writer LLM)")
    eval_tokens: Optional[TokenUsage] = Field(None, description="평가 토큰 사용량 (Turn Evaluator, Holistic Evaluator)")
    total_tokens: Optional[TokenUsage] = Field(None, description="전체 토큰 사용량 (chat + eval 합계)")
    error: bool = Field(False, description="에러 발생 여부")
    error_message: Optional[str] = Field(None, description="에러 메시지")
















