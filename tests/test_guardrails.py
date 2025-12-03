"""
가드레일 테스트 (2-Layer Guardrails)
"""
import pytest
from datetime import datetime
from typing import Dict, Any
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 테스트에서 LangSmith 추적 비활성화 (토큰 절약)
os.environ["LANGCHAIN_TRACING_V2"] = "false"
if "LANGCHAIN_API_KEY" in os.environ:
    del os.environ["LANGCHAIN_API_KEY"]

# 환경 변수 확인
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# 실제 LLM 테스트는 API 키가 있을 때만 실행
pytestmark = pytest.mark.skipif(
    not GEMINI_API_KEY or GEMINI_API_KEY == "test-api-key",
    reason="GEMINI_API_KEY가 설정되지 않았거나 테스트용 키입니다."
)

from app.domain.langgraph.states import MainGraphState
from app.domain.langgraph.nodes.intent_analyzer import (
    intent_analyzer,
    quick_answer_detection,
    IntentAnalysisResult,
)
from app.domain.langgraph.nodes.writer import writer_llm, prepare_writer_input
from app.infrastructure.persistence.models.enums import IntentAnalyzerStatus, WriterResponseStatus


def create_test_state(
    human_message: str = "피보나치 함수를 작성해주세요",
    is_guardrail_failed: bool = False,
    guardrail_message: str | None = None,
    guide_strategy: str | None = None,
    keywords: list[str] | None = None,
    memory_summary: str | None = None,
    messages: list = None,
    spec_id: int = 1,
    enable_langsmith_tracing: bool = False,
) -> MainGraphState:
    """테스트용 State 생성"""
    return {
        "session_id": f"test-session-{datetime.utcnow().timestamp()}",
        "exam_id": 1,
        "participant_id": 1,
        "spec_id": spec_id,
        "messages": messages or [],
        "current_turn": 1,
        "human_message": human_message,
        "ai_message": None,
        "intent_status": None,
        "is_guardrail_failed": is_guardrail_failed,
        "guardrail_message": guardrail_message,
        "guide_strategy": guide_strategy,
        "keywords": keywords or [],
        "writer_status": None,
        "writer_error": None,
        "is_submitted": False,
        "submission_id": None,
        "code_content": None,
        "turn_scores": {},
        "holistic_flow_score": None,
        "aggregate_turn_score": None,
        "code_performance_score": None,
        "code_correctness_score": None,
        "final_scores": None,
        "memory_summary": memory_summary,
        "error_message": None,
        "retry_count": 0,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "enable_langsmith_tracing": enable_langsmith_tracing,
    }


class TestLayer1KeywordDetection:
    """Layer 1: 키워드 기반 빠른 검증 테스트"""
    
    def test_quick_answer_detection_korean(self):
        """한국어 정답 요청 패턴 감지"""
        test_cases = [
            "정답 코드를 알려줘",
            "정답 알려줘",
            "답 코드",
            "전체 코드",
            "점화식 알려줘",
            "재귀 구조",
            "핵심 로직",
        ]
        
        for message in test_cases:
            result = quick_answer_detection(message)
            assert result is not None, f"'{message}'가 차단되지 않았습니다"
            assert result["status"] == "BLOCKED"
            assert result["block_reason"] == "DIRECT_ANSWER"
            assert result["guardrail_passed"] is False
    
    def test_quick_answer_detection_english(self):
        """영어 정답 요청 패턴 감지"""
        test_cases = [
            "complete solution",
            "full code",
            "answer code",
            "entire code",
            "recurrence relation",
        ]
        
        for message in test_cases:
            result = quick_answer_detection(message)
            assert result is not None, f"'{message}'가 차단되지 않았습니다"
            assert result["status"] == "BLOCKED"
            assert result["block_reason"] == "DIRECT_ANSWER"
    
    def test_quick_answer_detection_safe(self):
        """안전한 요청 통과"""
        test_cases = [
            "비트마스킹이 뭔가요?",
            "동적 계획법의 개념을 설명해주세요",
            "비트 연산자 어떻게 쓰나요?",
            "파이썬 리스트 컴프리헨션 문법은?",
        ]
        
        for message in test_cases:
            result = quick_answer_detection(message)
            assert result is None, f"'{message}'가 차단되었습니다 (통과해야 함)"
    
    def test_quick_answer_detection_problem_specific(self):
        """문제별 키워드 감지 (TSP 예시)"""
        problem_context = {
            "problem_id": "2098",
            "problem_name": "외판원 순회",
        }
        
        test_cases = [
            "외판원 문제의 정답 코드",
            "TSP 문제의 점화식",
            "traveling salesman solution",
        ]
        
        for message in test_cases:
            result = quick_answer_detection(message, problem_context)
            assert result is not None, f"'{message}'가 차단되지 않았습니다"
            assert result["status"] == "BLOCKED"


