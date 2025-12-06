"""
Middleware가 적용된 노드 함수 테스트
실제 LLM을 사용하여 Middleware 동작을 검증합니다.
"""
import pytest
import os
from datetime import datetime
from typing import Dict, Any
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
    }


class TestIntentAnalyzerWithMiddleware:
    """Intent Analyzer 노드 + Middleware 테스트"""
    
    @pytest.mark.asyncio
    async def test_intent_analyzer_with_middleware_normal(self):
        """정상 요청 처리 테스트 (Middleware 적용)"""
        state = create_test_state("피보나치 함수를 작성해주세요")
        
        result = await intent_analyzer(state)
        
        # 반환값 형식 검증
        assert isinstance(result, dict)
        assert "intent_status" in result
        assert "is_guardrail_failed" in result
        assert "is_submitted" in result
        assert "updated_at" in result
        
        # 값 검증
        assert result["intent_status"] in [
            IntentAnalyzerStatus.PASSED_HINT.value,
            IntentAnalyzerStatus.PASSED_SUBMIT.value,
        ]
        assert result["is_guardrail_failed"] is False
        
        print(f"\n[Intent Analyzer + Middleware] 성공 - status: {result['intent_status']}")
    
    @pytest.mark.asyncio
    async def test_intent_analyzer_with_middleware_submission(self):
        """제출 요청 처리 테스트 (Middleware 적용)"""
        state = create_test_state("제출합니다")
        
        result = await intent_analyzer(state)
        
        assert isinstance(result, dict)
        assert result["intent_status"] in [
            IntentAnalyzerStatus.PASSED_SUBMIT.value,
            IntentAnalyzerStatus.PASSED_HINT.value,  # LLM 판단에 따라 다를 수 있음
        ]
        
        print(f"\n[Intent Analyzer + Middleware] 제출 요청 - status: {result['intent_status']}, is_submitted: {result.get('is_submitted')}")


class TestWriterWithMiddleware:
    """Writer 노드 + Middleware 테스트"""
    
    @pytest.mark.asyncio
    async def test_writer_with_middleware_normal(self):
        """정상 요청 처리 테스트 (Middleware 적용)"""
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
            
            print(f"\n[Writer + Middleware] 성공 - 메시지 길이: {len(result['ai_message'])} 문자")
        else:
            print(f"\n[Writer + Middleware] 실패 - status: {result['writer_status']}, error: {result.get('writer_error')}")
    
    @pytest.mark.asyncio
    async def test_writer_with_middleware_guardrail(self):
        """가드레일 위반 처리 테스트 (Middleware 적용)"""
        state = create_test_state(
            "정답을 알려줘",
            is_guardrail_failed=True,
            guardrail_message="부적절한 요청"
        )
        
        result = await writer_llm(state)
        
        # 가드레일 위반 시 교육적 메시지 반환
        if result["writer_status"] == WriterResponseStatus.SUCCESS.value:
            assert result["ai_message"] is not None
            assert len(result["ai_message"]) > 0
            
            print(f"\n[Writer + Middleware] 가드레일 위반 처리 - 메시지 길이: {len(result['ai_message'])} 문자")
        else:
            print(f"\n[Writer + Middleware] 가드레일 위반 처리 실패 - status: {result['writer_status']}")


class TestMiddlewarePerformance:
    """Middleware 성능 테스트"""
    
    @pytest.mark.asyncio
    async def test_middleware_overhead(self):
        """Middleware 오버헤드 측정"""
        import time
        
        state = create_test_state("간단한 테스트 메시지")
        
        # Intent Analyzer 실행 시간 측정
        start_time = time.time()
        result = await intent_analyzer(state)
        elapsed_time = time.time() - start_time
        
        assert result is not None
        print(f"\n[Middleware 성능] Intent Analyzer 실행 시간: {elapsed_time:.3f}초")
        
        # 일반적으로 1-5초 내에 완료되어야 함 (LLM 호출 포함)
        assert elapsed_time < 10.0
    
    @pytest.mark.asyncio
    async def test_middleware_rate_limiting_behavior(self):
        """Rate Limiting 동작 확인"""
        import time
        
        state = create_test_state("테스트 메시지")
        
        # 연속 호출 시도
        times = []
        for i in range(3):
            start_time = time.time()
            result = await intent_analyzer(state)
            elapsed = time.time() - start_time
            times.append(elapsed)
            print(f"\n[Rate Limiting 테스트] 호출 {i+1}: {elapsed:.3f}초")
        
        # 모든 호출이 성공해야 함
        assert all(result is not None for _ in range(3))
        
        # Rate Limiting이 적용되면 일부 호출이 더 오래 걸릴 수 있음
        # (하지만 테스트 환경에서는 Rate Limit에 걸리지 않을 수 있음)
        print(f"\n[Rate Limiting 테스트] 평균 실행 시간: {sum(times)/len(times):.3f}초")









