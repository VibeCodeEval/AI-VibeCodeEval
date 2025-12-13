"""
제출 플로우 Unit Test (Graph만 테스트)

[목적]
- prompt_messages를 DB에 저장하지 않고 Graph만 테스트
- 4번 노드와 6.a 노드의 동작 확인
- Redis turn_logs 저장/조회 확인
- prompt_evaluation 저장 확인

[사용법]
uv run python test_scripts/test_submit_flow_unit.py
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, Any, List

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from langchain_core.messages import HumanMessage, AIMessage
from app.domain.langgraph.states import MainGraphState
from app.domain.langgraph.graph import create_main_graph
from app.domain.langgraph.utils.problem_info import get_problem_info_sync
from app.infrastructure.cache.redis_client import redis_client


def create_test_state(
    session_id: str = "test_session_1",
    messages: List[Dict[str, Any]] = None,
    current_turn: int = None,
    problem_id: int = 1,
    spec_version: int = 10
) -> MainGraphState:
    """
    테스트용 State 생성
    
    Args:
        session_id: 세션 ID
        messages: 메시지 리스트 (없으면 기본 메시지 생성)
        current_turn: 현재 턴 (없으면 messages 길이 기반으로 계산)
        problem_id: 문제 ID
        spec_version: 스펙 버전
    """
    if messages is None:
        # 기본 테스트 메시지 생성
        messages = [
            HumanMessage(
                content="외판원 순회 문제를 풀고 싶어요. 어떻게 시작해야 할까요?",
                additional_kwargs={"turn": 1, "role": "user"}
            ),
            AIMessage(
                content="외판원 순회 문제는 여러 도시를 한 번씩만 방문하고 시작점으로 돌아오는 최단 경로를 찾는 문제입니다. 동적 계획법이나 백트래킹을 사용할 수 있습니다.",
                additional_kwargs={"turn": 1, "role": "assistant"}
            ),
            HumanMessage(
                content="동적 계획법으로 풀어보고 싶어요. 힌트를 주실 수 있나요?",
                additional_kwargs={"turn": 2, "role": "user"}
            ),
            AIMessage(
                content="동적 계획법을 사용하려면, 방문한 도시 집합과 현재 위치를 상태로 사용하는 점화식을 세울 수 있습니다. 비트마스킹을 활용하면 집합을 효율적으로 표현할 수 있습니다.",
                additional_kwargs={"turn": 2, "role": "assistant"}
            ),
            HumanMessage(
                content="비트마스킹을 사용한 코드를 작성해주세요.",
                additional_kwargs={"turn": 3, "role": "user"}
            ),
            AIMessage(
                content="비트마스킹을 사용한 외판원 순회 문제 해결 코드를 제공하겠습니다:\n\n```python\ndef tsp_dp(dist):\n    n = len(dist)\n    # dp[mask][pos]: mask 집합의 도시를 방문하고 pos에 있을 때의 최소 비용\n    dp = [[float('inf')] * n for _ in range(1 << n)]\n    dp[1][0] = 0  # 시작점 (도시 0)\n    \n    for mask in range(1, 1 << n):\n        for pos in range(n):\n            if not (mask & (1 << pos)):\n                continue\n            for next_pos in range(n):\n                if mask & (1 << next_pos):\n                    continue\n                new_mask = mask | (1 << next_pos)\n                dp[new_mask][next_pos] = min(\n                    dp[new_mask][next_pos],\n                    dp[mask][pos] + dist[pos][next_pos]\n                )\n    \n    # 시작점으로 돌아오는 경로 추가\n    result = float('inf')\n    for pos in range(1, n):\n        result = min(result, dp[(1 << n) - 1][pos] + dist[pos][0])\n    \n    return result\n```",
                additional_kwargs={"turn": 3, "role": "assistant"}
            )
        ]
    
    # turn 속성 추가 (LangChain 메시지 객체에)
    for i, msg in enumerate(messages):
        if isinstance(msg, (HumanMessage, AIMessage)):
            # turn 계산: 0,1 -> turn 1, 2,3 -> turn 2, ...
            turn = (i // 2) + 1
            if not hasattr(msg, "turn"):
                msg.turn = turn
            if not hasattr(msg, "role"):
                msg.role = "user" if isinstance(msg, HumanMessage) else "assistant"
    
    if current_turn is None:
        current_turn = (len(messages) // 2) + 1
    
    # 문제 정보 가져오기
    problem_info = get_problem_info_sync(problem_id, spec_version)
    
    state: MainGraphState = {
        "session_id": session_id,
        "messages": messages,
        "current_turn": current_turn,
        "problem_id": problem_id,
        "spec_version": spec_version,
        "problem_context": problem_info,
        "code_content": None,  # 제출 시 설정
        "intent": "PASSED_SUBMIT",  # 제출 의도
        "turn_scores": {},
        "holistic_flow_score": None,
        "holistic_flow_analysis": None,
    }
    
    return state


async def test_submit_flow():
    """제출 플로우 테스트"""
    print("=" * 80)
    print("제출 플로우 Unit Test")
    print("=" * 80)
    print()
    
    # 1. 테스트 State 생성
    session_id = "test_session_1"
    state = create_test_state(
        session_id=session_id,
        current_turn=4,  # 3턴까지 대화, 4턴에서 제출
        problem_id=1,
        spec_version=10
    )
    
    print(f"✅ 테스트 State 생성 완료")
    print(f"   - Session ID: {session_id}")
    print(f"   - Current Turn: {state['current_turn']}")
    print(f"   - Messages 개수: {len(state['messages'])}")
    print(f"   - Problem ID: {state['problem_id']}")
    print(f"   - Spec Version: {state['spec_version']}")
    print()
    
    # 2. 코드 내용 추가 (제출용)
    code_content = """def tsp_dp(dist):
    n = len(dist)
    dp = [[float('inf')] * n for _ in range(1 << n)]
    dp[1][0] = 0
    
    for mask in range(1, 1 << n):
        for pos in range(n):
            if not (mask & (1 << pos)):
                continue
            for next_pos in range(n):
                if mask & (1 << next_pos):
                    continue
                new_mask = mask | (1 << next_pos)
                dp[new_mask][next_pos] = min(
                    dp[new_mask][next_pos],
                    dp[mask][pos] + dist[pos][next_pos]
                )
    
    result = float('inf')
    for pos in range(1, n):
        result = min(result, dp[(1 << n) - 1][pos] + dist[pos][0])
    
    return result
