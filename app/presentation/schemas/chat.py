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
                "error_message": None,
                "chat_tokens": {
                    "prompt_tokens": 150,
                    "completion_tokens": 200,
                    "total_tokens": 350
                },
                "eval_tokens": {
                    "prompt_tokens": 300,
                    "completion_tokens": 400,
                    "total_tokens": 700
                }
            }
        }
    )
    
    session_id: str = Field(..., description="세션 ID")
    turn: int = Field(..., description="턴 번호")
    ai_message: Optional[str] = Field(None, description="AI 응답 메시지")
    is_submitted: bool = Field(False, description="제출 여부")
    error: bool = Field(False, description="에러 발생 여부")
    error_message: Optional[str] = Field(None, description="에러 메시지")
    chat_tokens: Optional[Dict[str, int]] = Field(None, description="채팅 검사 토큰 사용량 (Intent Analyzer, Writer LLM)")
    eval_tokens: Optional[Dict[str, int]] = Field(None, description="평가 토큰 사용량 (Turn Evaluator, Holistic Evaluator)")
    total_tokens: Optional[Dict[str, int]] = Field(None, description="전체 토큰 사용량 (chat + eval 합계, Core 전달용)")


class SubmitRequest(BaseModel):
    """코드 제출 요청 (레거시 - 주석처리 예정)"""
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


class SubmitCodeRequest(BaseModel):
    """코드 제출 요청 (신규)"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "examId": 1,
                "participantId": 1,
                "problemId": 1,
                "specId": 1,
                "finalCode": "def solve():\n    print('hello')",
                "language": "python3.11",
                "submissionId": 88001
            }
        }
    )
    
    examId: int = Field(..., description="시험 ID")
    participantId: int = Field(..., description="참가자 ID (participants.id)")
    problemId: int = Field(..., description="문제 ID")
    specId: int = Field(..., description="스펙 ID (problem_specs.id)")
    finalCode: str = Field(..., description="제출 코드")
    language: str = Field(..., description="프로그래밍 언어 (예: python3.11)")
    submissionId: int = Field(..., description="제출 ID (백엔드에서 생성)")


class FinalScores(BaseModel):
    """최종 점수"""
    prompt_score: float = Field(..., description="프롬프트 점수 (0-100)")
    performance_score: float = Field(..., description="성능 점수 (0-100)")
    correctness_score: float = Field(..., description="정확성 점수 (0-100)")
    total_score: float = Field(..., description="총점 (0-100)")
    grade: str = Field(..., description="등급 (A/B/C/D/F)")


class EvaluationFeedback(BaseModel):
    """평가 피드백"""
    holistic_flow_analysis: Optional[str] = Field(None, description="체이닝 전략에 대한 상세 분석 (문제 분해, 피드백 수용성, 주도성, 전략적 탐색)")


class SubmitResponse(BaseModel):
    """코드 제출 응답 (레거시 - 주석처리 예정)"""
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
    feedback: Optional[EvaluationFeedback] = Field(None, description="평가 피드백 (체이닝 전략 분석 등)")
    chat_tokens: Optional[Dict[str, int]] = Field(None, description="채팅 검사 토큰 사용량 (Intent Analyzer, Writer LLM)")
    eval_tokens: Optional[Dict[str, int]] = Field(None, description="평가 토큰 사용량 (Turn Evaluator, Holistic Evaluator)")
    error: bool = Field(False, description="에러 발생 여부")
    error_message: Optional[str] = Field(None, description="에러 메시지")


class SubmitCodeResponse(BaseModel):
    """코드 제출 응답 (신규)"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "submissionId": 88001,
                "status": "successed"
            }
        }
    )
    
    submissionId: int = Field(..., description="제출 ID")
    status: str = Field(..., description="처리 상태 (successed 또는 failed)")


class SaveChatMessageRequest(BaseModel):
    """Spring Boot에서 메시지 저장 요청"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "examId": 1,
                "participantId": 1,
                "turn": 1,
                "role": "user",
                "content": "안녕하세요",
                "tokenCount": 10,
                "meta": "{\"key\": \"value\"}"
            }
        }
    )
    
    examId: int = Field(..., description="시험 ID", alias="examId")
    participantId: int = Field(..., description="참가자 ID", alias="participantId")
    turn: int = Field(..., description="턴 번호")
    role: str = Field(..., description="역할 (user, assistant)")
    content: str = Field(..., description="메시지 내용")
    tokenCount: Optional[int] = Field(None, description="토큰 사용량", alias="tokenCount")
    meta: Optional[str] = Field(None, description="메타데이터 (JSON 문자열)")


class SaveChatMessageResponse(BaseModel):
    """메시지 저장 응답"""
    session_id: int = Field(..., description="세션 ID")
    message_id: int = Field(..., description="메시지 ID")
    success: bool = Field(True, description="저장 성공 여부")
    error_message: Optional[str] = Field(None, description="에러 메시지")


# ===== 신규 API 스키마 (2024-12-07) =====

class ProblemContext(BaseModel):
    """문제 컨텍스트"""
    problemId: int = Field(..., description="문제 ID", alias="problemId")
    specVersion: int = Field(..., description="스펙 버전", alias="specVersion")


class ChatMessagesRequest(BaseModel):
    """메시지 전송 요청 (신규)"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sessionId": 1,
                "participantId": 1,
                "turnId": 1,
                "role": "USER",
                "content": "이 문제를 DP로 푸는 힌트를 줘",
                "context": {
                    "problemId": 1,
                    "specVersion": 1
                }
            }
        }
    )
    
    sessionId: int = Field(..., description="세션 ID", alias="sessionId")
    participantId: int = Field(..., description="참가자 ID (participants.id)", alias="participantId")
    turnId: int = Field(..., description="DB의 prompt_messages.turn", alias="turnId")
    role: str = Field(..., description="역할 (USER)")
    content: str = Field(..., description="메시지 내용")
    context: ProblemContext = Field(..., description="문제 컨텍스트")


class AIMessageInfo(BaseModel):
    """AI 메시지 정보"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sessionId": 1,
                "turn": 2,
                "role": "AI",
                "content": "다음은 문제 조건입니다...",
                "tokenCount": 120,
                "totalToken": 135
            }
        }
    )
    
    sessionId: int = Field(..., description="세션 ID", alias="sessionId")
    turn: int = Field(..., description="AI 응답 턴 (이전 대화 Turn + 1)")
    role: str = Field("AI", description="역할")
    content: str = Field(..., description="LLM이 생성한 응답")
    tokenCount: int = Field(..., description="현재 턴 대화 토큰 (사용자 메시지 + AI 응답)", alias="tokenCount")
    totalToken: int = Field(..., description="한 세션의 모든 대화 token_count의 합", alias="totalToken")


class ChatMessagesResponse(BaseModel):
    """메시지 전송 응답 (신규)"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "aiMessage": {
                    "sessionId": 1,
                    "turn": 2,
                    "role": "AI",
                    "content": "다음은 문제 조건입니다...",
                    "tokenCount": 120,
                    "totalToken": 135
                }
            }
        }
    )
    
    aiMessage: AIMessageInfo = Field(..., description="AI 응답 메시지")



