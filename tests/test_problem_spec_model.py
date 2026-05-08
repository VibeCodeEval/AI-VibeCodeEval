"""
problem_specs 테이블 DDL(scripts/init-db.sql)과 SQLAlchemy 모델 컬럼명 정합성.

실제 DB 오류: asyncpg UndefinedColumnError column problem_specs.id does not exist
→ PK 컬럼은 spec_id 여야 함.
"""

from app.infrastructure.persistence.models.exams import ExamParticipant
from app.infrastructure.persistence.models.problems import Problem, ProblemSpec
from app.infrastructure.persistence.models.sessions import PromptSession
from app.infrastructure.persistence.models.submissions import Submission


def test_problem_spec_primary_key_is_spec_id_column():
    cols = ProblemSpec.__table__.c
    assert "spec_id" in cols
    assert cols.spec_id.primary_key
    assert "id" not in cols


def test_foreign_keys_reference_problem_specs_spec_id():
    """problem_specs를 가리키는 FK는 spec_id 컬럼을 참조해야 한다."""
    fk_targets = []
    for table in (
        Problem.__table__,
        ExamParticipant.__table__,
        PromptSession.__table__,
        Submission.__table__,
    ):
        for fk in table.foreign_keys:
            if fk.column.table.name == "problem_specs":
                fk_targets.append(fk.column.name)
    assert fk_targets, "expected FKs pointing to problem_specs"
    assert all(t == "spec_id" for t in fk_targets), fk_targets
