"""
LangGraph 상태 정의
메인 그래프 및 서브그래프의 상태 타입
"""

import operator
from datetime import datetime
from typing import Annotated, Any, Dict, List, Literal, Optional

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from app.infrastructure.persistence.models.enums import (CodeIntentType,
                                                         IntentAnalyzerStatus,
                                                         UnifiedIntentType,
                                                         WriterResponseStatus)

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
    problem_context: Optional[
        Dict[str, Any]
    ]  # 상세한 문제 정보 (basic_info, constraints, ai_guide, solution_code 포함)

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
    # Intent 노드가 chat_tokens에 사용자 프롬프트(tiktoken)를 이미 누적했는지 (Writer 이중 카운트 방지)
    intent_llm_ran: Optional[bool]

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
    # N8 FinalVerdict: R4 대화 맥락 유지 (turn_scores 궤적 기반, N9 prompt_score에 반영)
    r4_context_maintenance_score: Optional[float]
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
    chat_tokens: Optional[
        Dict[str, int]
    ]  # 사용자 채팅 검사 토큰 (Intent Analyzer + Writer LLM)
    eval_tokens: Optional[
        Dict[str, int]
    ]  # 평가 토큰 (Eval Turn SubGraph + Holistic Evaluators)

    # Phase 6: AST 기반 코드 생성 시스템
    spec_result: Optional[Dict[str, Any]]  # Spec Extractor 결과
    ast_analysis: Optional[Dict[str, Any]]  # AST Analyzer 결과
    modification_plan: Optional[Dict[str, Any]]  # Spec-AST 매핑 결과
    modified_code: Optional[str]  # Error Injector가 생성한 변형 코드
    injection_result: Optional[Dict[str, Any]]  # 전체 Injection 결과

    # Phase 6B: Spec 중심 통합 평가 시스템
    turn_analysis: Optional[Dict[str, Any]]  # 현재 턴의 TurnAnalysis 결과
    integrated_score: Optional[float]  # 통합 평가 점수 (제출 시)
    integrated_evaluation: Optional[Dict[str, Any]]  # 통합 평가 상세 결과

    # Phase 6E: 평가 파이프라인 재설계 (N5~N8)
    code_quality_metrics: Optional[Dict[str, Any]]  # N6: Radon CC 등 정적 분석
    code_eval_report: Optional[Dict[str, Any]]      # N7: 코드 리뷰 에이전트 결과
    debate_log: Optional[List[Dict[str, Any]]]      # N8: 다중 에이전트 토론 전체 기록
    debate_initial_opinions: Optional[List[Dict[str, Any]]]  # N8 Round1
    debate_rebuttals: Optional[List[Dict[str, Any]]]  # N8 Round2

    # v2.1 Snapshot: Phase 1 확정 / 최종 제출 코드 추적
    v1_code: Optional[str]  # Phase 1 SAVE로 확정된 Baseline 코드
    v2_code: Optional[str]  # 최종 제출 시점의 Final 코드
    v1_metrics: Optional[Dict[str, Any]]  # v1_code 분석 결과 (예: Radon CC 등)
    v2_metrics: Optional[Dict[str, Any]]  # v2_code 분석 결과 (예: Radon CC, AST 패턴 등)


# ===== Debate SubGraph 상태 =====


class DebateState(TypedDict):
    """N8 다중 에이전트 토론 SubGraph 상태"""

    # 입력 컨텍스트 (MainGraphState에서 전달)
    session_id: str
    problem_context: Optional[Dict[str, Any]]
    code_content: Optional[str]

    # N4 — 턴별 숫자 점수 (MainGraphState.turn_scores)
    turn_scores: Optional[Dict[str, Any]]
    aggregate_turn_score: Optional[float]

    # N4 — 턴별 전체 평가 내용 (Redis에서 읽은 detailed_turn_log)
    # 구조: {turn_key: {user_prompt_summary, llm_answer_summary, prompt_evaluation_details}}
    turn_logs: Optional[Dict[str, Any]]

    # N5 — Judge0 점수 + 실행 상세
    code_correctness_score: Optional[float]
    code_performance_score: Optional[float]
    test_cases_passed: Optional[int]
    test_cases_total: Optional[int]
    execution_time: Optional[float]
    memory_used_mb: Optional[float]
    correctness_reasoning: Optional[str]

    # N6 — Radon CC 정적 분석
    code_quality_metrics: Optional[Dict[str, Any]]

    # N7 — LLM 코드 리뷰 전문
    code_eval_report: Optional[Dict[str, Any]]

    # 토론 누적 (operator.add: 병렬 팬인 시 자동 병합)
    initial_opinions: Annotated[List[Dict[str, Any]], operator.add]  # Round 1 병렬
    rebuttals: Annotated[List[Dict[str, Any]], operator.add]          # Round 2 순차

    # 최종 출력 (MainGraphState.holistic_flow_score / holistic_flow_analysis로 반환)
    holistic_flow_score: Optional[float]
    r4_context_maintenance_score: Optional[float]
    holistic_flow_analysis: Optional[str]
    debate_log: Optional[List[Dict[str, Any]]]


