"""
Node 4 (Turn Evaluator) Unit Test

각 평가 함수를 개별적으로 테스트합니다.
user, ai message를 입력받아 Turn별 평가를 수행합니다.
"""
import pytest
from typing import Dict, Any

pytestmark = pytest.mark.llm

from app.domain.langgraph.nodes.eval_turn.evaluators import (
    eval_debugging,
    eval_exploration,
    eval_follow_up,
    eval_generation,
    eval_hint_query,
    eval_optimization,
    eval_rule_setting,
    eval_system_prompt,
    eval_test_case,
)
from app.domain.langgraph.nodes.eval_turn.analysis import intent_analysis
from app.domain.langgraph.states import EvalTurnState

# V3.0 eval_turn.yaml — intent_rubric_gates 와 동기 (적용 가능한 R 태그만)
V3_ALLOWED_APPLIED_BY_INTENT: dict[str, frozenset[str]] = {
    "SETTING": frozenset({"R2", "R3"}),
    "CREATION": frozenset({"R1", "R2", "R3"}),
    "REFINEMENT": frozenset({"R1", "R2", "R3", "R4"}),
    "DEBUGGING": frozenset({"R1", "R2", "R4"}),
    "EXPLORATION": frozenset({"R1", "R2"}),
    "FOLLOW_UP": frozenset({"R4"}),
    # 레거시 eval_hint_query 직접 호출용 (짧은 힌트에서 R3 포함 가능)
    "HINT_QUERY": frozenset({"R1", "R2", "R3"}),
}
_RUBRIC_TAGS = frozenset({"R1", "R2", "R3", "R4"})


def assert_v3_turn_rubric(eval_data: dict, *, allowed_applied: frozenset[str]) -> None:
    """V3 턴 평가: rubric_breakdown + applied_rubrics + turn_score, rubrics 리스트는 비어 있음."""
    assert "score" in eval_data
    assert 0 <= eval_data["score"] <= 100
    assert eval_data.get("rubrics") == []
    assert "rubric_breakdown" in eval_data
    assert "applied_rubrics" in eval_data
    assert "turn_score" in eval_data
    ts = eval_data["turn_score"]
    assert ts is None or (isinstance(ts, int) and 1 <= ts <= 5)

    applied = eval_data["applied_rubrics"]
    assert isinstance(applied, list)
    assert len(applied) >= 1, "V3: applied_rubrics 비어 있음 (LLM/파싱 실패 가능)"
    for tag in applied:
        assert tag in _RUBRIC_TAGS
        assert tag in allowed_applied, f"허용 집합 위반: {tag} not in {allowed_applied}"

    bd = eval_data["rubric_breakdown"]
    assert isinstance(bd, dict)
    assert len(bd) >= 1
    for _k, v in bd.items():
        assert isinstance(v, int) and 1 <= v <= 5

    for tag in applied:
        assert any(
            str(k).upper().startswith(tag) for k in bd
        ), f"rubric_breakdown에 {tag} 대응 키 없음: {list(bd)}"


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
        "turn": 2,
        "human_message": "",
        "ai_message": "",
        "previous_turns_summary": None,
        "problem_context": sample_problem_context,
        "is_guardrail_failed": False,
        "guardrail_message": None,
        "intent_types": None,
        "intent_confidence": 0.0,
        "unified_intent": None,
        "system_prompt_eval": None,
        "rule_setting_eval": None,
        "generation_eval": None,
        "optimization_eval": None,
        "debugging_eval": None,
        "test_case_eval": None,
        "hint_query_eval": None,
        "exploration_eval": None,
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
        # v2.1: 5대 통합 의도 (FOLLOW_UP 독립)
        assert "unified_intent" in result
        assert result["unified_intent"] in (
            "SETTING",
            "CREATION",
            "REFINEMENT",
            "DEBUGGING",
            "EXPLORATION",
            "FOLLOW_UP",
            "VALIDATION",  # 구버전 저장 호환
        )
        print(f"\n[Intent Analysis] 의도: {result['intent_types']}, unified_intent: {result['unified_intent']}, 신뢰도: {result['intent_confidence']:.2f}")
    
    @pytest.mark.asyncio
    async def test_intent_analysis_hint_query(self, base_eval_state):
        """힌트/질의 의도 분석 테스트"""
        state = base_eval_state.copy()
        state["human_message"] = "점화식 힌트를 주세요."
        state["ai_message"] = "점화식은 다음과 같습니다: dp[current][visited] = min(...)"
        
        result = await intent_analysis(state)
        
        assert "intent_types" in result
        assert "unified_intent" in result
        assert result["unified_intent"] in (
            "SETTING",
            "CREATION",
            "REFINEMENT",
            "DEBUGGING",
            "EXPLORATION",
            "FOLLOW_UP",
            "VALIDATION",  # 구버전 저장 호환
        )
        print(f"\n[Intent Analysis] 의도: {result['intent_types']}, unified_intent: {result['unified_intent']}, 신뢰도: {result['intent_confidence']:.2f}")


class TestGenerationEvaluation:
    """코드 생성 평가 테스트 (V3 루브릭)"""

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
        assert "score" in eval_result
        print(f"\n[Generation Evaluation with Examples]")
        print(f"  Score: {eval_result['score']:.2f}")
        print(f"  applied_rubrics: {eval_result.get('applied_rubrics')}")


class TestOptimizationEvaluation:
    """최적화 평가 테스트 (V3 루브릭)"""

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

        print(f"\n[Optimization Evaluation] Score: {eval_result['score']:.2f}")


class TestDebuggingEvaluation:
    """디버깅 평가 테스트 (V3 루브릭)"""

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


