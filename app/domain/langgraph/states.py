"""
LangGraph 상태 정의
메인 그래프 및 서브그래프의 상태 타입
"""
from typing import Annotated, List, Optional, Dict, Any, Literal
from datetime import datetime

from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from app.infrastructure.persistence.models.enums import (
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
    
    # 문제 정보 (하드코딩 또는 DB에서 가져옴)
    problem_id: Optional[str]  # 문제 번호 (백준 등) - 하위 호환성 유지
    problem_name: Optional[str]  # 문제 이름 - 하위 호환성 유지
    problem_algorithm: Optional[str]  # 알고리즘 유형 - 하위 호환성 유지
    problem_keywords: Optional[List[str]]  # 가드레일용 문제별 키워드 - 하위 호환성 유지
    problem_context: Optional[Dict[str, Any]]  # 상세한 문제 정보 (basic_info, constraints, ai_guide, solution_code 포함)
    
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
    guide_strategy: Optional[str]  # SYNTAX_GUIDE, LOGIC_HINT, ROADMAP, GENERATION
    keywords: Optional[List[str]]  # 사용자 질문의 핵심 키워드
    
    # Writer LLM 결과
    writer_status: Optional[str]  # WriterResponseStatus
    writer_error: Optional[str]
    
    # 제출 상태
    is_submitted: bool
    submission_id: Optional[int]
    code_content: Optional[str]
    lang: Optional[str]  # 프로그래밍 언어 (python, java, cpp 등)
    
    # 평가 점수
    turn_scores: Dict[str, Any]
    holistic_flow_score: Optional[float]
    holistic_flow_analysis: Optional[str]  # 체이닝 전략에 대한 상세 분석
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
    
    # LangSmith 추적 제어 (Optional, None이면 환경 변수 사용)
    enable_langsmith_tracing: Optional[bool]
    
    # 토큰 사용량 (채팅 검사 vs 평가 분리)
    chat_tokens: Optional[Dict[str, int]]  # 사용자 채팅 검사 토큰 (Intent Analyzer + Writer LLM)
    eval_tokens: Optional[Dict[str, int]]  # 평가 토큰 (Eval Turn SubGraph + Holistic Evaluators)


# ===== Eval Turn SubGraph 상태 =====

class EvalTurnState(TypedDict):
    """Eval Turn SubGraph 상태 (사용자 프롬프트 평가)"""
    # 입력 데이터
    session_id: str
    turn: int
    human_message: str
    ai_message: str
    
    # 문제 정보 (평가 시 문제 적절성 판단용)
    problem_context: Optional[Dict[str, Any]]
    
    # Guardrail 정보 (eval_service에서 전달)
    is_guardrail_failed: bool
    guardrail_message: Optional[str]
    
    # Intent 분석 결과 (복수 의도 지원)
    intent_types: Optional[list[str]]  # CodeIntentType 목록
    intent_confidence: float
    
    # 8가지 의도별 평가 결과
    system_prompt_eval: Optional[Dict[str, Any]]  # 신규 추가
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
    
    # 토큰 사용량 (평가용)
    eval_tokens: Optional[Dict[str, int]]  # 평가 토큰 (Eval Turn SubGraph)


# ===== Pydantic 모델 (LLM 구조화 출력용) =====

class IntentClassification(BaseModel):
    """Intent 분류 결과 (복수 의도 지원)"""
    intent_types: list[CodeIntentType] = Field(
        ...,
        description="분류된 코드 의도 타입 목록 (복수 선택 가능)"
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


class Rubric(BaseModel):
    """평가 루브릭 (단일 기준)"""
    criterion: str = Field(
        ...,
        description="평가 기준 (예: 명확성, 예시 사용, 규칙 명시)"
    )
    score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="해당 기준의 점수 (0-100)"
    )
    reasoning: str = Field(
        ...,
        description="해당 기준에 대한 평가 근거"
    )


class TurnEvaluation(BaseModel):
    """턴 평가 결과 (Claude Prompt Engineering 기준)"""
    intent: str = Field(
        ...,
        description="분류된 의도 (GENERATION, OPTIMIZATION, DEBUGGING 등)"
    )
    score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="전체 점수 (0-100)"
    )
    rubrics: list[Rubric] = Field(
        default_factory=list,
        description="평가 루브릭 목록 (명확성, 예시, 규칙, 사고 연쇄)"
    )
    final_reasoning: str = Field(
        ...,
        description="전체 평가 근거 및 요약"
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
    problem_decomposition: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="문제 분해 점수 (항목 1)"
    )
    feedback_integration: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="피드백 수용성 점수 (항목 2)"
    )
    strategic_exploration: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="전략적 탐색 점수 (항목 4)"
    )
    overall_flow_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="전체 플로우 점수 (종합 점수)"
    )
    analysis: str = Field(
        ...,
        description="상세 분석 내용 (주도성 및 오류 수정, 고급 프롬프트 기법 포함)"
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