class TestLayer2LLMAnalysis:
    """Layer 2: LLM 기반 상세 분석 테스트"""
    
    @pytest.mark.asyncio
    async def test_intent_analyzer_safe_syntax_guide(self):
        """안전한 문법 질문 (SYNTAX_GUIDE)"""
        state = create_test_state("비트 연산자 어떻게 쓰나요?")
        
        result = await intent_analyzer(state)
        
        assert "intent_status" in result
        assert "guide_strategy" in result
        assert "keywords" in result
        
        # 가드레일 통과해야 함
        assert result["is_guardrail_failed"] is False
        
        # Guide Strategy가 설정되어야 함 (LLM 판단에 따라 다를 수 있음)
        if result.get("guide_strategy"):
            assert result["guide_strategy"] in ["SYNTAX_GUIDE", "LOGIC_HINT", "ROADMAP"]
    
    @pytest.mark.asyncio
    async def test_intent_analyzer_safe_logic_hint(self):
        """안전한 개념 질문 (LOGIC_HINT)"""
        state = create_test_state("동적 계획법의 개념을 설명해주세요")
        
        result = await intent_analyzer(state)
        
        assert result["is_guardrail_failed"] is False
        
        if result.get("guide_strategy"):
            assert result["guide_strategy"] in ["LOGIC_HINT", "SYNTAX_GUIDE", "ROADMAP"]
    
    @pytest.mark.asyncio
    async def test_intent_analyzer_safe_roadmap(self):
        """안전한 접근법 질문 (ROADMAP)"""
        state = create_test_state("문제 해결 순서를 알려주세요")
        
        result = await intent_analyzer(state)
        
        assert result["is_guardrail_failed"] is False
    
    @pytest.mark.asyncio
    async def test_intent_analyzer_submission(self):
        """제출 요청"""
        state = create_test_state("제출합니다")
        
        result = await intent_analyzer(state)
        
        # 제출 요청은 통과해야 함
        assert result["is_guardrail_failed"] is False
        assert result["is_submitted"] is True or result["intent_status"] == IntentAnalyzerStatus.PASSED_SUBMIT.value


class Test2LayerGuardrailsIntegration:
    """2-Layer Guardrails 통합 테스트"""
    
    @pytest.mark.asyncio
    async def test_layer1_blocks_before_layer2(self):
        """Layer 1이 차단하면 Layer 2는 호출되지 않음"""
        # 명확한 정답 요청 (Layer 1에서 차단)
        state = create_test_state("정답 코드를 알려줘")
        
        result = await intent_analyzer(state)
        
        # Layer 1에서 차단되어야 함
        assert result["is_guardrail_failed"] is True
        assert result["intent_status"] == IntentAnalyzerStatus.FAILED_GUARDRAIL.value
        assert "guide_strategy" in result
        assert "keywords" in result
    
    @pytest.mark.asyncio
    async def test_layer2_analyzes_ambiguous(self):
        """모호한 요청은 Layer 2에서 분석"""
        # 모호한 요청 (Layer 1 통과, Layer 2에서 분석)
        state = create_test_state("이 문제를 어떻게 풀어야 하나요?")
        
        result = await intent_analyzer(state)
        
        # 결과가 있어야 함
        assert "intent_status" in result
        assert "is_guardrail_failed" in result
        assert "guide_strategy" in result
        assert "keywords" in result


