"""
제출 플로우 테스트 (채팅부터 시작)

[목적]
- 채팅 API를 여러 번 호출하여 대화 생성
- Submit API 호출
- prompt_evaluations 테이블 저장 확인

[사용법]
1. 먼저 테스트 데이터 생성:
   uv run python test_scripts/setup_tsp_test_data.py

2. 서버 실행:
   uv run python scripts/run_dev.py

3. 이 스크립트 실행:
   uv run python test_scripts/test_submit_flow_with_chat.py
"""

import asyncio
import sys
import json
import httpx
from pathlib import Path
from typing import Dict, Any, Optional

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 기본 설정
BASE_URL = "http://localhost:8000"
TIMEOUT = 120  # 2분 타임아웃


async def send_chat_message(
    client: httpx.AsyncClient,
    session_id: int,
    participant_id: int,
    turn_id: int,
    content: str,
    problem_id: int = 1,
    spec_version: int = 10
) -> Dict[str, Any]:
    """
    채팅 메시지 전송
    
    Args:
        client: httpx 클라이언트
        session_id: 세션 ID
        participant_id: 참가자 ID
        turn_id: 턴 ID
        content: 메시지 내용
        problem_id: 문제 ID
        spec_version: 스펙 버전
    
    Returns:
        API 응답 데이터
    """
    url = f"{BASE_URL}/api/chat/messages"
    
    payload = {
        "sessionId": session_id,
        "participantId": participant_id,
        "turnId": turn_id,
        "role": "USER",
        "content": content,
        "context": {
            "problemId": problem_id,
            "specVersion": spec_version
        }
    }
    
    print(f"\n📤 채팅 메시지 전송 (Turn {turn_id}):")
    print(f"   Content: {content[:50]}...")
    
    try:
        response = await client.post(url, json=payload, timeout=TIMEOUT)
        response.raise_for_status()
        
        data = response.json()
        ai_message = data.get("aiMessage", {})
        
        print(f"✅ 응답 받음:")
        print(f"   - Turn: {ai_message.get('turn')}")
        print(f"   - Token Count: {ai_message.get('tokenCount')}")
        print(f"   - Total Token: {ai_message.get('totalToken')}")
        print(f"   - Content: {ai_message.get('content', '')[:100]}...")
        
        return data
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP 에러: {e.response.status_code}")
        print(f"   Response: {e.response.text}")
        raise
    except Exception as e:
        print(f"❌ 에러 발생: {str(e)}")
        raise


async def submit_code(
    client: httpx.AsyncClient,
    exam_id: int,
    participant_id: int,
    problem_id: int,
    spec_id: int,
    final_code: str,
    submission_id: int,
    language: str = "python3.11"
) -> Dict[str, Any]:
    """
    코드 제출
    
    Args:
        client: httpx 클라이언트
        exam_id: 시험 ID
        participant_id: 참가자 ID
        problem_id: 문제 ID
        spec_id: 스펙 ID (problem_specs.id)
        final_code: 최종 코드
        submission_id: 제출 ID (백엔드에서 생성)
        language: 언어
    
    Returns:
        API 응답 데이터
    """
    url = f"{BASE_URL}/api/session/submit"
    
    payload = {
        "examId": exam_id,
        "participantId": participant_id,
        "problemId": problem_id,
        "specId": spec_id,
        "finalCode": final_code,
        "language": language,
        "submissionId": submission_id
    }
    
    print(f"\n📤 코드 제출:")
    print(f"   - Exam ID: {exam_id}")
    print(f"   - Participant ID: {participant_id}")
    print(f"   - Problem ID: {problem_id}")
    print(f"   - Spec ID: {spec_id}")
    print(f"   - Submission ID: {submission_id}")
    print(f"   - Language: {language}")
    print(f"   - Code Length: {len(final_code)} chars")
    
    try:
        response = await client.post(url, json=payload, timeout=TIMEOUT)
        response.raise_for_status()
        
        data = response.json()
        
        print(f"✅ 제출 완료:")
        print(f"   - Submission ID: {data.get('submissionId')}")
        print(f"   - Status: {data.get('status')}")
        
        return data
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP 에러: {e.response.status_code}")
        print(f"   Response: {e.response.text}")
        raise
    except Exception as e:
        print(f"❌ 에러 발생: {str(e)}")
        raise