"""
    state["code_content"] = code_content
    print(f"✅ 코드 내용 추가 완료")
    print()
    
    # 3. Graph 생성
    from langgraph.checkpoint.memory import MemorySaver
    checkpointer = MemorySaver()
    graph = create_main_graph(checkpointer)
    
    print(f"✅ Graph 생성 완료")
    print()
    
    # 4. Graph 실행 (제출 플로우)
    print("=" * 80)
    print("Graph 실행 시작 (제출 플로우)")
    print("=" * 80)
    print()
    
    config = {
        "configurable": {
            "thread_id": session_id
        }
    }
    
    try:
        # Graph 실행
        result = await graph.ainvoke(state, config)
        
        print()
        print("=" * 80)
        print("✅ Graph 실행 완료")
        print("=" * 80)
        print()
        
        # 5. 결과 확인
        print("📊 실행 결과:")
        print(f"   - Turn Scores: {result.get('turn_scores', {})}")
        print(f"   - Holistic Flow Score: {result.get('holistic_flow_score')}")
        print(f"   - Holistic Flow Analysis: {result.get('holistic_flow_analysis', '')[:100]}...")
        print()
        
        # 6. Redis turn_logs 확인
        print("=" * 80)
        print("Redis turn_logs 확인")
        print("=" * 80)
        print()
        
        all_turn_logs = await redis_client.get_all_turn_logs(session_id)
        print(f"✅ Redis turn_logs 조회 완료 - 턴 개수: {len(all_turn_logs)}")
        print()
        
        for turn_num in sorted([int(k) for k in all_turn_logs.keys()]):
            turn_log = all_turn_logs[str(turn_num)]
            print(f"📋 Turn {turn_num}:")
            print(f"   - Intent: {turn_log.get('prompt_evaluation_details', {}).get('intent', 'UNKNOWN')}")
            print(f"   - Score: {turn_log.get('prompt_evaluation_details', {}).get('score', 0)}")
            print(f"   - User Prompt Summary: {turn_log.get('user_prompt_summary', '')[:50]}...")
            print()
        
        # 7. PostgreSQL prompt_evaluations 확인 (선택적)
        print("=" * 80)
        print("PostgreSQL prompt_evaluations 확인 (선택적)")
        print("=" * 80)
        print()
        
        try:
            from app.infrastructure.persistence.session import get_db_context
            from sqlalchemy import text
            
            # session_id에서 숫자 추출 (test_session_1 -> 1)
            postgres_session_id = int(session_id.replace("test_session_", "")) if "test_session_" in session_id else None
            
            if postgres_session_id:
                async with get_db_context() as db:
                    # TURN_EVAL 조회
                    turn_evals = await db.execute(
                        text("""
                            SELECT turn, evaluation_type, details->>'score' as score, created_at
                            FROM ai_vibe_coding_test.prompt_evaluations
                            WHERE session_id = :session_id AND evaluation_type = 'TURN_EVAL'
                            ORDER BY turn
                        """),
                        {"session_id": postgres_session_id}
                    )
                    turn_eval_rows = turn_evals.fetchall()
                    
                    print(f"✅ TURN_EVAL 평가 결과: {len(turn_eval_rows)}개")
                    for row in turn_eval_rows:
                        print(f"   - Turn {row.turn}: Score {row.score}, Created: {row.created_at}")
                    print()
                    
                    # HOLISTIC_FLOW 조회
                    holistic_evals = await db.execute(
                        text("""
                            SELECT evaluation_type, details->>'overall_flow_score' as score, created_at
                            FROM ai_vibe_coding_test.prompt_evaluations
                            WHERE session_id = :session_id AND evaluation_type = 'HOLISTIC_FLOW'
                            ORDER BY created_at DESC
                            LIMIT 1
                        """),
                        {"session_id": postgres_session_id}
                    )
                    holistic_row = holistic_evals.fetchone()
                    
                    if holistic_row:
                        print(f"✅ HOLISTIC_FLOW 평가 결과:")
                        print(f"   - Score: {holistic_row.score}")
                        print(f"   - Created: {holistic_row.created_at}")
                    else:
                        print("⚠️  HOLISTIC_FLOW 평가 결과 없음 (6.a 노드가 실행되지 않았을 수 있음)")
                    print()
            else:
                print("⚠️  PostgreSQL 세션 ID를 추출할 수 없음 (test_session_1 형식이 아님)")
                print()
        except Exception as e:
            print(f"⚠️  PostgreSQL 확인 실패: {str(e)}")
            print("   (DB 연결 실패 또는 세션이 존재하지 않을 수 있음)")
            print()
        
        print("=" * 80)
        print("✅ 테스트 완료")
        print("=" * 80)
        
    except Exception as e:
        print()
        print("=" * 80)
        print(f"❌ Graph 실행 실패: {str(e)}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(test_submit_flow())












