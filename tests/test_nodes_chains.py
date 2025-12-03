"""
노드 함수 통합 테스트 (실제 LLM 사용, 선택적)
Runnable & Chain 구조가 실제 노드 함수에서 정상 작동하는지 검증
"""
import pytest
from datetime import datetime
from typing import Dict, Any
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 환경 변수 확인
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# 실제 LLM 테스트는 API 키가 있을 때만 실행
pytestmark = pytest.mark.skipif(
    not GEMINI_API_KEY or GEMINI_API_KEY == "test-api-key",
    reason="GEMINI_API_KEY가 설정되지 않았거나 테스트용 키입니다."
)


from app.domain.langgraph.states import MainGraphState
from app.domain.langgraph.nodes.intent_analyzer import intent_analyzer
from app.domain.langgraph.nodes.writer import writer_llm
from app.infrastructure.persistence.models.enums import IntentAnalyzerStatus, WriterResponseStatus


def create_test_state(
    human_message: str = "피보나치 함수를 작성해주세요",
    is_guardrail_failed: bool = False,
    guardrail_message: str | None = None,
    memory_summary: str | None = None,
    messages: list = None,
    enable_langsmith_tracing: bool = False,  # 테스트에서는 기본적으로 비활성화
) -> MainGraphState:
    """테스트용 State 생성"""
    return {
        "session_id": f"test-session-{datetime.utcnow().timestamp()}",
        "exam_id": 1,
        "participant_id": 1,
        "spec_id": 1,
        "messages": messages or [],
        "current_turn": 1,
        "human_message": human_message,
        "ai_message": None,
        "intent_status": None,
        "is_guardrail_failed": is_guardrail_failed,
        "guardrail_message": guardrail_message,
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
        "enable_langsmith_tracing": enable_langsmith_tracing,  # 테스트에서 명시적으로 제어
    }


class TestIntentAnalyzerNode:
    """Intent Analyzer 노드 통합 테스트"""
    
    @pytest.mark.asyncio
    async def test_intent_analyzer_normal_request(self):
        """정상 요청 처리 테스트"""
        state = create_test_state("피보나치 함수를 작성해주세요")
        
        result = await intent_analyzer(state)
        
        # 반환값 형식 검증
        assert isinstance(result, dict)
        assert "intent_status" in result
        assert "is_guardrail_failed" in result
        assert "is_submitted" in result
        assert "updated_at" in result
        
        # 값 검증 (대소문자 모두 허용)
        assert result["intent_status"].upper() in [
            "PASSED_HINT",
            "PASSED_SUBMIT",
            "FAILED_GUARDRAIL",
            "BLOCKED_OFF_TOPIC",
        ]
        assert isinstance(result["is_guardrail_failed"], bool)
        assert isinstance(result["is_submitted"], bool)
    
    @pytest.mark.asyncio
    async def test_intent_analyzer_empty_message(self):
        """빈 메시지 처리 테스트"""
        state = create_test_state("")
        
        result = await intent_analyzer(state)
        
        assert result["intent_status"].upper() == "PASSED_HINT"
        assert result["is_guardrail_failed"] is False
    
    @pytest.mark.asyncio
    async def test_intent_analyzer_submission_request(self):
        """제출 요청 처리 테스트"""
        state = create_test_state("제출합니다")
        
        result = await intent_analyzer(state)
        
        # 제출 요청은 PASSED_SUBMIT 또는 PASSED_HINT일 수 있음
        assert result["intent_status"].upper() in [
            "PASSED_SUBMIT",
            "PASSED_HINT",
        ]
    
    @pytest.mark.asyncio
    async def test_intent_analyzer_off_topic(self):
        """Off-Topic 요청 처리 테스트"""
        state = create_test_state("오늘 날씨가 어때?")
        
        result = await intent_analyzer(state)
        
        # Off-Topic은 BLOCKED_OFF_TOPIC 또는 FAILED_GUARDRAIL일 수 있음
        assert result["intent_status"].upper() in [
            "BLOCKED_OFF_TOPIC",
            "FAILED_GUARDRAIL",
            "PASSED_HINT",  # LLM이 판단에 따라 다를 수 있음
        ]