# ===== Eval Turn SubGraph 상태 =====


class EvalTurnState(TypedDict):
    """Eval Turn SubGraph 상태 (사용자 프롬프트 평가)"""

    # 입력 데이터
    session_id: str
    turn: int
    human_message: str
    ai_message: str

    # 이전 턴 대화 요약 (V2.2 Context-Integrated: 턴 N 평가 시 1~N-1 요약)
    previous_turns_summary: Optional[str]

    # Phase 2 첫 지시 여부 (SAVE 직후 턴 → 문맥 감점 없음)
    is_phase2_first_turn: Optional[bool]

    # 문제 정보 (평가 시 문제 적절성 판단용)
    problem_context: Optional[Dict[str, Any]]

    # Guardrail 정보 (eval_service에서 전달)
    is_guardrail_failed: bool
    guardrail_message: Optional[str]

    # Intent 분석 결과 (복수 의도 지원)
    intent_types: Optional[list[str]]  # CodeIntentType 목록
    intent_confidence: float
    unified_intent: Optional[str]  # v2.3 6대 통합 의도 (SETTING/CREATION/REFINEMENT/DEBUGGING/EXPLORATION/FOLLOW_UP)

    # 8가지 의도별 평가 결과
    system_prompt_eval: Optional[Dict[str, Any]]  # 신규 추가
    rule_setting_eval: Optional[Dict[str, Any]]
    generation_eval: Optional[Dict[str, Any]]
    optimization_eval: Optional[Dict[str, Any]]
    debugging_eval: Optional[Dict[str, Any]]
    test_case_eval: Optional[Dict[str, Any]]
    hint_query_eval: Optional[Dict[str, Any]]
    exploration_eval: Optional[Dict[str, Any]]
    follow_up_eval: Optional[Dict[str, Any]]

    # 답변 요약
    answer_summary: Optional[str]

    # 최종 턴 로그
    turn_log: Optional[Dict[str, Any]]
    turn_score: Optional[float]

    # 토큰 사용량 (평가용)
    eval_tokens: Optional[Dict[str, int]]  # 평가 토큰 (Eval Turn SubGraph)


# ===== Pydantic 모델 (LLM 구조화 출력용) =====


class PromptCharacteristics(BaseModel):
    """1단계: 사용자 프롬프트 특성만 추출 (의도 라벨 금지)"""

    has_code_snippet: bool = Field(
        ...,
        description="사용자 메시지에 실행·수정 대상이 되는 코드 블록 또는 의미 있는 코드 조각이 포함되는가",
    )
    is_error_reported: bool = Field(
        ...,
        description="Traceback, 스택, 에러 메시지, '왜 안 돼', 실패 증상 등 실행 오류·버그를 보고하는가",
    )
    is_asking_for_concept: bool = Field(
        ...,
        description="알고리즘 정의, 개념 비교, 도구/라이브러리 설명 등 코드 작성 없이 지식·이해를 묻는가",
    )
    is_requesting_new_code: bool = Field(
        ...,
        description="새 코드 작성, 기존 코드 수정·리팩터, 최적화, 테스트 추가 등 결과물로 코드를 바꾸거나 만들어 달라는 요청인가",
    )


class IntentClassification(BaseModel):
    """Intent 분류 결과 (V2.3: 6대 통합 의도 단일 선택)"""

    intent_types: list[UnifiedIntentType] = Field(
        ...,
        description="6대 통합 의도 중 하나: SETTING, CREATION, REFINEMENT, DEBUGGING, EXPLORATION, FOLLOW_UP",
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="분류 신뢰도 (0-1)")
    reasoning: Optional[str] = Field(None, description="분류 이유")


class GuardrailCheck(BaseModel):
    """가드레일 검사 결과"""

    is_allowed: bool = Field(..., description="요청이 허용되는지 여부")
    violation_type: Optional[str] = Field(None, description="위반 유형 (있는 경우)")
    message: Optional[str] = Field(None, description="사용자에게 전달할 메시지")


