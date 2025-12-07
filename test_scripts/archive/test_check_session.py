"""
세션 존재 확인 스크립트
"""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select, and_
from app.infrastructure.persistence.session import get_db_context
from app.infrastructure.persistence.models.sessions import PromptSession
from app.infrastructure.persistence.models.exams import ExamParticipant


async def check_session():
    """세션 존재 확인"""
    print("=" * 80)
    print("세션 존재 확인")
    print("=" * 80)
    
    async with get_db_context() as db:
        # exam_participant 조회
        exam_participant_query = select(ExamParticipant).where(ExamParticipant.id == 1000)
        exam_participant_result = await db.execute(exam_participant_query)
        exam_participant = exam_participant_result.scalar_one_or_none()
        
        if not exam_participant:
            print("❌ ExamParticipant (ID: 1000)를 찾을 수 없습니다.")
            return
        
        print(f"\n✅ ExamParticipant 발견:")
        print(f"   - id: {exam_participant.id}")
        print(f"   - exam_id: {exam_participant.exam_id}")
        print(f"   - participant_id: {exam_participant.participant_id}")
        print(f"   - spec_id: {exam_participant.spec_id}")
        
        exam_id = exam_participant.exam_id
        participant_id = exam_participant.participant_id
        
        # 세션 조회
        session_query = select(PromptSession).where(
            and_(
                PromptSession.exam_id == exam_id,
                PromptSession.participant_id == participant_id,
                PromptSession.ended_at.is_(None)  # 종료되지 않은 세션
            )
        )
        session_result = await db.execute(session_query)
        session = session_result.scalar_one_or_none()
        
        if not session:
            print(f"\n❌ 세션을 찾을 수 없습니다.")
            print(f"   검색 조건:")
            print(f"   - exam_id: {exam_id}")
            print(f"   - participant_id: {participant_id}")
            print(f"   - ended_at IS NULL")
            
            # 모든 세션 조회 (종료된 것 포함)
            all_sessions_query = select(PromptSession).where(
                and_(
                    PromptSession.exam_id == exam_id,
                    PromptSession.participant_id == participant_id
                )
            )
            all_sessions_result = await db.execute(all_sessions_query)
            all_sessions = all_sessions_result.scalars().all()
            
            if all_sessions:
                print(f"\n   발견된 세션 (종료된 것 포함): {len(all_sessions)}개")
                for s in all_sessions:
                    print(f"   - Session ID: {s.id}, ended_at: {s.ended_at}, spec_id: {s.spec_id}")
            else:
                print(f"\n   해당 exam_id, participant_id로 세션이 전혀 없습니다.")
        else:
            print(f"\n✅ 세션 발견:")
            print(f"   - id: {session.id}")
            print(f"   - exam_id: {session.exam_id}")
            print(f"   - participant_id: {session.participant_id}")
            print(f"   - spec_id: {session.spec_id}")
            print(f"   - started_at: {session.started_at}")
            print(f"   - ended_at: {session.ended_at}")


if __name__ == "__main__":
    asyncio.run(check_session())