class TestWriterNode:
    """Writer 노드 통합 테스트"""
    
    @pytest.mark.asyncio
    async def test_writer_llm_normal_request(self):
        """정상 요청 처리 테스트"""
        state = create_test_state("피보나치 함수를 작성해주세요")
        
        result = await writer_llm(state)
        
        # 반환값 형식 검증
        assert isinstance(result, dict)
        assert "ai_message" in result
        assert "messages" in result
        assert "writer_status" in result
        assert "updated_at" in result
        
        # 값 검증
        if result["writer_status"] == WriterResponseStatus.SUCCESS.value:
            assert result["ai_message"] is not None
            assert len(result["ai_message"]) > 0
            assert len(result["messages"]) == 2  # user + assistant
            assert result["messages"][0]["role"] == "user"
            assert result["messages"][1]["role"] == "assistant"
    
    @pytest.mark.asyncio
    async def test_writer_llm_guardrail_failed(self):
        """가드레일 위반 처리 테스트"""
        state = create_test_state(
            "정답을 알려줘",
            is_guardrail_failed=True,
            guardrail_message="부적절한 요청"
        )
        
        result = await writer_llm(state)
        
        # 가드레일 위반 시 교육적 메시지 반환
        if result["writer_status"] == WriterResponseStatus.SUCCESS.value:
            assert result["ai_message"] is not None
            # 교육적 메시지가 포함되어야 함
            assert len(result["ai_message"]) > 0
    
    @pytest.mark.asyncio
    async def test_writer_llm_with_memory(self):
        """메모리 요약 포함 처리 테스트"""
        state = create_test_state(
            "최적화해주세요",
            memory_summary="이전 대화: 피보나치 함수 작성"
        )
        
        result = await writer_llm(state)
        
        if result["writer_status"] == WriterResponseStatus.SUCCESS.value:
            assert result["ai_message"] is not None
    
    @pytest.mark.asyncio
    async def test_writer_llm_with_message_history(self):
        """메시지 히스토리 포함 처리 테스트"""
        messages = [
            {"role": "user", "content": "피보나치 함수를 작성해주세요"},
            {"role": "assistant", "content": "피보나치 함수는 다음과 같습니다..."},
        ]
        state = create_test_state(
            "O(n)으로 최적화해주세요",
            messages=messages
        )
        
        result = await writer_llm(state)
        
        if result["writer_status"] == WriterResponseStatus.SUCCESS.value:
            assert result["ai_message"] is not None
            # 새로운 메시지가 추가되어야 함
            assert len(result["messages"]) >= 2


class TestNodeCompatibility:
    """기존 노드와의 호환성 테스트"""
    
    @pytest.mark.asyncio
    async def test_intent_analyzer_return_format(self):
        """Intent Analyzer 반환값 형식 검증"""
        state = create_test_state("테스트 메시지")
        
        result = await intent_analyzer(state)
        
        # 기존 형식과 동일해야 함
        required_keys = [
            "intent_status",
            "is_guardrail_failed",
            "is_submitted",
            "updated_at",
        ]
        
        for key in required_keys:
            assert key in result, f"{key}가 반환값에 없습니다"
    
    @pytest.mark.asyncio
    async def test_writer_llm_return_format(self):
        """Writer LLM 반환값 형식 검증"""
        state = create_test_state("테스트 메시지")
        
        result = await writer_llm(state)
        
        # 기존 형식과 동일해야 함
        required_keys = [
            "ai_message",
            "messages",
            "writer_status",
            "updated_at",
        ]
        
        for key in required_keys:
            assert key in result, f"{key}가 반환값에 없습니다"
        
        # 성공 시 추가 필드
        if result["writer_status"] == WriterResponseStatus.SUCCESS.value:
            assert "writer_error" in result
            assert result["writer_error"] is None