class Rubric(BaseModel):
    """평가 루브릭 (단일 기준)"""

    criterion: str = Field(
        ..., description="평가 기준 (예: 명확성, 예시 사용, 규칙 명시)"
    )
    score: float = Field(..., ge=0.0, le=100.0, description="해당 기준의 점수 (0-100)")
    reasoning: str = Field(..., description="해당 기준에 대한 평가 근거")


class TurnEvaluation(BaseModel):
    """턴 평가 결과 (Claude Prompt Engineering 기준)"""

    intent: str = Field(
        ..., description="분류된 의도 (GENERATION, OPTIMIZATION, DEBUGGING 등)"
    )
    score: float = Field(..., ge=0.0, le=100.0, description="전체 점수 (0-100)")
    rubrics: list[Rubric] = Field(
        default_factory=list,
        description="평가 루브릭 목록 (명확성, 예시, 규칙, 사고 연쇄)",
    )
    final_reasoning: str = Field(..., description="전체 평가 근거 및 요약")


class CodeQualityEvaluation(BaseModel):
    """코드 품질 평가 결과"""

    correctness: float = Field(..., ge=0.0, le=100.0, description="정확성 점수 (0-100)")
    efficiency: float = Field(..., ge=0.0, le=100.0, description="효율성 점수 (0-100)")
    readability: float = Field(..., ge=0.0, le=100.0, description="가독성 점수 (0-100)")
    best_practices: float = Field(
        ..., ge=0.0, le=100.0, description="모범 사례 준수 점수 (0-100)"
    )
    detailed_feedback: str = Field(..., description="상세 피드백")


class HolisticFlowEvaluation(BaseModel):
    """전체 플로우 평가 결과 (V2.3: 1~5 정수, 외부에서 0~100 환산)"""

    problem_decomposition: int = Field(
        ..., ge=1, le=5, description="문제 분해 점수 (1~5 정수)"
    )
    feedback_integration: int = Field(
        ..., ge=1, le=5, description="피드백 수용성 점수 (1~5 정수)"
    )
    strategic_exploration: int = Field(
        ..., ge=1, le=5, description="전략적 탐색 및 관리 점수 (1~5 정수)"
    )
    overall_flow_score: int = Field(
        ..., ge=1, le=5, description="종합 점수 (1~5 정수, Holistic Impression)"
    )
    analysis: str = Field(
        ..., description="상세 분석 (위임 전략·고급 기법·주도성 포함)"
    )


class FinalScoreAggregation(BaseModel):
    """최종 점수 집계"""

    prompt_score: float = Field(..., ge=0.0, le=100.0, description="프롬프트 활용 점수")
    performance_score: float = Field(..., ge=0.0, le=100.0, description="성능 점수")
    correctness_score: float = Field(..., ge=0.0, le=100.0, description="정확성 점수")
    total_score: float = Field(..., ge=0.0, le=100.0, description="총점")
    grade: str = Field(..., description="등급 (A, B, C, D, F)")
    summary: str = Field(..., description="평가 요약")


# ===== Phase 6B: Spec 중심 통합 평가 모델 =====


class MissingSpecDetail(BaseModel):
    """누락된 Spec 상세 정보"""

    category: str = Field(..., description="누락된 요구사항 카테고리 (예: 비트마스킹, 기저조건)")
    importance: str = Field(
        ..., description="중요도 (HIGH, MEDIUM, LOW)"
    )
    related_component: Optional[str] = Field(
        None, description="관련 코드 컴포넌트 (예: BIT_OPERATION)"
    )


