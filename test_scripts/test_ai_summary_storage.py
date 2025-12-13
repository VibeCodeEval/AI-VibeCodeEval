"""
ai_summary 저장 및 사용 테스트 스크립트

테스트 내용:
1. 4번 Node에서 ai_summary가 prompt_evaluations.details에 저장되는지 확인
2. 6번 Node에서 ai_summary를 조회하여 사용하는지 확인

사용법:
    python test_scripts/test_ai_summary_storage.py [session_id] [turn]
"""
import asyncio
import sys
import os
from typing import Dict, Any, Optional

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.infrastructure.persistence.session import get_db_context
from app.infrastructure.persistence.models.sessions import PromptEvaluation
from app.infrastructure.persistence.models.enums import EvaluationTypeEnum
from sqlalchemy import select, text


async def check_ai_summary_in_db(session_id: int, turn: int) -> Optional[str]:
    """DB에서 ai_summary 확인"""
    try:
        async with get_db_context() as db:
            query = select(PromptEvaluation).where(
                PromptEvaluation.session_id == session_id,
                PromptEvaluation.turn == turn,
                text("prompt_evaluations.evaluation_type::text = :eval_type")
            )
            result = await db.execute(query.params(eval_type=EvaluationTypeEnum.TURN_EVAL.value))
            evaluation = result.scalar_one_or_none()
            
            if evaluation and evaluation.details:
                ai_summary = evaluation.details.get("ai_summary", "")
                return ai_summary
            return None
    except Exception as e:
        print(f"❌ DB 조회 오류: {str(e)}")
        return None


async def check_holistic_evaluation(session_id: int) -> Dict[str, Any]:
    """6번 Node 평가 결과 확인 (structured_logs에 ai_summary 포함 여부)"""
    try:
        async with get_db_context() as db:
            query = select(PromptEvaluation).where(
                PromptEvaluation.session_id == session_id,
                PromptEvaluation.turn.is_(None),  # holistic 평가는 turn이 NULL
                text("prompt_evaluations.evaluation_type::text = :eval_type")
            )
            result = await db.execute(query.params(eval_type=EvaluationTypeEnum.HOLISTIC_FLOW.value))
            evaluation = result.scalar_one_or_none()
            
            if evaluation and evaluation.details:
                structured_logs = evaluation.details.get("structured_logs", [])
                return {
                    "exists": True,
                    "structured_logs": structured_logs,
                    "has_ai_summary": any(
                        log.get("ai_summary") for log in structured_logs
                    )
                }
            return {"exists": False, "structured_logs": [], "has_ai_summary": False}
    except Exception as e:
        print(f"❌ Holistic 평가 조회 오류: {str(e)}")
        return {"exists": False, "error": str(e)}


async def main():
    """메인 테스트 함수"""
    print("=" * 80)
    print("ai_summary 저장 및 사용 테스트")
    print("=" * 80)
    print()
    
    # 명령줄 인자 처리
    if len(sys.argv) >= 3:
        session_id = int(sys.argv[1])
        turn = int(sys.argv[2])
    else:
        # 대화형 입력
        print("테스트할 세션 정보를 입력하세요:")
        session_id_input = input("  session_id (PostgreSQL id): ").strip()
        turn_input = input("  turn 번호: ").strip()
        
        if not session_id_input or not turn_input:
            print("❌ session_id와 turn을 입력해주세요.")
            return
        
        session_id = int(session_id_input)
        turn = int(turn_input)
    
    print(f"\n[테스트 대상]")
    print(f"  session_id: {session_id}")
    print(f"  turn: {turn}")
    print()
    
    # 1. 4번 Node 평가 결과에서 ai_summary 확인
    print("[1단계] 4번 Node 평가 결과에서 ai_summary 확인")
    print("-" * 80)
    
    ai_summary = await check_ai_summary_in_db(session_id, turn)
    
    if ai_summary:
        print(f"✅ ai_summary 저장됨")
        print(f"   길이: {len(ai_summary)} 문자")
        print(f"   내용 (처음 200자): {ai_summary[:200]}...")
    else:
        print(f"❌ ai_summary가 저장되지 않았습니다.")
        print(f"   - 해당 턴의 평가가 실행되었는지 확인하세요.")
        print(f"   - 또는 4번 Node에서 ai_summary 저장 로직을 확인하세요.")
    
    print()
    
    # 2. 6번 Node 평가 결과에서 ai_summary 사용 확인
    print("[2단계] 6번 Node 평가 결과에서 ai_summary 사용 확인")
    print("-" * 80)
    
    holistic_result = await check_holistic_evaluation(session_id)
    
    if holistic_result.get("exists"):
        print(f"✅ Holistic 평가 결과 존재")
        structured_logs = holistic_result.get("structured_logs", [])
        print(f"   턴 개수: {len(structured_logs)}")
        
        if holistic_result.get("has_ai_summary"):
            print(f"✅ structured_logs에 ai_summary 포함됨")
            
            # 각 턴의 ai_summary 확인
            for log in structured_logs:
                turn_num = log.get("turn", "?")
                ai_summary = log.get("ai_summary", "")
                if ai_summary:
                    print(f"   - 턴 {turn_num}: ai_summary 있음 ({len(ai_summary)} 문자)")
                else:
                    print(f"   - 턴 {turn_num}: ai_summary 없음")
        else:
            print(f"❌ structured_logs에 ai_summary가 포함되지 않았습니다.")
            print(f"   - 6번 Node에서 ai_summary 조회 로직을 확인하세요.")
    else:
        print(f"⚠️  Holistic 평가 결과가 없습니다.")
        print(f"   - 제출(submit)이 완료되었는지 확인하세요.")
        if holistic_result.get("error"):
            print(f"   - 오류: {holistic_result.get('error')}")
    
    print()
    print("=" * 80)
    print("테스트 완료")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())





