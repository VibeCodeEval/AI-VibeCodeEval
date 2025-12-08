"""
Node 4 (Turn Evaluator) Unit Test

각 평가 함수를 개별적으로 테스트합니다.
user, ai message를 입력받아 Turn별 평가를 수행합니다.
"""
import pytest
import asyncio
from typing import Dict, Any

from app.domain.langgraph.nodes.turn_evaluator.evaluators import (
    eval_generation,
    eval_optimization,
    eval_debugging,
    eval_test_case,
    eval_hint_query,
    eval_follow_up,
    eval_system_prompt,
    eval_rule_setting,
)
from app.domain.langgraph.nodes.turn_evaluator.analysis import intent_analysis
from app.domain.langgraph.states import EvalTurnState


@pytest.fixture
def sample_problem_context():
    """테스트용 문제 정보"""
    return {
        "basic_info": {
            "title": "외판원 순회 (TSP)",
            "problem_id": "2098",
        },
        "ai_guide": {
            "key_algorithms": ["DP", "Bitmasking"],
        },
    }


@pytest.fixture
def base_eval_state(sample_problem_context) -> EvalTurnState:
    """기본 EvalTurnState 생성"""
    return {
        "session_id": "test_session",
        "turn": 1,
        "human_message": "",
        "ai_message": "",
        "problem_context": sample_problem_context,
        "is_guardrail_failed": False,
        "guardrail_message": None,
        "intent_types": None,
        "intent_confidence": 0.0,
        "system_prompt_eval": None,
        "rule_setting_eval": None,
        "generation_eval": None,
        "optimization_eval": None,
        "debugging_eval": None,
        "test_case_eval": None,
        "hint_query_eval": None,
        "follow_up_eval": None,
        "llm_answer_summary": None,
        "eval_tokens": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }


class TestIntentAnalysis:
    """의도 분석 테스트"""
    
    @pytest.mark.asyncio
    async def test_intent_analysis_generation(self, base_eval_state):
        """코드 생성 의도 분석 테스트"""
        state = base_eval_state.copy()
        state["human_message"] = "외판원 순회 문제를 풀기 위해 비트마스킹 DP 코드를 작성해주세요."
        state["ai_message"] = "네, 비트마스킹 DP를 사용한 외판원 순회 코드를 작성해드리겠습니다."
        
        result = await intent_analysis(state)
        
        assert "intent_types" in result
        assert len(result["intent_types"]) > 0
        assert "intent_confidence" in result
        assert result["intent_confidence"] >= 0.0
        assert result["intent_confidence"] <= 1.0
        print(f"\n[Intent Analysis] 의도: {result['intent_types']}, 신뢰도: {result['intent_confidence']:.2f}")
    
    @pytest.mark.asyncio
    async def test_intent_analysis_hint_query(self, base_eval_state):
        """힌트/질의 의도 분석 테스트"""
        state = base_eval_state.copy()
        state["human_message"] = "점화식 힌트를 주세요."
        state["ai_message"] = "점화식은 다음과 같습니다: dp[current][visited] = min(...)"
        
        result = await intent_analysis(state)
        
        assert "intent_types" in result
        print(f"\n[Intent Analysis] 의도: {result['intent_types']}, 신뢰도: {result['intent_confidence']:.2f}")


class TestGenerationEvaluation:
    """코드 생성 평가 테스트"""
    
    @pytest.mark.asyncio
    async def test_eval_generation_basic(self, base_eval_state):
        """기본 코드 생성 평가 테스트"""
        state = base_eval_state.copy()
        state["human_message"] = "외판원 순회 문제를 풀기 위해 비트마스킹 DP 코드를 작성해주세요."
        state["ai_message"] = "네, 비트마스킹 DP를 사용한 외판원 순회 코드를 작성해드리겠습니다."
        
        result = await eval_generation(state)
        
        assert "generation_eval" in result
        eval_result = result["generation_eval"]
        assert "intent" in eval_result
        assert "score" in eval_result
        assert "rubrics" in eval_result
        assert "final_reasoning" in eval_result
        
        assert 0 <= eval_result["score"] <= 100
        assert len(eval_result["rubrics"]) == 5  # 5가지 평가 기준
        
        # 각 rubric에 reasoning 필드 확인
        for rubric in eval_result["rubrics"]:
            assert "criterion" in rubric
            assert "score" in rubric
            assert "reasoning" in rubric
            assert 0 <= rubric["score"] <= 100
        
        print(f"\n[Generation Evaluation]")
        print(f"  Intent: {eval_result['intent']}")
        print(f"  Score: {eval_result['score']:.2f}")
        print(f"  Final Reasoning: {eval_result['final_reasoning'][:100]}...")
    
    @pytest.mark.asyncio
    async def test_eval_generation_with_examples(self, base_eval_state):
        """예시가 포함된 코드 생성 평가 테스트"""
        state = base_eval_state.copy()
        state["human_message"] = """
        외판원 순회 문제를 풀기 위해 비트마스킹 DP 코드를 작성해주세요.
        
        [제약 조건]
        - 시간 복잡도: O(N^2 * 2^N)
        - 입력: sys.stdin.readline 사용
        
        [예시]
        입력:
        4
        0 10 15 20
        5 0 9 10
        6 13 0 12
        8 8 9 0
        
        출력: 35
        """
        state["ai_message"] = "네, 요청하신 제약 조건을 반영하여 코드를 작성하겠습니다."
        
        result = await eval_generation(state)
        
        eval_result = result["generation_eval"]
        print(f"\n[Generation Evaluation with Examples]")
        print(f"  Score: {eval_result['score']:.2f}")
        print(f"  Rubrics:")
        for rubric in eval_result["rubrics"]:
            print(f"    - {rubric['criterion']}: {rubric['score']:.2f}")