class TurnAnalysis(BaseModel):
    """
    턴별 분석 결과 (Spec 중심 통합 평가용)
    
    대화 중 매 턴마다 생성되어 prompt_messages.meta에 저장됨.
    제출 시 모든 턴의 TurnAnalysis를 조회하여 통합 평가 수행.
    """

    turn: int = Field(..., description="턴 번호")
    is_first_prompt: bool = Field(..., description="첫 프롬프트 여부")

    # Spec 분석 (from Spec Extractor)
    spec_completeness: float = Field(
        ..., ge=0.0, le=100.0, description="Spec 완전성 점수 (0-100)"
    )
    specified_specs: List[str] = Field(
        default_factory=list, description="명시된 요구사항 목록"
    )
    missing_specs: List[MissingSpecDetail] = Field(
        default_factory=list, description="누락된 요구사항 목록"
    )
    ambiguous_specs: List[str] = Field(
        default_factory=list, description="모호한 요구사항 목록"
    )

    # 표현 품질 지표
    clarity_score: float = Field(
        ..., ge=0.0, le=100.0, description="명확성 점수 (0-100)"
    )
    has_structure: bool = Field(
        ..., description="구조화 여부 (XML 태그, 마크다운, 리스트 등)"
    )
    has_examples: bool = Field(
        ..., description="예시 포함 여부 (I/O 예시, 엣지 케이스)"
    )
    has_specific_values: bool = Field(
        ..., description="구체적 값 포함 여부 (숫자, 조건, 제약)"
    )

    # 맥락 연결 (후속 턴용)
    spec_recovery_count: int = Field(
        default=0, description="이번 턴에서 회복한 Spec 수"
    )
    references_previous: bool = Field(
        default=False, description="이전 턴 참조 여부"
    )
    recovered_specs: List[str] = Field(
        default_factory=list, description="이번 턴에서 회복한 Spec 목록"
    )

    # 요약
    summary: str = Field(
        ..., max_length=150, description="프롬프트 요약 (최대 150자)"
    )

    # 표현 품질 종합 점수 (계산됨)
    @property
    def expression_score(self) -> float:
        """표현 품질 종합 점수 계산"""
        structure_bonus = 30 if self.has_structure else 0
        examples_bonus = 35 if self.has_examples else 0
        values_bonus = 35 if self.has_specific_values else 0
        return min(100.0, self.clarity_score * 0.5 + structure_bonus + examples_bonus + values_bonus)


class SessionAnalysis(BaseModel):
    """
    세션 전체 분석 결과 (제출 시 생성)
    
    모든 턴의 TurnAnalysis를 집계하여 통합 평가에 사용.
    """

    session_id: str = Field(..., description="세션 ID")
    total_turns: int = Field(..., description="총 턴 수")
    turn_analyses: List[TurnAnalysis] = Field(
        default_factory=list, description="턴별 분석 결과 목록"
    )

    # Spec 회복 타임라인
    spec_recovery_timeline: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Spec 회복 타임라인 [{turn, recovered_specs, cumulative_completeness}]"
    )

    # 최종 Spec 완전성
    final_spec_completeness: float = Field(
        ..., ge=0.0, le=100.0, description="최종 Spec 완전성 (마지막 턴 기준)"
    )

    # 첫 프롬프트 정보 (빠른 접근용)
    first_prompt_spec_completeness: float = Field(
        ..., ge=0.0, le=100.0, description="첫 프롬프트 Spec 완전성"
    )
    first_prompt_expression_score: float = Field(
        ..., ge=0.0, le=100.0, description="첫 프롬프트 표현 품질"
    )


class IntegratedEvaluationResult(BaseModel):
    """
    통합 평가 결과 (제출 시 생성)
    
    6개 핵심 지표 기반 평가 결과.
    가중치: 첫 프롬프트 55%, 후속 턴 25%, 효율성 20%
    """

    # 첫 프롬프트 평가 (55%)
    first_prompt_score: float = Field(
        ..., ge=0.0, le=100.0, description="첫 프롬프트 점수"
    )
    first_prompt_details: Dict[str, Any] = Field(
        default_factory=dict,
        description="첫 프롬프트 상세 {spec_completeness, expression_quality}"
    )

    # 후속 턴 평가 (25%)
    follow_up_score: float = Field(
        ..., ge=0.0, le=100.0, description="후속 턴 점수"
    )
    follow_up_details: Dict[str, Any] = Field(
        default_factory=dict,
        description="후속 턴 상세 {context_quality, spec_recovery}"
    )

    # 효율성 평가 (20%)
    efficiency_score: float = Field(
        ..., ge=0.0, le=100.0, description="효율성 점수"
    )
    efficiency_details: Dict[str, Any] = Field(
        default_factory=dict,
        description="효율성 상세 {total_turns, recovery_speed}"
    )

    # 통합 점수
    integrated_score: float = Field(
        ..., ge=0.0, le=100.0, description="통합 평가 점수 (가중 합계)"
    )

    # 피드백 및 제안
    analysis: str = Field(..., description="종합 분석")
    suggestions: List[str] = Field(
        default_factory=list, description="개선 제안 목록"
    )

    # 턴별 상세 (프론트엔드 표시용)
    turn_details: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="턴별 상세 [{turn, spec_completeness, expression_score, ...}]"
    )
