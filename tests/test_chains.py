"""
Chain 단위 테스트 (Mock LLM 사용)
Runnable & Chain 구조 검증
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from typing import Dict, Any

from app.domain.langgraph.nodes.intent_analyzer import (
    prepare_input,
    process_output,
    IntentAnalysisResult,
    intent_analysis_chain,
)
from app.domain.langgraph.nodes.writer import (
    prepare_writer_input,
    format_writer_messages,
    get_writer_chain,
)
from app.domain.langgraph.states import MainGraphState
from app.infrastructure.persistence.models.enums import IntentAnalyzerStatus


class TestIntentAnalyzerChain:
    """Intent Analyzer Chain 테스트"""
    
    def test_prepare_input(self):
        """prepare_input 함수 테스트"""
        inputs = {"human_message": "피보나치 함수를 작성해주세요"}
        result = prepare_input(inputs)
        
        assert "human_message" in result
        assert result["human_message"] == "피보나치 함수를 작성해주세요"
    
    def test_prepare_input_empty(self):
        """빈 메시지 처리 테스트"""
        from app.domain.langgraph.states import MainGraphState
        from datetime import datetime
        
        state: MainGraphState = {
            "session_id": "test",
            "exam_id": 1,
            "participant_id": 1,
            "spec_id": 10,
            "problem_context": None,
            "problem_id": None,
            "problem_name": None,
            "problem_algorithm": None,
            "problem_keywords": None,
            "messages": [],
            "current_turn": 1,
            "human_message": "",
            "ai_message": None,
            "intent_status": None,
            "is_guardrail_failed": False,
            "guardrail_message": None,
            "guide_strategy": None,
            "keywords": None,
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
            "memory_summary": None,
            "error_message": None,
            "retry_count": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "enable_langsmith_tracing": None,
        }
        
        inputs = {"state": state, "human_message": ""}
        result = prepare_input(inputs)
        
        assert result["human_message"] == ""
        assert "system_prompt" in result
    
    def test_process_output(self):
        """process_output 함수 테스트"""
        mock_result = IntentAnalysisResult(
            status="SAFE",
            request_type="CHAT",
            is_submission_request=False,
            guardrail_passed=True,
            violation_message=None,
            reasoning="정상적인 요청입니다."
        )
        
        result = process_output(mock_result)
        
        assert result["intent_status"] == "passed_hint"
        assert result["is_guardrail_failed"] is False
        assert result["is_submitted"] is False
        assert "updated_at" in result
    
    def test_process_output_guardrail_failed(self):
        """가드레일 위반 처리 테스트"""
        mock_result = IntentAnalysisResult(
            status="BLOCKED",
            block_reason="DIRECT_ANSWER",
            request_type="CHAT",
            is_submission_request=False,
            guardrail_passed=False,
            violation_message="부적절한 요청입니다.",
            reasoning="가드레일 위반"
        )
        
        result = process_output(mock_result)
        
        assert result["intent_status"] == "failed_guardrail"
        assert result["is_guardrail_failed"] is True
        assert result["guardrail_message"] == "부적절한 요청입니다."
    
    def test_process_output_submission(self):
        """제출 요청 처리 테스트"""
        mock_result = IntentAnalysisResult(
            status="SAFE",
            request_type="SUBMISSION",
            is_submission_request=True,
            guardrail_passed=True,
            violation_message=None,
            reasoning="제출 요청입니다."
        )
        
        result = process_output(mock_result)
        
        assert result["intent_status"] == "passed_submit"
        assert result["is_submitted"] is True


class TestWriterChain:
    """Writer Chain 테스트"""
    
    def test_prepare_writer_input_normal(self):
        """정상 요청 입력 준비 테스트"""
        state: MainGraphState = {
            "session_id": "test-session",
            "exam_id": 1,
            "participant_id": 1,
            "spec_id": 1,
            "messages": [],
            "current_turn": 1,
            "human_message": "피보나치 함수를 작성해주세요",
            "ai_message": None,
            "intent_status": None,
            "is_guardrail_failed": False,
            "guardrail_message": None,
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
            "memory_summary": None,
            "error_message": None,
            "retry_count": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        result = prepare_writer_input(state)
        
        assert "system_prompt" in result
        assert "messages" in result
        assert "human_message" in result
        assert result["human_message"] == "피보나치 함수를 작성해주세요"
        assert "정상적인" in result["system_prompt"] or "소크라테스" in result["system_prompt"]
    
    def test_prepare_writer_input_guardrail_failed(self):
        """가드레일 위반 입력 준비 테스트"""
        state: MainGraphState = {
            "session_id": "test-session",
            "exam_id": 1,
            "participant_id": 1,
            "spec_id": 1,
            "messages": [],
            "current_turn": 1,
            "human_message": "정답을 알려줘",
            "ai_message": None,
            "intent_status": None,
            "is_guardrail_failed": True,
            "guardrail_message": "부적절한 요청",
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
            "memory_summary": None,
            "error_message": None,
            "retry_count": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        result = prepare_writer_input(state)
        
        assert "system_prompt" in result
        assert "부적절한 요청" in result["system_prompt"] or "Gatekeeper" in result["system_prompt"]
    
    def test_prepare_writer_input_with_memory(self):
        """메모리 요약 포함 입력 준비 테스트"""
        state: MainGraphState = {
            "session_id": "test-session",
            "exam_id": 1,
            "participant_id": 1,
            "spec_id": 1,
            "messages": [],
            "current_turn": 1,
            "human_message": "최적화해주세요",
            "ai_message": None,
            "intent_status": None,
            "is_guardrail_failed": False,
            "guardrail_message": None,
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
            "memory_summary": "이전 대화: 피보나치 함수 작성",
            "error_message": None,
            "retry_count": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        result = prepare_writer_input(state)
        
        assert "이전 대화: 피보나치 함수 작성" in result["system_prompt"]
    
    def test_format_writer_messages(self):
        """메시지 포맷팅 테스트"""
        inputs = {
            "system_prompt": "시스템 프롬프트",
            "messages": [
                {"role": "user", "content": "이전 메시지"},
                {"role": "assistant", "content": "이전 답변"}
            ],
            "human_message": "현재 메시지",
            "state": {}
        }
        
        result = format_writer_messages(inputs)
        
        assert len(result) == 4  # system + 2 messages + current
        assert result[0]["role"] == "system"
        assert result[-1]["role"] == "user"
        assert result[-1]["content"] == "현재 메시지"
    
    def test_format_writer_messages_empty_history(self):
        """빈 히스토리 메시지 포맷팅 테스트"""
        inputs = {
            "system_prompt": "시스템 프롬프트",
            "messages": [],
            "human_message": "현재 메시지",
            "state": {}
        }
        
        result = format_writer_messages(inputs)
        
        assert len(result) == 2  # system + current
        assert result[0]["role"] == "system"
        assert result[1]["role"] == "user"


class TestChainIntegration:
    """Chain 통합 테스트 (Mock LLM 사용)"""
    
    @pytest.mark.asyncio
    async def test_intent_analysis_chain_mock(self):
        """Intent Analysis Chain Mock 테스트"""
        from app.domain.langgraph.states import MainGraphState
        from datetime import datetime
        
        # Chain의 헬퍼 함수만 테스트 (실제 LLM 호출 없이)
        state: MainGraphState = {
            "session_id": "test",
            "exam_id": 1,
            "participant_id": 1,
            "spec_id": 10,
            "problem_context": None,
            "problem_id": None,
            "problem_name": None,
            "problem_algorithm": None,
            "problem_keywords": None,
            "messages": [],
            "current_turn": 1,
            "human_message": "피보나치 함수를 작성해주세요",
            "ai_message": None,
            "intent_status": None,
            "is_guardrail_failed": False,
            "guardrail_message": None,
            "guide_strategy": None,
            "keywords": None,
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
            "memory_summary": None,
            "error_message": None,
            "retry_count": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "enable_langsmith_tracing": None,
        }
        
        inputs = {"state": state, "human_message": "피보나치 함수를 작성해주세요"}
        prepared = prepare_input(inputs)
        
        assert prepared["human_message"] == "피보나치 함수를 작성해주세요"
        assert "system_prompt" in prepared
        
        # process_output 테스트
        mock_result = IntentAnalysisResult(
            status="SAFE",
            request_type="CHAT",
            is_submission_request=False,
            guardrail_passed=True,
            violation_message=None,
            reasoning="정상적인 요청"
        )
        
        processed = process_output(mock_result)
        assert processed["intent_status"] == "passed_hint"
    
    @pytest.mark.asyncio
    @patch('app.domain.langgraph.nodes.writer.get_llm')
    async def test_writer_chain_mock(self, mock_get_llm):
        """Writer Chain Mock 테스트"""
        # Mock LLM 설정
        mock_llm = AsyncMock()
        mock_response = Mock()
        mock_response.content = "Mock AI response"
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_get_llm.return_value = mock_llm
        
        # State 준비
        state: MainGraphState = {
            "session_id": "test-session",
            "exam_id": 1,
            "participant_id": 1,
            "spec_id": 1,
            "messages": [],
            "current_turn": 1,
            "human_message": "피보나치 함수를 작성해주세요",
            "ai_message": None,
            "intent_status": None,
            "is_guardrail_failed": False,
            "guardrail_message": None,
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
            "memory_summary": None,
            "error_message": None,
            "retry_count": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        # 입력 준비 및 메시지 포맷팅 테스트
        prepared = prepare_writer_input(state)
        formatted = format_writer_messages(prepared)
        
        assert len(formatted) >= 2
        assert formatted[0]["role"] == "system"
        assert formatted[-1]["role"] == "user"
        assert formatted[-1]["content"] == "피보나치 함수를 작성해주세요"

