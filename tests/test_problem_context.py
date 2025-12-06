"""
Problem Context 구조 테스트
새로운 HARDCODED_PROBLEM_SPEC 구조 검증
"""
import pytest
from typing import Dict, Any

from app.domain.langgraph.utils.problem_info import (
    get_problem_info_sync,
    get_problem_info,
    HARDCODED_PROBLEM_SPEC
)
from app.domain.langgraph.nodes.intent_analyzer import create_intent_analysis_system_prompt
from app.domain.langgraph.nodes.writer import create_normal_system_prompt
from app.domain.langgraph.nodes.holistic_evaluator.flow import create_holistic_system_prompt


class TestProblemInfoStructure:
    """Problem Info 구조 테스트"""
    
    def test_hardcoded_problem_spec_exists(self):
        """HARDCODED_PROBLEM_SPEC이 존재하는지 확인"""
        assert 10 in HARDCODED_PROBLEM_SPEC
        problem_spec = HARDCODED_PROBLEM_SPEC[10]
        
        # 필수 필드 확인
        assert "basic_info" in problem_spec
        assert "constraints" in problem_spec
        assert "ai_guide" in problem_spec
        assert "solution_code" in problem_spec
        assert "keywords" in problem_spec
    
    def test_basic_info_structure(self):
        """basic_info 구조 확인"""
        problem_spec = HARDCODED_PROBLEM_SPEC[10]
        basic_info = problem_spec["basic_info"]
        
        assert "problem_id" in basic_info
        assert "title" in basic_info
        assert "description_summary" in basic_info
        assert "input_format" in basic_info
        assert "output_format" in basic_info
        
        assert basic_info["problem_id"] == "2098"
        assert basic_info["title"] == "외판원 순회"
    
    def test_constraints_structure(self):
        """constraints 구조 확인"""
        problem_spec = HARDCODED_PROBLEM_SPEC[10]
        constraints = problem_spec["constraints"]
        
        assert "time_limit_sec" in constraints
        assert "memory_limit_mb" in constraints
        assert "variable_ranges" in constraints
        assert "logic_reasoning" in constraints
        
        assert constraints["time_limit_sec"] == 1.0
        assert "비트마스킹" in constraints["logic_reasoning"]
    
    def test_ai_guide_structure(self):
        """ai_guide 구조 확인"""
        problem_spec = HARDCODED_PROBLEM_SPEC[10]
        ai_guide = problem_spec["ai_guide"]
        
        assert "key_algorithms" in ai_guide
        assert "solution_architecture" in ai_guide
        assert "hint_roadmap" in ai_guide
        assert "common_pitfalls" in ai_guide
        
        assert isinstance(ai_guide["key_algorithms"], list)
        assert len(ai_guide["key_algorithms"]) > 0
        assert "Dynamic Programming" in ai_guide["key_algorithms"]
        
        # hint_roadmap 확인
        hint_roadmap = ai_guide["hint_roadmap"]
        assert "step_1_concept" in hint_roadmap
        assert "step_2_state" in hint_roadmap
        assert "step_3_transition" in hint_roadmap
        assert "step_4_base_case" in hint_roadmap


class TestProblemInfoFunctions:
    """Problem Info 함수 테스트"""
    
    def test_get_problem_info_sync_existing(self):
        """존재하는 spec_id로 조회 테스트"""
        result = get_problem_info_sync(10)
        
        # 새로운 구조 확인
        assert "basic_info" in result
        assert "constraints" in result
        assert "ai_guide" in result
        assert "solution_code" in result
        
        # basic_info 확인
        assert result["basic_info"]["problem_id"] == "2098"
        assert result["basic_info"]["title"] == "외판원 순회"
    
    def test_get_problem_info_sync_not_existing(self):
        """존재하지 않는 spec_id로 조회 테스트"""
        result = get_problem_info_sync(999)
        
        # 기본값 구조 확인
        assert "basic_info" in result
        assert "constraints" in result
        assert "ai_guide" in result
        assert result["basic_info"]["problem_id"] == "999"
        assert result["basic_info"]["title"] == ""
    
    @pytest.mark.asyncio
    async def test_get_problem_info_async_existing(self):
        """비동기 함수로 존재하는 spec_id 조회 테스트"""
        result = await get_problem_info(10)
        
        assert "basic_info" in result
        assert "constraints" in result
        assert "ai_guide" in result
        assert result["basic_info"]["problem_id"] == "2098"
    
    @pytest.mark.asyncio
    async def test_get_problem_info_async_not_existing(self):
        """비동기 함수로 존재하지 않는 spec_id 조회 테스트"""
        result = await get_problem_info(999)
        
        assert "basic_info" in result
        assert result["basic_info"]["problem_id"] == "999"