class TestV3RubricSixUnifiedIntents:
    """
    V3.0 루브릭 검증: 6대 통합 의도별 평가 노드 1건씩 (eval_turn.yaml intent_rubric_gates).
    LLM 호출 포함 — API 키·쿼터 필요.
    """

    @pytest.mark.asyncio
    async def test_v3_rubric_setting(self, base_eval_state):
        state = base_eval_state.copy()
        state["human_message"] = (
            "<Role>알고리즘 튜터</Role><Content>앞으로는 한국어로만 답하고, "
            "코드는 타입 힌트를 붙여 줘.</Content>"
        )
        state["ai_message"] = "네, 이후 답변에 반영하겠습니다."
        out = await eval_rule_setting(state)
        ev = out["rule_setting_eval"]
        assert_v3_turn_rubric(ev, allowed_applied=V3_ALLOWED_APPLIED_BY_INTENT["SETTING"])

    @pytest.mark.asyncio
    async def test_v3_rubric_creation(self, base_eval_state):
        state = base_eval_state.copy()
        state["human_message"] = (
            "파이썬으로 stdin 한 줄에서 두 정렬된 리스트를 읽어 병합하는 함수를 "
            "처음부터 작성해 주세요. 기존 코드 수정이 아닙니다."
        )
        state["ai_message"] = "요구사항에 맞춰 새 함수를 작성하겠습니다."
        out = await eval_generation(state)
        ev = out["generation_eval"]
        assert_v3_turn_rubric(ev, allowed_applied=V3_ALLOWED_APPLIED_BY_INTENT["CREATION"])

    @pytest.mark.asyncio
    async def test_v3_rubric_refinement(self, base_eval_state):
        state = base_eval_state.copy()
        state["previous_turns_summary"] = (
            "이전 턴: 사용자가 merge(a,b) 리스트 병합 함수를 받음. "
            "AI가 O(n) 두 포인터 구현을 제시함."
        )
        state["human_message"] = (
            "방금 준 merge 함수에서, 왼쪽 배열이 비었을 때만 오른쪽을 통째로 붙이도록 "
            "조건 분기만 수정해 주세요."
        )
        state["ai_message"] = "네, 해당 분기만 반영하겠습니다."
        out = await eval_optimization(state)
        ev = out["optimization_eval"]
        assert_v3_turn_rubric(ev, allowed_applied=V3_ALLOWED_APPLIED_BY_INTENT["REFINEMENT"])

    @pytest.mark.asyncio
    async def test_v3_rubric_debugging(self, base_eval_state):
        state = base_eval_state.copy()
        state["human_message"] = (
            "실행 시 `IndexError: list index out of range`가 납니다. "
            "Traceback 첫 줄: File \"sol.py\", line 12 in solve. "
            "재현: 입력 예시 [1,2,3] 일 때 항상 발생합니다."
        )
        state["ai_message"] = "인덱스 경계를 점검해 보세요."
        out = await eval_debugging(state)
        ev = out["debugging_eval"]
        assert_v3_turn_rubric(ev, allowed_applied=V3_ALLOWED_APPLIED_BY_INTENT["DEBUGGING"])

    @pytest.mark.asyncio
    async def test_v3_rubric_exploration(self, base_eval_state):
        state = base_eval_state.copy()
        state["human_message"] = (
            "TSP 외판원 순회에서 비트마스킹 DP가 왜 쓰이는지, "
            "시간 복잡도 관점에서만 개념 설명해 주세요. 코드 작성은 필요 없습니다."
        )
        state["ai_message"] = "상태를 비트로 압축하면 부분집합을 인덱스로 표현할 수 있어서…"
        out = await eval_exploration(state)
        ev = out["exploration_eval"]
        assert_v3_turn_rubric(ev, allowed_applied=V3_ALLOWED_APPLIED_BY_INTENT["EXPLORATION"])

    @pytest.mark.asyncio
    async def test_v3_rubric_follow_up(self, base_eval_state):
        state = base_eval_state.copy()
        state["previous_turns_summary"] = "이전 턴에서 O(n) 병합 방식을 합의함."
        state["human_message"] = "네, 알겠어요. 그 다음 단계로 진행해 주세요."
        state["ai_message"] = "다음으로 엣지 케이스 테스트를 추가할까요?"
        out = await eval_follow_up(state)
        ev = out["follow_up_eval"]
        assert_v3_turn_rubric(ev, allowed_applied=V3_ALLOWED_APPLIED_BY_INTENT["FOLLOW_UP"])


_EVAL_KEY_TO_UNIFIED_FOR_V3: dict[str, str] = {
    "generation_eval": "CREATION",
    "optimization_eval": "REFINEMENT",
    "debugging_eval": "DEBUGGING",
    # 레거시 노드: 짧은 힌트 문장에서 LLM이 R3까지 쓰는 경우가 있어 EXPLORATION보다 넓게 둠
    "hint_query_eval": "HINT_QUERY",
    # 테스트 케이스 요청은 구조·예시(R3)까지 쓰는 경우가 많아 REFINEMENT 게이트로 검증
    "test_case_eval": "REFINEMENT",
    "follow_up_eval": "FOLLOW_UP",
    "system_prompt_eval": "SETTING",
    "rule_setting_eval": "SETTING",
}


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
            unified = _EVAL_KEY_TO_UNIFIED_FOR_V3[test_case["key"]]
            assert_v3_turn_rubric(
                eval_result,
                allowed_applied=V3_ALLOWED_APPLIED_BY_INTENT[unified],
            )

            print(f"\n[{test_case['name']} Evaluation (Direct)]")
            print(f"  Score: {eval_result['score']:.2f}")
            print(f"  applied_rubrics: {eval_result.get('applied_rubrics')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])


