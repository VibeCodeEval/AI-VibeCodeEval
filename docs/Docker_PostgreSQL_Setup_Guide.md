# Docker PostgreSQL 설정 가이드

## 1. Docker Compose로 PostgreSQL 실행

### 기본 실행

```bash
# PostgreSQL과 Redis만 실행
docker-compose up -d postgres redis

# 또는 전체 서비스 실행
docker-compose up -d
```

### 서비스 확인

```bash
# 컨테이너 상태 확인
docker-compose ps

# PostgreSQL 로그 확인
docker-compose logs postgres

# Redis 로그 확인
docker-compose logs redis
```

---

## 2. PostgreSQL 접속 및 스키마 확인

### Docker 컨테이너 내부 접속

```bash
# PostgreSQL 컨테이너 접속
docker exec -it ai_vibe_postgres psql -U postgres -d ai_vibe_coding_test

# 또는 직접 SQL 실행
docker exec -it ai_vibe_postgres psql -U postgres -d ai_vibe_coding_test -c "SELECT version();"
```

### 로컬에서 접속 (포트 포워딩)

```bash
# psql이 설치되어 있다면
psql -h localhost -p 5432 -U postgres -d ai_vibe_coding_test

# 비밀번호: postgres
```

### 스키마 확인

```sql
-- 현재 스키마 목록
\dn

-- ai_vibe_coding_test 스키마의 테이블 목록
\dt ai_vibe_coding_test.*

-- 특정 테이블 구조 확인
\d ai_vibe_coding_test.prompt_sessions
\d ai_vibe_coding_test.submissions
```

---

## 3. 문서에 맞춰 Entity 생성

### 3.1 Enum 타입 확인/생성

먼저 문서의 Enum 타입이 DB에 존재하는지 확인:

```sql
-- Enum 타입 확인
SELECT typname FROM pg_type WHERE typname LIKE '%_enum';

-- Enum 값 확인
SELECT enumlabel FROM pg_enum 
WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'difficulty_enum')
ORDER BY enumsortorder;
```

**문서의 Enum 목록**:
- `difficulty_enum`: EASY | MEDIUM | HARD
- `problem_status_enum`: DRAFT | REVIEW | PUBLISHED | ARCHIVED
- `exam_state_enum`: WAITING | RUNNING | ENDED
- `prompt_role_enum`: USER | AI
- `submission_status_enum`: QUEUED | RUNNING | DONE | FAILED
- `run_grp_enum`: SAMPLE | PUBLIC | PRIVATE
- `verdict_enum`: AC | WA | TLE | MLE | RE

### 3.2 Entity 생성 순서

**1단계: Enum 타입 정의**
- `app/infrastructure/persistence/models/enums.py` 업데이트

**2단계: 기본 테이블 Entity 생성**
- `admins`, `admin_numbers`
- `participants`
- `problems`, `problem_specs`
- `problem_sets`, `problem_set_items`
- `exams`, `entry_codes`, `exam_participants`

**3단계: 대화/제출 Entity 생성**
- `prompt_sessions`, `prompt_messages` (이미 존재)
- `submissions`, `submission_runs`, `scores` (이미 존재)

**4단계: 통계 Entity 생성**
- `exam_statistics` (새로 추가)

**5단계: 감사 로그 Entity 생성**
- `admin_audit_logs`

---

## 4. Entity 생성 예시

### 예시 1: Admin Entity

```python
# app/infrastructure/persistence/models/admins.py
from sqlalchemy import BigInteger, Boolean, String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.infrastructure.persistence.session import Base

class Admin(Base):
    """관리자 테이블"""
    __tablename__ = "admins"
    __table_args__ = {"schema": "ai_vibe_coding_test"}
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    admin_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="ADMIN")  # ADMIN | MASTER
    is_2fa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### 예시 2: ExamStatistics Entity (새로 추가)

```python
# app/infrastructure/persistence/models/exam_statistics.py
from sqlalchemy import BigInteger, Integer, Numeric, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.infrastructure.persistence.session import Base