class TestPromptGeneration:
    """프롬프트 생성 함수 테스트"""
    
    def test_intent_analysis_prompt_with_problem_context(self):
        """Intent Analyzer 프롬프트에 문제 정보 포함 확인"""
        problem_context = get_problem_info_sync(10)
        prompt = create_intent_analysis_system_prompt(problem_context)
        
        # 문제 정보가 포함되어 있는지 확인
        assert "외판원 순회" in prompt
        assert "2098" in prompt
        assert "Dynamic Programming" in prompt or "Bitmasking" in prompt
    
    def test_intent_analysis_prompt_without_problem_context(self):
        """Intent Analyzer 프롬프트 (문제 정보 없음)"""
        prompt = create_intent_analysis_system_prompt(None)
        
        # 기본 프롬프트 구조 확인
        assert "보안관" in prompt or "Gatekeeper" in prompt
        assert "정답 코드 유출 방지" in prompt
    
    def test_writer_prompt_with_problem_context(self):
        """Writer LLM 프롬프트에 문제 정보 포함 확인"""
        problem_context = get_problem_info_sync(10)
        prompt = create_normal_system_prompt(
            status="SAFE",
            guide_strategy="LOGIC_HINT",
            keywords="비트마스킹, DP",
            memory_summary="",
            problem_context=problem_context
        )
        
        # 문제 정보가 포함되어 있는지 확인
        assert "외판원 순회" in prompt
        assert "2098" in prompt
        assert "Dynamic Programming" in prompt or "Bitmasking" in prompt
        
        # 힌트 로드맵이 포함되어 있는지 확인
        assert "힌트 로드맵" in prompt or "1단계" in prompt
    
    def test_writer_prompt_without_problem_context(self):
        """Writer LLM 프롬프트 (문제 정보 없음)"""
        prompt = create_normal_system_prompt(
            status="SAFE",
            guide_strategy="LOGIC_HINT",
            keywords="비트마스킹",
            memory_summary="",
            problem_context=None
        )
        
        # 기본 프롬프트 구조 확인
        assert "소크라테스" in prompt or "튜터" in prompt
        assert "LOGIC_HINT" in prompt
    
    def test_holistic_prompt_with_problem_context(self):
        """Holistic Evaluator 프롬프트에 문제 정보 포함 확인"""
        problem_context = get_problem_info_sync(10)
        prompt = create_holistic_system_prompt(problem_context)
        
        # 문제 정보가 포함되어 있는지 확인
        assert "외판원 순회" in prompt
        assert "Dynamic Programming" in prompt or "Bitmasking" in prompt
        
        # 힌트 로드맵이 포함되어 있는지 확인
        assert "힌트 로드맵" in prompt or "1단계" in prompt
    
    def test_holistic_prompt_without_problem_context(self):
        """Holistic Evaluator 프롬프트 (문제 정보 없음)"""
        prompt = create_holistic_system_prompt(None)
        
        # 기본 프롬프트 구조 확인
        assert "Chaining 전략" in prompt
        assert "문제 분해" in prompt


class TestStateIntegration:
    """State 통합 테스트"""
    
    def test_handle_request_problem_context(self):
        """handle_request에서 problem_context 저장 확인"""
        from app.domain.langgraph.nodes.handle_request import handle_request_load_state
        from app.domain.langgraph.graph import get_initial_state
        
        # get_initial_state로 초기 상태 생성
        initial_state = get_initial_state(
            session_id="test-session",
            exam_id=1,
            participant_id=1,
            spec_id=10
        )
        
        # problem_context가 저장되어 있는지 확인
        assert "problem_context" in initial_state
        assert initial_state["problem_context"] is not None
        
        # 개별 필드도 동기화되어 있는지 확인
        assert initial_state["problem_id"] == "2098"
        assert initial_state["problem_name"] == "외판원 순회"
        assert initial_state["problem_algorithm"] is not None
        
        # problem_context 구조 확인
        problem_context = initial_state["problem_context"]
        assert "basic_info" in problem_context
        assert problem_context["basic_info"]["problem_id"] == "2098"







