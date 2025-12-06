"""
Entity 기반으로 스키마 SQL 생성
로컬에서 Entity를 기반으로 SQL 파일을 생성하여 Docker PostgreSQL로 복원
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.schema import CreateSchema, CreateTable
from app.infrastructure.persistence.session import Base, engine
from app.core.config import settings

# 모든 모델 import (테이블 생성에 필요)
from app.infrastructure.persistence.models import (
    sessions,
    problems,
    submissions,
    exams,
    participants,
)


def export_schema_sql():
    """Entity 기반으로 스키마 SQL 생성"""
    
    print("=" * 80)
    print("Entity 기반 스키마 SQL 생성")
    print("=" * 80)
    print()
    
    # 스키마 생성 SQL
    schema_name = "ai_vibe_coding_test"
    schema_sql = f"CREATE SCHEMA IF NOT EXISTS {schema_name};\n\n"
    
    # 테이블 생성 SQL
    tables_sql = []
    
    # Base.metadata에서 모든 테이블 가져오기
    for table_name, table in Base.metadata.tables.items():
        # 스키마가 포함된 테이블만 처리
        if schema_name in table_name or table.schema == schema_name:
            create_table_sql = str(CreateTable(table).compile(engine.sync_engine))
            tables_sql.append(create_table_sql)
            print(f"✅ 테이블 추가: {table_name}")
    
    # SQL 파일로 저장
    output_file = "schema_from_entities.sql"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("-- Entity 기반 스키마 생성 SQL\n")
        f.write(f"-- 데이터베이스: {settings.POSTGRES_DB}\n")
        f.write(f"-- 스키마: {schema_name}\n")
        f.write("-- 생성 시간: " + str(Path(__file__).stat().st_mtime) + "\n")
        f.write("\n")
        f.write(schema_sql)
        f.write("\n".join(tables_sql))
    
    print()
    print(f"✅ SQL 파일 생성 완료: {output_file}")
    print()
    print("사용 방법:")
    print(f"  psql -h localhost -p {settings.POSTGRES_PORT} -U {settings.POSTGRES_USER} -d {settings.POSTGRES_DB} < {output_file}")
    print()
    print("또는 Docker에서:")
    print(f"  docker cp {output_file} ai_vibe_postgres:/tmp/")
    print(f"  docker exec -i ai_vibe_postgres psql -U postgres -d {settings.POSTGRES_DB} < /tmp/{output_file}")
    print()
    print("=" * 80)


if __name__ == "__main__":
    export_schema_sql()