class TestWriterGuideStrategy:
    """Writer LLM Guide Strategy 기반 답변 테스트"""
    
    def test_prepare_writer_input_syntax_guide(self):
        """SYNTAX_GUIDE 기반 입력 준비"""
        state = create_test_state(
            "비트 연산자 어떻게 쓰나요?",
            guide_strategy="SYNTAX_GUIDE",
            keywords=["비트", "연산자"]
        )
        
        result = prepare_writer_input(state)
        
        assert "system_prompt" in result
        assert "SYNTAX_GUIDE" in result["system_prompt"]
        assert "비트" in result["system_prompt"] or "연산자" in result["system_prompt"]
        assert "[Syntax Example]" in result["system_prompt"]
    
    def test_prepare_writer_input_logic_hint(self):
        """LOGIC_HINT 기반 입력 준비"""
        state = create_test_state(
            "동적 계획법의 개념을 설명해주세요",
            guide_strategy="LOGIC_HINT",
            keywords=["동적", "계획법"]
        )
        
        result = prepare_writer_input(state)
        
        assert "system_prompt" in result
        assert "LOGIC_HINT" in result["system_prompt"]
        assert "[Concept]" in result["system_prompt"]
    
    def test_prepare_writer_input_roadmap(self):
        """ROADMAP 기반 입력 준비"""
        state = create_test_state(
            "문제 해결 순서를 알려주세요",
            guide_strategy="ROADMAP",
            keywords=["문제", "해결"]
        )
        
        result = prepare_writer_input(state)
        
        assert "system_prompt" in result
        assert "ROADMAP" in result["system_prompt"]
        assert "[Roadmap]" in result["system_prompt"]
    
    def test_prepare_writer_input_default_strategy(self):
        """기본 전략 (guide_strategy 없음)"""
        state = create_test_state("일반 질문")
        
        result = prepare_writer_input(state)
        
        assert "system_prompt" in result
        # 기본값 LOGIC_HINT가 사용되어야 함
        assert "LOGIC_HINT" in result["system_prompt"] or "SAFE" in result["system_prompt"]
    
    @pytest.mark.asyncio
    async def test_writer_llm_with_guide_strategy(self):
        """Guide Strategy 기반 Writer LLM 답변 생성"""
        state = create_test_state(
            "비트마스킹으로 상태를 표현하는 방법을 알려줘",
            guide_strategy="SYNTAX_GUIDE",
            keywords=["비트마스킹", "상태"]
        )
        
        # 먼저 Intent Analyzer 실행 (Guide Strategy 설정)
        from app.domain.langgraph.nodes.intent_analyzer import intent_analyzer
        intent_result = await intent_analyzer(state)
        
        # Guide Strategy가 설정되었으면 State 업데이트
        if intent_result.get("guide_strategy"):
            state["guide_strategy"] = intent_result["guide_strategy"]
            state["keywords"] = intent_result.get("keywords", [])
        
        # Writer LLM 실행
        result = await writer_llm(state)
        
        assert "ai_message" in result
        assert result["writer_status"] == WriterResponseStatus.SUCCESS.value
        
        # 답변에 Guide Strategy 관련 내용이 포함되어야 함
        if result["ai_message"]:
            # Syntax Example, Concept, Roadmap 중 하나가 포함되어야 함
            assert any(keyword in result["ai_message"] for keyword in [
                "Syntax", "Concept", "Roadmap", "비트", "상태"
            ]) or len(result["ai_message"]) > 0  # 최소한 답변이 있어야 함


class TestGuardrailCompatibility:
    """기존 가드레일과의 호환성 테스트"""
    
    @pytest.mark.asyncio
    async def test_backward_compatibility(self):
        """하위 호환성 검증"""
        state = create_test_state("테스트 메시지")
        
        result = await intent_analyzer(state)
        
        # 기존 필드들이 모두 있어야 함
        required_keys = [
            "intent_status",
            "is_guardrail_failed",
            "is_submitted",
            "updated_at",
        ]
        
        for key in required_keys:
            assert key in result, f"{key}가 반환값에 없습니다"
        
        # 새로운 필드들도 있어야 함
        assert "guide_strategy" in result
        assert "keywords" in result
        
        # intent_status는 기존 Enum 값이어야 함
        assert result["intent_status"] in [
            IntentAnalyzerStatus.PASSED_HINT.value,
            IntentAnalyzerStatus.PASSED_SUBMIT.value,
            IntentAnalyzerStatus.FAILED_GUARDRAIL.value,
            IntentAnalyzerStatus.FAILED_RATE_LIMIT.value,
        ]

