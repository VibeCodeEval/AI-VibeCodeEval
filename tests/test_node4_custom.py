"""
Node 4 (Turn Evaluator) 커스텀 테스트
실제 사용자 질문과 AI 답변으로 테스트
"""
import pytest
import asyncio
from typing import Dict, Any

from app.domain.langgraph.nodes.turn_evaluator.evaluators import eval_generation
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


@pytest.mark.asyncio
async def test_custom_user_ai_messages(base_eval_state):
    """실제 사용자 질문과 AI 답변으로 테스트"""
    
    # 실제 사용자 질문과 AI 답변 입력
    user_message = "외판원 순회 문제를 풀기 위해 비트마스킹 DP 코드를 작성해주세요."
    ai_message = """네, 비트마스킹 DP를 사용한 외판원 순회 코드를 작성해드리겠습니다.

다음과 같은 접근 방식을 사용합니다:

1. 비트마스크로 방문한 도시를 표현
2. DP 테이블에 현재 도시와 방문 상태를 저장
3. 모든 도시를 방문한 후 시작 도시로 돌아오는 최소 비용 계산

코드는 다음과 같습니다:
```python
import sys
input = sys.stdin.readline

def tsp(n, graph):
    # dp[현재도시][방문상태] = 최소비용
    dp = [[float('inf')] * (1 << n) for _ in range(n)]
    dp[0][1] = 0  # 시작 도시 0, 방문 상태 1 (0번 도시만 방문)
    
    for visited in range(1, 1 << n):
        for current in range(n):
            if not (visited & (1 << current)):
                continue
            if dp[current][visited] == float('inf'):
                continue
            
            # 다음 도시로 이동
            for next_city in range(n):
                if visited & (1 << next_city):
                    continue
                if graph[current][next_city] == 0:
                    continue
                
                next_visited = visited | (1 << next_city)
                dp[next_city][next_visited] = min(
                    dp[next_city][next_visited],
                    dp[current][visited] + graph[current][next_city]
                )
    
    # 모든 도시 방문 후 시작 도시로 돌아오기
    result = float('inf')
    final_visited = (1 << n) - 1
    for i in range(n):
        if graph[i][0] > 0:
            result = min(result, dp[i][final_visited] + graph[i][0])
    
    return result if result != float('inf') else -1

n = int(input())
graph = [list(map(int, input().split())) for _ in range(n)]
print(tsp(n, graph))
```"""
    
    state = base_eval_state.copy()
    state["human_message"] = user_message
    state["ai_message"] = ai_message
    
    print("\n" + "="*80)
    print("사용자 질문:")
    print(user_message)
    print("\n" + "-"*80)
    print("AI 답변:")
    print(ai_message[:200] + "..." if len(ai_message) > 200 else ai_message)
    print("="*80)
    
    # 1. 의도 분석
    print("\n[1단계] 의도 분석 중...")
    intent_result = await intent_analysis(state)
    
    print(f"  ✅ 감지된 의도: {intent_result['intent_types']}")
    print(f"  ✅ 신뢰도: {intent_result['intent_confidence']:.2f}")
    
    # 2. 평가 실행
    state["intent_types"] = intent_result["intent_types"]
    state["intent_confidence"] = intent_result["intent_confidence"]
    
    print("\n[2단계] Generation 평가 중...")
    eval_result = await eval_generation(state)
    
    # 3. 결과 출력
    generation_eval = eval_result["generation_eval"]
    
    print("\n" + "="*80)
    print("평가 결과:")
    print("="*80)
    print(f"의도: {generation_eval['intent']}")
    print(f"전체 점수: {generation_eval['score']:.2f}/100")
    print(f"\n루브릭별 점수:")
    for rubric in generation_eval["rubrics"]:
        print(f"  - {rubric['criterion']}: {rubric['score']:.2f}/100")
        print(f"    근거: {rubric['reasoning'][:100]}...")
    
    print(f"\n전체 평가 요약:")
    print(f"  {generation_eval['final_reasoning']}")
    print("="*80)
    
    # 검증
    assert "generation_eval" in eval_result
    assert generation_eval["score"] >= 0
    assert generation_eval["score"] <= 100
    assert len(generation_eval["rubrics"]) == 5
    assert "final_reasoning" in generation_eval


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])





