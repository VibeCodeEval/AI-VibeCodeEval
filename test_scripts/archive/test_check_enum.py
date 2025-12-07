"""
DB에 evaluation_type_enum이 존재하는지 확인
"""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from app.infrastructure.persistence.session import get_db_context


async def check_enum():
    """ENUM 타입 존재 확인"""
    print("=" * 80)
    print("evaluation_type_enum 존재 확인")
    print("=" * 80)
    
    async with get_db_context() as db:
        try:
            # ENUM 타입 조회
            result = await db.execute(text("""
                SELECT typname 
                FROM pg_type 
                WHERE typname = 'evaluation_type_enum'
                AND typnamespace = (
                    SELECT oid 
                    FROM pg_namespace 
                    WHERE nspname = 'ai_vibe_coding_test'
                )
            """))
            enum_exists = result.scalar_one_or_none()
            
            if enum_exists:
                print("✅ evaluation_type_enum이 존재합니다.")
                
                # ENUM 값 확인
                result = await db.execute(text("""
                    SELECT enumlabel 
                    FROM pg_enum 
                    WHERE enumtypid = (
                        SELECT oid 
                        FROM pg_type 
                        WHERE typname = 'evaluation_type_enum'
                        AND typnamespace = (
                            SELECT oid 
                            FROM pg_namespace 
                            WHERE nspname = 'ai_vibe_coding_test'
                        )
                    )
                    ORDER BY enumsortorder
                """))
                enum_values = result.scalars().all()
                print(f"   ENUM 값: {list(enum_values)}")
            else:
                print("❌ evaluation_type_enum이 존재하지 않습니다.")
                print("   init-db.sql을 실행해야 합니다.")
                
        except Exception as e:
            print(f"❌ 오류 발생: {str(e)}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(check_enum())

