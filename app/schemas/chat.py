"""
채팅 관련 스키마
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class ChatRequest(BaseModel):
    """채팅 요청"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "session-123",
                "exam_id": 1,
                "participant_id": 100,
                "spec_id": 10,
                "message": "피보나치 수열을 계산하는 함수를 작성해주세요."
            }
        }
    )
    
    session_id: str = Field(..., description="세션 ID")
    exam_id: int = Field(..., description="시험 ID")
    participant_id: int = Field(..., description="참가자 ID")
    spec_id: int = Field(..., description="문제 스펙 ID")
    message: str = Field(..., description="사용자 메시지")


class ChatResponse(BaseModel):
    """채팅 응답"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "session-123",
                "turn": 1,
                "ai_message": "피보나치 수열을 계산하는 함수입니다:\n\n```python\ndef fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)\n```",
                "is_submitted": False,
                "error": False,
                "error_message": None
            }
        }
    )
    
    session_id: str = Field(..., description="세션 ID")
    turn: int = Field(..., description="턴 번호")
    ai_message: Optional[str] = Field(None, description="AI 응답 메시지")
    is_submitted: bool = Field(False, description="제출 여부")
    error: bool = Field(False, description="에러 발생 여부")
    error_message: Optional[str] = Field(None, description="에러 메시지")


class SubmitRequest(BaseModel):
    """코드 제출 요청"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "session-123",
                "exam_id": 1,
                "participant_id": 100,
                "spec_id": 10,
                "code": "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)",
                "lang": "python"
            }
        }
    )
    
    session_id: str = Field(..., description="세션 ID")
    exam_id: int = Field(..., description="시험 ID")
    participant_id: int = Field(..., description="참가자 ID")
    spec_id: int = Field(..., description="문제 스펙 ID")
    code: str = Field(..., description="제출 코드")
    lang: str = Field("python", description="프로그래밍 언어")


class FinalScores(BaseModel):
    """최종 점수"""
    prompt_score: float = Field(..., description="프롬프트 점수 (0-100)")
    performance_score: float = Field(..., description="성능 점수 (0-100)")
    correctness_score: float = Field(..., description="정확성 점수 (0-100)")
    total_score: float = Field(..., description="총점 (0-100)")
    grade: str = Field(..., description="등급 (A/B/C/D/F)")


class SubmitResponse(BaseModel):
    """코드 제출 응답"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "session-123",
                "submission_id": 1,
                "is_submitted": True,
                "final_scores": {
                    "prompt_score": 85.5,
                    "performance_score": 78.0,
                    "correctness_score": 92.0,
                    "total_score": 86.38,
                    "grade": "B"
                },
                "turn_scores": {
                    "1": {"turn_score": 82.0},
                    "2": {"turn_score": 88.0}
                },
                "error": False,
                "error_message": None
            }
        }
    )
    
    session_id: str = Field(..., description="세션 ID")
    submission_id: Optional[int] = Field(None, description="제출 ID")
    is_submitted: bool = Field(True, description="제출 완료 여부")
    final_scores: Optional[FinalScores] = Field(None, description="최종 점수")
    turn_scores: Optional[Dict[str, Any]] = Field(None, description="턴별 점수")
    error: bool = Field(False, description="에러 발생 여부")
    error_message: Optional[str] = Field(None, description="에러 메시지")