class TestOptimizationEvaluation:
    """최적화 평가 테스트"""
    
    @pytest.mark.asyncio
    async def test_eval_optimization(self, base_eval_state):
        """최적화 평가 테스트"""
        state = base_eval_state.copy()
        state["human_message"] = "현재 코드의 시간 복잡도를 O(N^2 * 2^N)으로 최적화해주세요."
        state["ai_message"] = "네, 메모이제이션을 활용하여 최적화하겠습니다."
        
        result = await eval_optimization(state)
        
        assert "optimization_eval" in result
        eval_result = result["optimization_eval"]
        assert "score" in eval_result
        assert "rubrics" in eval_result
        
        print(f"\n[Optimization Evaluation] Score: {eval_result['score']:.2f}")


class TestDebuggingEvaluation:
    """디버깅 평가 테스트"""
    
    @pytest.mark.asyncio
    async def test_eval_debugging(self, base_eval_state):
        """디버깅 평가 테스트"""
        state = base_eval_state.copy()
        state["human_message"] = "코드에서 메모리 초과 오류가 발생하는데, 원인을 찾아주세요."
        state["ai_message"] = "메모리 초과는 DP 테이블 크기 문제일 수 있습니다."
        
        result = await eval_debugging(state)
        
        assert "debugging_eval" in result
        eval_result = result["debugging_eval"]
        assert "score" in eval_result
        
        print(f"\n[Debugging Evaluation] Score: {eval_result['score']:.2f}")


class TestHintQueryEvaluation:
    """힌트/질의 평가 테스트"""
    
    @pytest.mark.asyncio
    async def test_eval_hint_query(self, base_eval_state):
        """힌트/질의 평가 테스트"""
        state = base_eval_state.copy()
        state["human_message"] = "점화식 수립을 위한 힌트를 주세요."
        state["ai_message"] = "점화식은 다음과 같이 수립할 수 있습니다: dp[current][visited] = min(...)"
        
        result = await eval_hint_query(state)
        
        assert "hint_query_eval" in result
        eval_result = result["hint_query_eval"]
        assert "score" in eval_result
        
        print(f"\n[Hint Query Evaluation] Score: {eval_result['score']:.2f}")


