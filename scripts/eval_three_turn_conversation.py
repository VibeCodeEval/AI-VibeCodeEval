#!/usr/bin/env python
"""
3턴 대화를 V2.2 Context-Integrated Eval Turn으로 평가 (DB/Redis 불필요).

사용법:
    uv run python scripts/eval_three_turn_conversation.py
"""

import asyncio
import logging
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)

# 평가할 3턴 대화 (USER / AI)
TURNS = [
    {
        "human": "파이썬으로 재귀(recursion)를 사용한 팩토리얼 함수를 작성해줘.",
        "ai": """네, 파이썬으로 작성한 재귀 방식의 팩토리얼 함수입니다.

```python
def factorial_recursive(n):
    if n <= 1:
        return 1
    return n * factorial_recursive(n - 1)

print(factorial_recursive(5))  # 출력: 120
```""",
    },
    {
        "human": "그거 for문을 사용하는 반복문 방식으로 바꿔줘.",
        "ai": """네, 재귀 방식 대신 for문을 사용하여 반복문(Iteration) 방식으로 변경했습니다.

```python
def factorial_iterative(n):
    result = 1
    for i in range(1, n + 1):
        result *= i
    return result

print(factorial_iterative(5))  # 출력: 120
```""",
    },
    {
        "human": "좋아. 입력값이 음수일 때는 ValueError를 일으키도록 예외 처리를 추가해.",
        "ai": """네, 입력값이 음수일 경우 `ValueError`를 발생시키도록 예외 처리를 추가했습니다.

```python
def factorial_iterative(n):
    if n < 0:
        raise ValueError("입력값은 0 이상의 정수여야 합니다.")
    result = 1
    for i in range(1, n + 1):
        result *= i
    return result
```""",
    },
]


def make_initial_state(turn: int, human_message: str, ai_message: str, previous_turns_summary: str | None) -> dict:
    """Eval Turn SubGraph용 초기 상태."""
    return {
        "session_id": "eval_three_turn",
        "turn": turn,
        "human_message": human_message,
        "ai_message": ai_message,
        "previous_turns_summary": previous_turns_summary,
        "is_phase2_first_turn": False,
        "problem_context": None,
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
        "follow_up_eval": None,
        "answer_summary": None,
        "turn_log": None,
        "turn_score": None,
        "eval_tokens": None,
    }


async def run():
    from app.domain.langgraph.subgraph_eval_turn import create_eval_turn_subgraph

    subgraph = create_eval_turn_subgraph()
    previous_turns_summaries: list[str] = []

    print("\n" + "=" * 60)
    print("V2.2 Context-Integrated Eval Turn — 3턴 대화 평가")
    print("=" * 60)

    for idx, (turn_data) in enumerate(TURNS, 1):
        human = turn_data["human"]
        ai = turn_data["ai"]
        prev_summary = "\n\n".join(previous_turns_summaries) if previous_turns_summaries else None

        state = make_initial_state(idx, human, ai, prev_summary)
        result = await subgraph.ainvoke(state)

        turn_score = result.get("turn_score", 0)
        intent_types = result.get("intent_types") or []
        unified_intent = result.get("unified_intent", "")
        turn_log = result.get("turn_log") or {}
        reasoning = turn_log.get("comprehensive_reasoning", "") or result.get("answer_summary", "")

        print(f"\n--- Turn {idx} ---")
        print(f"  사용자: {human[:60]}{'...' if len(human) > 60 else ''}")
        print(f"  의도: {unified_intent or intent_types}")
        print(f"  턴 점수: {turn_score}")
        if reasoning:
            print(f"  평가 요약: {reasoning[:300]}{'...' if len(reasoning) > 300 else ''}")

        # 다음 턴용 이전 요약 누적 (Guard와 동일 형식)
        user_prompt_summary = human[:200] + "..." if len(human) > 200 else human
        llm_answer_summary = result.get("answer_summary", "") or ""
        previous_turns_summaries.append(
            f"[Turn {idx}] 사용자 요약: {user_prompt_summary}\nAI 요약: {llm_answer_summary}"
        )

    print("\n" + "=" * 60)
    print("평가 완료")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(run())
