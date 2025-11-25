"""
세션 관련 스키마
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


class SessionState(BaseModel):
    """세션 상태"""
    session_id: str = Field(..., description="세션 ID")
    exam_id: int = Field(..., description="시험 ID")
    participant_id: int = Field(..., description="참가자 ID")
    spec_id: int = Field(..., description="문제 스펙 ID")
    current_turn: int = Field(0, description="현재 턴")
    is_submitted: bool = Field(False, description="제출 여부")
    memory_summary: Optional[str] = Field(None, description="메모리 요약")
    created_at: str = Field(..., description="생성 시간")
    updated_at: str = Field(..., description="수정 시간")


class TurnScore(BaseModel):
    """턴 점수"""
    turn: int = Field(..., description="턴 번호")
    turn_score: float = Field(..., description="턴 점수")
    intent_type: Optional[str] = Field(None, description="의도 유형")
    timestamp: Optional[str] = Field(None, description="타임스탬프")


class SessionScores(BaseModel):
    """세션 점수"""
    session_id: str = Field(..., description="세션 ID")
    turns: Dict[str, TurnScore] = Field(default_factory=dict, description="턴별 점수")
    final: Optional[Dict[str, Any]] = Field(None, description="최종 점수")
    updated_at: Optional[str] = Field(None, description="수정 시간")
    completed_at: Optional[str] = Field(None, description="완료 시간")


class Message(BaseModel):
    """메시지"""
    role: str = Field(..., description="역할 (user/assistant)")
    content: str = Field(..., description="내용")


class ConversationHistory(BaseModel):
    """대화 히스토리"""
    session_id: str = Field(..., description="세션 ID")
    messages: List[Message] = Field(default_factory=list, description="메시지 목록")
    total_messages: int = Field(0, description="총 메시지 수")



