"""
prompt_evaluations 테이블 상세 조회 스크립트

사용법:
    # 특정 세션의 모든 평가 조회
    uv run python test_scripts/check_prompt_evaluations.py <session_id>
    
    # 특정 턴 평가만 조회
    uv run python test_scripts/check_prompt_evaluations.py <session_id> --turn <turn_number>
    
    # 최근 평가 조회 (기본 10개)
    uv run python test_scripts/check_prompt_evaluations.py --recent [개수]
"""
import asyncio
import sys
import json
from pathlib import Path
from typing import Optional

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from app.infrastructure.persistence.session import get_db_context, init_db


def print_json_pretty(data, indent=2):
    """JSON 데이터를 예쁘게 출력"""
    if isinstance(data, dict):
        print(json.dumps(data, indent=indent, ensure_ascii=False))
    else:
        print(data)


async def check_session_evaluations(session_id: int, turn: Optional[int] = None):
    """특정 세션의 평가 결과 상세 조회"""
    await init_db()
    
    async with get_db_context() as db:
        print("=" * 100)
        print(f"📊 prompt_evaluations 상세 조회 (Session ID: {session_id})")
        if turn is not None:
            print(f"   Turn: {turn}")
        print("=" * 100)
        
        # 세션 정보 확인
        session_result = await db.execute(
            text("""
                SELECT id, exam_id, participant_id, spec_id, started_at, ended_at, total_tokens
                FROM ai_vibe_coding_test.prompt_sessions
                WHERE id = :session_id
            """),
            {"session_id": session_id}
        )
        session = session_result.fetchone()
        
        if not session:
            print(f"❌ Session {session_id}을 찾을 수 없습니다.")
            return
        
        print(f"\n[세션 정보]")
        print(f"  - ID: {session[0]}")
        print(f"  - Exam ID: {session[1]}")
        print(f"  - Participant ID: {session[2]}")
        print(f"  - Spec ID: {session[3]}")
        print(f"  - Started: {session[4]}")
        print(f"  - Ended: {session[5]}")
        print(f"  - Total Tokens: {session[6]}")
        
        # Turn Evaluations 조회
        print(f"\n{'='*100}")
        print("[1] Turn Evaluations (TURN_EVAL)")
        print("="*100)
        
        if turn is not None:
            query = text("""
                SELECT 
                    id,
                    turn,
                    evaluation_type,
                    details,
                    created_at
                FROM ai_vibe_coding_test.prompt_evaluations
                WHERE session_id = :session_id 
                  AND evaluation_type = 'TURN_EVAL'
                  AND turn = :turn
                ORDER BY turn
            """)
            params = {"session_id": session_id, "turn": turn}
        else:
            query = text("""
                SELECT 
                    id,
                    turn,
                    evaluation_type,
                    details,
                    created_at
                FROM ai_vibe_coding_test.prompt_evaluations
                WHERE session_id = :session_id 
                  AND evaluation_type = 'TURN_EVAL'
                ORDER BY turn
            """)
            params = {"session_id": session_id}
        
        turn_result = await db.execute(query, params)
        turn_evals = turn_result.fetchall()
        
        if turn_evals:
            print(f"✅ {len(turn_evals)}개 Turn Evaluation 발견:\n")
            for idx, eval_row in enumerate(turn_evals, 1):
                eval_id, eval_turn, eval_type, details, created_at = eval_row
                
                print(f"\n{'─'*100}")
                print(f"[Turn {eval_turn}] (ID: {eval_id}, Created: {created_at})")
                print(f"{'─'*100}")
                
                # details JSONB 파싱
                if isinstance(details, dict):
                    # 기본 정보
                    print(f"\n[기본 정보]")
                    print(f"  - Score: {details.get('score', 'N/A')}")
                    print(f"  - Intent: {details.get('intent', 'N/A')}")
                    print(f"  - Intent Types: {details.get('intent_types', 'N/A')}")
                    print(f"  - Intent Confidence: {details.get('intent_confidence', 'N/A')}")
                    
                    # Weights 정보
                    if 'weights' in details:
                        print(f"\n[가중치 (Weights)]")
                        weights = details['weights']
                        if isinstance(weights, dict):
                            for key, value in weights.items():
                                print(f"  - {key}: {value}")
                        else:
                            print(f"  {weights}")
                    
                    # Rubrics 정보
                    if 'rubrics' in details:
                        print(f"\n[루브릭별 평가]")
                        rubrics = details['rubrics']
                        if isinstance(rubrics, list):
                            for rubric in rubrics:
                                print(f"\n  [{rubric.get('criterion', rubric.get('name', 'Unknown'))}]")
                                print(f"    - Score: {rubric.get('score', 'N/A')}")
                                if 'weight' in rubric:
                                    print(f"    - Weight: {rubric.get('weight', 'N/A')}")
                                if 'reasoning' in rubric:
                                    reasoning = rubric['reasoning']
                                    if len(str(reasoning)) > 200:
                                        print(f"    - Reasoning: {str(reasoning)[:200]}...")
                                    else:
                                        print(f"    - Reasoning: {reasoning}")
                        else:
                            print(f"  {rubrics}")
                    
                    # Analysis 정보
                    if 'analysis' in details:
                        print(f"\n[종합 분석]")
                        analysis = details['analysis']
                        if len(str(analysis)) > 500:
                            print(f"  {str(analysis)[:500]}...")
                        else:
                            print(f"  {analysis}")
                    
                    # 전체 details 출력 (선택적)
                    print(f"\n[전체 Details (JSON)]")
                    print_json_pretty(details, indent=2)
                else:
                    print(f"\n[Details (Raw)]")
                    print(details)
        else:
            print("❌ Turn Evaluations 없음")
        
        # Holistic Flow Evaluation 조회
        print(f"\n{'='*100}")
        print("[2] Holistic Flow Evaluation (HOLISTIC_FLOW)")
        print("="*100)
        
        holistic_result = await db.execute(
            text("""
                SELECT 
                    id,
                    turn,
                    evaluation_type,
                    details,
                    created_at
                FROM ai_vibe_coding_test.prompt_evaluations
                WHERE session_id = :session_id 
                  AND evaluation_type = 'HOLISTIC_FLOW'
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {"session_id": session_id}
        )
        holistic_eval = holistic_result.fetchone()
        
        if holistic_eval:
            eval_id, eval_turn, eval_type, details, created_at = holistic_eval
            
            print(f"\n✅ Holistic Flow Evaluation 발견:")
            print(f"  - ID: {eval_id}")
            print(f"  - Created: {created_at}")
            
            if isinstance(details, dict):
                print(f"\n[기본 정보]")
                print(f"  - Score: {details.get('score', 'N/A')}")
                print(f"  - Analysis: {details.get('analysis', 'N/A')[:200]}..." if details.get('analysis') else "  - Analysis: N/A")
                
                print(f"\n[전체 Details (JSON)]")
                print_json_pretty(details, indent=2)
            else:
                print(f"\n[Details (Raw)]")
                print(details)
        else:
            print("❌ Holistic Flow Evaluation 없음")
        
        print(f"\n{'='*100}")


async def check_recent_evaluations(limit: int = 10):
    """최근 평가 결과 조회"""
    await init_db()
    
    async with get_db_context() as db:
        print("=" * 100)
        print(f"📊 최근 평가 결과 조회 (최근 {limit}개)")
        print("=" * 100)
        
        result = await db.execute(
            text("""
                SELECT 
                    id,
                    session_id,
                    turn,
                    evaluation_type,
                    details->>'score' as score,
                    details->>'intent' as intent,
                    created_at
                FROM ai_vibe_coding_test.prompt_evaluations
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {"limit": limit}
        )
        evals = result.fetchall()
        
        if evals:
            print(f"\n✅ {len(evals)}개 평가 결과:\n")
            for idx, eval_row in enumerate(evals, 1):
                eval_id, session_id, turn, eval_type, score, intent, created_at = eval_row
                print(f"[{idx}] ID: {eval_id}, Session: {session_id}, Turn: {turn}, Type: {eval_type}")
                print(f"     Score: {score}, Intent: {intent}, Created: {created_at}")
        else:
            print("❌ 평가 결과 없음")
        
        print(f"\n{'='*100}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    if "--recent" in sys.argv:
        # 최근 평가 조회
        limit = 10
        if len(sys.argv) > 2:
            try:
                limit = int(sys.argv[sys.argv.index("--recent") + 1])
            except (ValueError, IndexError):
                pass
        asyncio.run(check_recent_evaluations(limit))
    else:
        # 세션별 조회
        try:
            session_id = int(sys.argv[1])
            turn = None
            if "--turn" in sys.argv:
                turn_idx = sys.argv.index("--turn")
                if turn_idx + 1 < len(sys.argv):
                    turn = int(sys.argv[turn_idx + 1])
            asyncio.run(check_session_evaluations(session_id, turn))
        except ValueError:
            print(f"❌ 잘못된 session_id: {sys.argv[1]}")
            print(__doc__)
            sys.exit(1)