async def check_prompt_evaluations(
    session_id: int
) -> Dict[str, Any]:
    """
    prompt_evaluations 테이블 확인
    
    Args:
        session_id: 세션 ID
    
    Returns:
        평가 결과 데이터
    """
    print(f"\n📊 prompt_evaluations 확인 (Session ID: {session_id}):")
    
    try:
        from app.infrastructure.persistence.session import get_db_context
        from sqlalchemy import text
        
        async with get_db_context() as db:
            # TURN_EVAL 조회
            turn_evals = await db.execute(
                text("""
                    SELECT 
                        id,
                        turn,
                        evaluation_type,
                        details->>'score' as score,
                        details->>'intent' as intent,
                        details->>'analysis' as analysis,
                        created_at
                    FROM ai_vibe_coding_test.prompt_evaluations
                    WHERE session_id = :session_id AND evaluation_type = 'TURN_EVAL'
                    ORDER BY turn
                """),
                {"session_id": session_id}
            )
            turn_eval_rows = turn_evals.fetchall()
            
            print(f"\n✅ TURN_EVAL 평가 결과: {len(turn_eval_rows)}개")
            for row in turn_eval_rows:
                print(f"   - Turn {row.turn}:")
                print(f"     * Score: {row.score}")
                print(f"     * Intent: {row.intent}")
                print(f"     * Analysis: {row.analysis[:100] if row.analysis else 'N/A'}...")
                print(f"     * Created: {row.created_at}")
            
            # HOLISTIC_FLOW 조회
            holistic_evals = await db.execute(
                text("""
                    SELECT 
                        id,
                        evaluation_type,
                        details->>'overall_flow_score' as score,
                        details->>'analysis' as analysis,
                        created_at
                    FROM ai_vibe_coding_test.prompt_evaluations
                    WHERE session_id = :session_id AND evaluation_type = 'HOLISTIC_FLOW'
                    ORDER BY created_at DESC
                    LIMIT 1
                """),
                {"session_id": session_id}
            )
            holistic_row = holistic_evals.fetchone()
            
            if holistic_row:
                print(f"\n✅ HOLISTIC_FLOW 평가 결과:")
                print(f"   - Score: {holistic_row.score}")
                print(f"   - Analysis: {holistic_row.analysis[:200] if holistic_row.analysis else 'N/A'}...")
                print(f"   - Created: {holistic_row.created_at}")
            else:
                print(f"\n⚠️  HOLISTIC_FLOW 평가 결과 없음 (6.a 노드가 실행되지 않았을 수 있음)")
            
            return {
                "turn_evals": [
                    {
                        "turn": row.turn,
                        "score": row.score,
                        "intent": row.intent,
                        "analysis": row.analysis,
                        "created_at": str(row.created_at)
                    }
                    for row in turn_eval_rows
                ],
                "holistic_eval": {
                    "score": holistic_row.score if holistic_row else None,
                    "analysis": holistic_row.analysis if holistic_row else None,
                    "created_at": str(holistic_row.created_at) if holistic_row else None
                } if holistic_row else None
            }
    except Exception as e:
        print(f"❌ DB 확인 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


async def main():
    """메인 테스트 함수"""
    print("=" * 80)
    print("제출 플로우 테스트 (채팅부터 시작)")
    print("=" * 80)
    print()
    
    # 1. 테스트 데이터 로드
    test_ids_file = project_root / "test_tsp_ids.json"
    if not test_ids_file.exists():
        print("❌ test_tsp_ids.json 파일이 없습니다.")
        print("   먼저 다음 명령을 실행하세요:")
        print("   uv run python test_scripts/setup_tsp_test_data.py")
        return
    
    with open(test_ids_file, "r", encoding="utf-8") as f:
        test_ids = json.load(f)
    
    session_id = test_ids.get("session_id")
    exam_id = test_ids.get("exam_id")
    participant_id = test_ids.get("participant_id")
    problem_id = test_ids.get("problem_id", 1)
    spec_id = test_ids.get("spec_id")
    spec_version = test_ids.get("spec_version", 10)
    
    print(f"✅ 테스트 데이터 로드 완료:")
    print(f"   - Session ID: {session_id}")
    print(f"   - Exam ID: {exam_id}")
    print(f"   - Participant ID: {participant_id}")
    print(f"   - Problem ID: {problem_id}")
    print(f"   - Spec ID: {spec_id}")
    print(f"   - Spec Version: {spec_version}")
    print()
    
    # 2. 채팅 메시지 전송 (여러 턴)
    async with httpx.AsyncClient() as client:
        # 서버 연결 확인
        try:
            health_response = await client.get(f"{BASE_URL}/health", timeout=5)
            if health_response.status_code != 200:
                print(f"⚠️  서버가 응답하지 않습니다. 서버를 실행하세요:")
                print(f"   uv run python scripts/run_dev.py")
                return
        except Exception as e:
            print(f"❌ 서버 연결 실패: {str(e)}")
            print(f"   서버를 실행하세요: uv run python scripts/run_dev.py")
            return
        
        print("=" * 80)
        print("1단계: 채팅 메시지 전송")
        print("=" * 80)
        
        # Turn 1
        await send_chat_message(
            client,
            session_id=session_id,
            participant_id=participant_id,
            turn_id=1,
            content="외판원 순회 문제를 풀고 싶어요. 어떻게 시작해야 할까요?",
            problem_id=problem_id,
            spec_version=spec_version
        )
        await asyncio.sleep(1)  # 잠시 대기
        
        # Turn 2
        await send_chat_message(
            client,
            session_id=session_id,
            participant_id=participant_id,
            turn_id=2,
            content="동적 계획법으로 풀어보고 싶어요. 힌트를 주실 수 있나요?",
            problem_id=problem_id,
            spec_version=spec_version
        )
        await asyncio.sleep(1)
        
        # Turn 3
        await send_chat_message(
            client,
            session_id=session_id,
            participant_id=participant_id,
            turn_id=3,
            content="비트마스킹을 사용한 코드를 작성해주세요.",
            problem_id=problem_id,
            spec_version=spec_version
        )
        await asyncio.sleep(1)
        
        print()
        print("=" * 80)
        print("2단계: 코드 제출")
        print("=" * 80)
        
        # 제출할 코드
        final_code = """def tsp_dp(dist):
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
        
        # Submission ID 생성 (임시로 큰 숫자 사용, 실제로는 백엔드에서 생성)
        import time
        submission_id = int(time.time() * 1000) % 1000000  # 임시 ID
        
        submit_result = await submit_code(
            client,
            exam_id=exam_id,
            participant_id=participant_id,
            problem_id=problem_id,
            spec_id=spec_id,
            final_code=final_code,
            submission_id=submission_id,
            language="python3.11"
        )
        
        submission_id = submit_result.get("submissionId")
        
        print()
        print("=" * 80)
        print("3단계: 평가 결과 확인")
        print("=" * 80)
        
        # 평가 결과 저장 대기 (비동기 처리이므로 잠시 대기)
        print("\n⏳ 평가 결과 저장 대기 중... (5초)")
        await asyncio.sleep(5)
        
        # prompt_evaluations 확인
        eval_results = await check_prompt_evaluations(session_id)
        
        print()
        print("=" * 80)
        print("✅ 테스트 완료")
        print("=" * 80)
        print()
        print("📋 요약:")
        print(f"   - 채팅 턴: 3개")
        print(f"   - 제출 ID: {submission_id}")
        print(f"   - TURN_EVAL 평가: {len(eval_results['turn_evals'])}개")
        print(f"   - HOLISTIC_FLOW 평가: {'있음' if eval_results['holistic_eval'] else '없음'}")
        print()
        
        # 결과를 JSON 파일로 저장
        result_file = project_root / "test_submit_flow_result.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump({
                "session_id": session_id,
                "submission_id": submission_id,
                "evaluations": eval_results
            }, f, indent=2, ensure_ascii=False)
        
        print(f"💾 결과가 {result_file}에 저장되었습니다.")


if __name__ == "__main__":
    asyncio.run(main())

