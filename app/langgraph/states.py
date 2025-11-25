"""
LangGraph 상태 정의
메인 그래프 및 서브그래프의 상태 타입
"""
from typing import Annotated, List, Optional, Dict, Any, Literal
from datetime import datetime

from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from app.db.models.enums import (
    WriterResponseStatus,
    IntentAnalyzerStatus,
    CodeIntentType,
)


# ===== 메인 그래프 상태 =====

class MainGraphState(TypedDict):
    """메인 그래프 상태"""
    # 세션 정보
    session_id: str
    exam_id: int
    participant_id: int
    spec_id: int
    
    # 메시지 히스토리
    messages: Annotated[list, add_messages]
    
    # 현재 턴 정보
    current_turn: int
    human_message: Optional[str]
    ai_message: Optional[str]
    
    # Intent Analyzer 결과
    intent_status: Optional[str]  # IntentAnalyzerStatus
    is_guardrail_failed: bool
    guardrail_message: Optional[str]
    
    # Writer LLM 결과
    writer_status: Optional[str]  # WriterResponseStatus
    writer_error: Optional[str]
    
    # 제출 상태
    is_submitted: bool
    submission_id: Optional[int]
    code_content: Optional[str]
    
    # 평가 점수
    turn_scores: Dict[str, Any]
    holistic_flow_score: Optional[float]
    aggregate_turn_score: Optional[float]
    code_performance_score: Optional[float]
    code_correctness_score: Optional[float]
    final_scores: Optional[Dict[str, float]]
    
    # 메모리 요약
    memory_summary: Optional[str]
    
    # 에러 처리
    error_message: Optional[str]
    retry_count: int
    
    # 메타데이터
    created_at: str
    updated_at: str


# ===== Eval Turn SubGraph 상태 =====

class EvalTurnState(TypedDict):
    """Eval Turn SubGraph 상태"""
    # 입력 데이터
    session_id: str
    turn: int
    human_message: str
    ai_message: str
    
    # Intent 분석 결과
    intent_type: Optional[str]  # CodeIntentType
    intent_confidence: float
    
    # 각 평가 결과
    rule_setting_eval: Optional[Dict[str, Any]]
    generation_eval: Optional[Dict[str, Any]]
    optimization_eval: Optional[Dict[str, Any]]
    debugging_eval: Optional[Dict[str, Any]]
    test_case_eval: Optional[Dict[str, Any]]
    hint_query_eval: Optional[Dict[str, Any]]
    follow_up_eval: Optional[Dict[str, Any]]
    
    # 답변 요약
    answer_summary: Optional[str]
    
    # 최종 턴 로그
    turn_log: Optional[Dict[str, Any]]
    turn_score: Optional[float]


# ===== Pydantic 모델 (LLM 구조화 출력용) =====

class IntentClassification(BaseModel):
    """Intent 분류 결과"""
    intent_type: CodeIntentType = Field(
        ...,
        description="분류된 코드 의도 타입"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="분류 신뢰도 (0-1)"
    )
    reasoning: str = Field(
        ...,
        description="분류 이유"
    )


class GuardrailCheck(BaseModel):
    """가드레일 검사 결과"""
    is_allowed: bool = Field(
        ...,
        description="요청이 허용되는지 여부"
    )
    violation_type: Optional[str] = Field(
        None,
        description="위반 유형 (있는 경우)"
    )
    message: Optional[str] = Field(
        None,
        description="사용자에게 전달할 메시지"
    )


class TurnEvaluation(BaseModel):
    """턴 평가 결과"""
    quality_score: float = Field(
        ...,
        ge=0.0,
        le=10.0,
        description="품질 점수 (0-10)"
    )
    relevance_score: float = Field(
        ...,
        ge=0.0,
        le=10.0,
        description="관련성 점수 (0-10)"
    )
    helpfulness_score: float = Field(
        ...,
        ge=0.0,
        le=10.0,
        description="유용성 점수 (0-10)"
    )
    feedback: str = Field(
        ...,
        description="평가 피드백"
    )


class CodeQualityEvaluation(BaseModel):
    """코드 품질 평가 결과"""
    correctness: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="정확성 점수 (0-100)"
    )
    efficiency: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="효율성 점수 (0-100)"
    )
    readability: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="가독성 점수 (0-100)"
    )
    best_practices: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="모범 사례 준수 점수 (0-100)"
    )
    detailed_feedback: str = Field(
        ...,
        description="상세 피드백"
    )


class HolisticFlowEvaluation(BaseModel):
    """전체 플로우 평가 결과"""
    strategy_coherence: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="전략 일관성 점수"
    )
    problem_solving_approach: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="문제 해결 접근법 점수"
    )
    iteration_quality: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="반복 개선 품질 점수"
    )
    overall_flow_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="전체 플로우 점수"
    )
    analysis: str = Field(
        ...,
        description="분석 내용"
    )


class FinalScoreAggregation(BaseModel):
    """최종 점수 집계"""
    prompt_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="프롬프트 활용 점수"
    )
    performance_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="성능 점수"
    )
    correctness_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="정확성 점수"
    )
    total_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="총점"
    )
    grade: str = Field(
        ...,
        description="등급 (A, B, C, D, F)"
    )
    summary: str = Field(
        ...,
        description="평가 요약"
    )