class ExamStatistics(Base):
    """시험 통계 테이블 (새로 추가)"""
    __tablename__ = "exam_statistics"
    __table_args__ = (
        UniqueConstraint("exam_id", "bucket_start", "bucket_sec", name="uq_exam_statistics"),
        {"schema": "ai_vibe_coding_test"}
    )
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exam_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("exams.id"), nullable=False)
    
    # 버킷 키
    bucket_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    bucket_sec: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # 운영 메트릭
    active_examinees: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ws_connections: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    judge_queue_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_wait_sec: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    avg_run_time_ms: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    errors_rate_1m: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    
    # 제출/성능/정답 요약
    submissions_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    submissions_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pass_rate_weighted: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    
    # 점수 평균
    avg_prompt_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    avg_perf_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    avg_correctness_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    avg_total_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    
    # 토큰 사용
    token_used_total: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    token_used_avg: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
```

---

## 5. 저장 테스트 진행 방법

### 5.1 테스트 스크립트 작성

```python
# test_scripts/test_postgres_save.py
import asyncio
from app.infrastructure.persistence.session import get_db_context
from app.infrastructure.persistence.models.sessions import PromptSession, PromptMessage
from app.infrastructure.persistence.models.enums import PromptRoleEnum
from datetime import datetime

async def test_save_prompt_session():
    """프롬프트 세션 저장 테스트"""
    async with get_db_context() as session:
        # 1. PromptSession 생성
        prompt_session = PromptSession(
            exam_id=1,
            participant_id=100,
            spec_id=10,
            started_at=datetime.utcnow(),
            total_tokens=0
        )
        session.add(prompt_session)
        await session.flush()  # ID 생성
        
        # 2. PromptMessage 생성
        message = PromptMessage(
            session_id=prompt_session.id,
            turn=1,
            role=PromptRoleEnum.USER,
            content="테스트 메시지",
            token_count=10
        )
        session.add(message)
        
        # 3. 커밋
        await session.commit()
        
        print(f"✅ 세션 저장 완료: session_id={prompt_session.id}")
        return prompt_session.id

if __name__ == "__main__":
    asyncio.run(test_save_prompt_session())
```

### 5.2 실행

```bash
# Docker에서 PostgreSQL 실행 중인지 확인
docker-compose ps

# 테스트 실행
uv run python test_scripts/test_postgres_save.py
```

### 5.3 결과 확인

```bash
# PostgreSQL에서 확인
docker exec -it ai_vibe_postgres psql -U postgres -d ai_vibe_coding_test -c "SELECT * FROM ai_vibe_coding_test.prompt_sessions ORDER BY id DESC LIMIT 5;"
```

---

## 6. 주의사항

### ⚠️ 스키마 이름

문서에 따르면 스키마는 `ai_vibe_coding_test`입니다.

```python
__table_args__ = {"schema": "ai_vibe_coding_test"}
```

### ⚠️ Spring Boot와 테이블 공유

- Spring Boot가 테이블을 생성/관리할 수 있음
- Python에서는 **읽기 위주** 또는 **데이터 삽입만** 수행
- 테이블 구조 변경은 Spring Boot에서 관리

### ⚠️ Enum 타입

- DB에 Enum 타입이 이미 존재하는지 확인 필요
- SQLAlchemy Enum은 DB Enum과 매핑되어야 함

```python
# DB Enum 사용
Enum(PromptRoleEnum, name="ai_vibe_coding_test.prompt_role_enum")

# 또는 문자열로 저장
role: Mapped[str] = mapped_column(String(20))
```

---

## 7. 다음 단계 체크리스트

- [ ] 문서의 모든 Enum 타입 확인/생성
- [ ] 모든 Entity 모델 생성
- [ ] Repository 패턴 구현
- [ ] 저장 테스트 스크립트 작성
- [ ] Docker에서 테스트 실행
- [ ] 실제 저장 로직 통합