class TestIntentBasedEvaluation:
    """의도 분석 기반 평가 테스트 (실제 동작 시뮬레이션)"""
    
    @pytest.mark.asyncio
    async def test_intent_based_evaluation_flow(self, base_eval_state):
        """
        실제 동작 시뮬레이션: 의도 분석 -> 해당 평가 함수만 실행
        
        실제 Node 4 동작:
        1. intent_analysis: 단일 의도 선택 (우선순위 기반)
        2. intent_router: 선택된 의도에 따라 해당 평가 노드만 반환
        3. LangGraph가 해당 노드만 실행
        """
        test_cases = [
            {
                "name": "Generation",
                "human": "외판원 순회 문제를 풀기 위해 비트마스킹 DP 코드를 작성해주세요.",
                "ai": "네, 비트마스킹 DP를 사용한 외판원 순회 코드를 작성해드리겠습니다.",
                "expected_intent": "generation",
                "eval_func": eval_generation,
                "key": "generation_eval",
            },
            {
                "name": "Optimization",
                "human": "현재 코드의 시간 복잡도를 O(N^2 * 2^N)으로 최적화해주세요.",
                "ai": "네, 메모이제이션을 활용하여 최적화하겠습니다.",
                "expected_intent": "optimization",
                "eval_func": eval_optimization,
                "key": "optimization_eval",
            },
            {
                "name": "Debugging",
                "human": "코드에서 메모리 초과 오류가 발생하는데, 원인을 찾아주세요.",
                "ai": "메모리 초과는 DP 테이블 크기 문제일 수 있습니다.",
                "expected_intent": "debugging",
                "eval_func": eval_debugging,
                "key": "debugging_eval",
            },
            {
                "name": "Hint Query",
                "human": "점화식 수립을 위한 힌트를 주세요.",
                "ai": "점화식은 다음과 같이 수립할 수 있습니다: dp[current][visited] = min(...)",
                "expected_intent": "hint_or_query",
                "eval_func": eval_hint_query,
                "key": "hint_query_eval",
            },
        ]
        
        for test_case in test_cases:
            # 1. 의도 분석 먼저 실행
            state = base_eval_state.copy()
            state["human_message"] = test_case["human"]
            state["ai_message"] = test_case["ai"]
            
            intent_result = await intent_analysis(state)
            
            # 의도 분석 결과 확인
            assert "intent_types" in intent_result
            assert len(intent_result["intent_types"]) > 0
            
            detected_intent = intent_result["intent_types"][0]
            print(f"\n[{test_case['name']} Test]")
            print(f"  Expected Intent: {test_case['expected_intent']}")
            print(f"  Detected Intent: {detected_intent}")
            
            # 2. 의도 분석 결과를 state에 반영
            state["intent_types"] = intent_result["intent_types"]
            state["intent_confidence"] = intent_result["intent_confidence"]
            
            # 3. 해당 의도의 평가 함수만 실행 (실제 동작 시뮬레이션)
            eval_result = await test_case["eval_func"](state)
            
            # 4. 결과 확인
            assert test_case["key"] in eval_result
            eval_data = eval_result[test_case["key"]]
            assert "score" in eval_data
            assert "rubrics" in eval_data
            assert "final_reasoning" in eval_data
            assert len(eval_data["rubrics"]) == 5
            
            print(f"  Score: {eval_data['score']:.2f}")
            print(f"  Rubrics: {len(eval_data['rubrics'])}개")
            print(f"  Confidence: {intent_result['intent_confidence']:.2f}")


class TestAllEvaluationFunctions:
    """모든 평가 함수 개별 테스트 (의도 분석 없이 직접 호출)"""
    
    @pytest.mark.asyncio
    async def test_all_evaluation_functions_direct(self, base_eval_state):
        """
        모든 평가 함수를 직접 호출하여 테스트
        (실제 동작과는 다르지만, 각 함수의 동작 확인용)
        """
        test_cases = [
            {
                "name": "Generation",
                "human": "비트마스킹 DP 코드를 작성해주세요.",
                "ai": "네, 코드를 작성하겠습니다.",
                "eval_func": eval_generation,
                "key": "generation_eval",
            },
            {
                "name": "Optimization",
                "human": "코드를 최적화해주세요.",
                "ai": "네, 최적화하겠습니다.",
                "eval_func": eval_optimization,
                "key": "optimization_eval",
            },
            {
                "name": "Debugging",
                "human": "버그를 수정해주세요.",
                "ai": "네, 버그를 찾아 수정하겠습니다.",
                "eval_func": eval_debugging,
                "key": "debugging_eval",
            },
            {
                "name": "Hint Query",
                "human": "힌트를 주세요.",
                "ai": "힌트를 제공하겠습니다.",
                "eval_func": eval_hint_query,
                "key": "hint_query_eval",
            },
            {
                "name": "Test Case",
                "human": "테스트 케이스를 작성해주세요.",
                "ai": "네, 테스트 케이스를 작성하겠습니다.",
                "eval_func": eval_test_case,
                "key": "test_case_eval",
            },
            {
                "name": "Follow Up",
                "human": "추가로 질문이 있습니다.",
                "ai": "네, 무엇이 궁금하신가요?",
                "eval_func": eval_follow_up,
                "key": "follow_up_eval",
            },
            {
                "name": "System Prompt",
                "human": "당신은 알고리즘 튜터입니다.",
                "ai": "네, 알고리즘 튜터 역할을 수행하겠습니다.",
                "eval_func": eval_system_prompt,
                "key": "system_prompt_eval",
            },
            {
                "name": "Rule Setting",
                "human": "[제약 조건] 시간 복잡도는 O(N^2)이어야 합니다.",
                "ai": "네, 제약 조건을 반영하겠습니다.",
                "eval_func": eval_rule_setting,
                "key": "rule_setting_eval",
            },
        ]
        
        for test_case in test_cases:
            state = base_eval_state.copy()
            state["human_message"] = test_case["human"]
            state["ai_message"] = test_case["ai"]
            
            result = await test_case["eval_func"](state)
            
            assert test_case["key"] in result
            eval_result = result[test_case["key"]]
            assert "score" in eval_result
            assert "rubrics" in eval_result
            assert "final_reasoning" in eval_result
            
            print(f"\n[{test_case['name']} Evaluation (Direct)]")
            print(f"  Score: {eval_result['score']:.2f}")
            print(f"  Rubrics: {len(eval_result['rubrics'])}개")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])


