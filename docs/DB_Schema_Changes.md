# DB 스키마 변경 사항 문서

## 📋 개요

`scripts/init-db.sql` 파일의 "DB 수정 Commit과 현재 Commit 비교"
2025-12-08 01:15

**비교 기준**:
- **이전 버전**: 사용자 제공 코드 (ENUM 직접 비교)
- **현재 버전**: `scripts/init-db.sql` (ENUM 텍스트 캐스팅)

---

## 🔍 주요 변경 사항

### 1. Check Constraint: `check_valid_turn_logic`

#### 이전 버전 (사용자 제공)
```sql
ALTER TABLE ai_vibe_coding_test.prompt_evaluations
ADD CONSTRAINT check_valid_turn_logic
CHECK (
    (evaluation_type = 'HOLISTIC_FLOW' AND turn IS NULL)
    OR
    (evaluation_type = 'TURN_EVAL' AND turn IS NOT NULL)
);
```

#### 현재 버전 (`scripts/init-db.sql`)
```sql
-- 안전장치 1: Check Constraint (ENUM 값에 맞춰 수정)
-- "Holistic 평가면 turn은 NULL, Turn 평가면 turn은 NOT NULL"
-- ENUM을 텍스트로 명시적 캐스팅하여 타입 불일치 방지
ALTER TABLE ai_vibe_coding_test.prompt_evaluations
ADD CONSTRAINT check_valid_turn_logic
CHECK (
    -- 경우 1: 전체 평가(HOLISTIC_FLOW)면 -> turn은 반드시 NULL
    (evaluation_type::text = 'HOLISTIC_FLOW' AND turn IS NULL)
    OR
    -- 경우 2: 턴 평가(TURN_EVAL)면 -> turn은 반드시 NOT NULL
    (evaluation_type::text = 'TURN_EVAL' AND turn IS NOT NULL)
);
```

#### 변경 내용
- 추가: `evaluation_type::text` 명시적 텍스트 캐스팅
- 이유: PostgreSQL ENUM 타입과 문자열 리터럴 비교 시 타입 불일치 오류 방지
- 영향: Check Constraint 검증 시 타입 안전성 향상

---

### 2. Unique Index: `idx_unique_turn_eval`

#### 이전 버전 (사용자 제공)
```sql
CREATE UNIQUE INDEX idx_unique_turn_eval 
ON ai_vibe_coding_test.prompt_evaluations (session_id, turn, evaluation_type) 
WHERE evaluation_type = 'TURN_EVAL';
```

#### 현재 버전 (`scripts/init-db.sql`)
```sql
-- 안전장치 2-1: 턴 평가용 유니크 인덱스 (ENUM 값 적용)
CREATE UNIQUE INDEX idx_unique_turn_eval 
ON ai_vibe_coding_test.prompt_evaluations (session_id, turn, evaluation_type) 
WHERE evaluation_type = 'TURN_EVAL';
```

#### 변경 내용
- **변경 없음**: 동일한 구문 유지
- **참고**: WHERE 절에서 ENUM 값 직접 비교는 PostgreSQL에서 정상 작동

---

### 3. Unique Index: `idx_unique_holistic_flow_eval`

#### 이전 버전 (사용자 제공)
```sql
CREATE UNIQUE INDEX idx_unique_holistic_flow_eval 
ON ai_vibe_coding_test.prompt_evaluations (session_id) 
WHERE evaluation_type = 'HOLISTIC_FLOW';
```

#### 현재 버전 (`scripts/init-db.sql`)
```sql
-- 안전장치 2-2: 전체 평가용 유니크 인덱스 (ENUM 값 적용)
CREATE UNIQUE INDEX idx_unique_holistic_flow_eval 
ON ai_vibe_coding_test.prompt_evaluations (session_id) 
WHERE evaluation_type = 'HOLISTIC_FLOW';
```

#### 변경 내용
- **변경 없음**: 동일한 구문 유지
- **참고**: WHERE 절에서 ENUM 값 직접 비교는 PostgreSQL에서 정상 작동

---

## 📊 변경 사항 요약

| 항목 | 이전 버전 | 현재 버전 | 변경 여부 |
|------|----------|----------|----------|
| `check_valid_turn_logic` CHECK | `evaluation_type = '...'` | `evaluation_type::text = '...'` | ✅ 변경 |
| `idx_unique_turn_eval` WHERE | `evaluation_type = 'TURN_EVAL'` | `evaluation_type = 'TURN_EVAL'` | ❌ 동일 |
| `idx_unique_holistic_flow_eval` WHERE | `evaluation_type = 'HOLISTIC_FLOW'` | `evaluation_type = 'HOLISTIC_FLOW'` | ❌ 동일 |

---

## 🔧 변경 이유 및 배경

### 문제 상황
이전 버전에서 다음과 같은 오류가 발생했습니다:

```
asyncpg.exceptions.CheckViolationError: 
new row for relation "prompt_evaluations" violates check constraint "check_valid_turn_logic"
```

### 원인 분석
1. **타입 불일치**: PostgreSQL ENUM 타입(`evaluation_type_enum`)과 문자열 리터럴(`'TURN_EVAL'`, `'HOLISTIC_FLOW'`)을 직접 비교할 때 타입 불일치 발생
2. **SQLAlchemy 동작**: Python 코드에서 문자열로 전달된 값이 ENUM 타입 컬럼과 비교될 때 암시적 캐스팅이 실패할 수 있음

### 해결 방법
- **Check Constraint**: `evaluation_type::text` 명시적 캐스팅 추가
- **인덱스 WHERE 절**: ENUM 직접 비교 유지 (PostgreSQL에서 정상 작동)

---

## 🎯 적용 시 주의사항

### 기존 DB에 적용하는 경우

1. **기존 제약 조건 삭제 후 재생성**:
```sql
-- 기존 제약 조건 삭제
ALTER TABLE ai_vibe_coding_test.prompt_evaluations
DROP CONSTRAINT IF EXISTS check_valid_turn_logic;

-- 새 제약 조건 추가 (텍스트 캐스팅 포함)
ALTER TABLE ai_vibe_coding_test.prompt_evaluations
ADD CONSTRAINT check_valid_turn_logic
CHECK (
    (evaluation_type::text = 'HOLISTIC_FLOW' AND turn IS NULL)
    OR
    (evaluation_type::text = 'TURN_EVAL' AND turn IS NOT NULL)
);
```

2. **인덱스는 변경 불필요**: WHERE 절에서 ENUM 직접 비교는 정상 작동

### 새 DB 생성 시
- `scripts/init-db.sql` 파일을 그대로 실행하면 최신 버전이 적용됩니다.

---

## 📝 관련 코드 변경 사항

### SQLAlchemy 모델 (`app/infrastructure/persistence/models/sessions.py`)

현재 모델 설정:
```python
evaluation_type: Mapped[EvaluationTypeEnum] = mapped_column(
    Enum(
        EvaluationTypeEnum,
        name="evaluation_type_enum",
        schema="ai_vibe_coding_test",
        create_type=False,  # 기존 ENUM 타입 사용 (DB에 이미 존재)
        native_enum=True   # PostgreSQL 네이티브 ENUM 사용
    ),
    nullable=False
)
```

**설명**:
- `create_type=False`: DB에 이미 존재하는 ENUM 타입 사용
- `native_enum=True`: PostgreSQL 네이티브 ENUM 타입 사용
- 이 설정으로 SQLAlchemy가 ENUM 타입을 올바르게 처리

---

## ✅ 검증 방법

### 1. Check Constraint 검증
```sql
-- TURN_EVAL: turn이 NOT NULL이어야 함
INSERT INTO ai_vibe_coding_test.prompt_evaluations 
(session_id, turn, evaluation_type, details)
VALUES (1, 1, 'TURN_EVAL', '{"score": 30.0}');
-- ✅ 성공

-- TURN_EVAL: turn이 NULL이면 실패해야 함
INSERT INTO ai_vibe_coding_test.prompt_evaluations 
(session_id, turn, evaluation_type, details)
VALUES (1, NULL, 'TURN_EVAL', '{"score": 30.0}');
-- ❌ 실패 (check_valid_turn_logic 위반)

-- HOLISTIC_FLOW: turn이 NULL이어야 함
INSERT INTO ai_vibe_coding_test.prompt_evaluations 
(session_id, turn, evaluation_type, details)
VALUES (1, NULL, 'HOLISTIC_FLOW', '{"score": 30.0}');
-- ✅ 성공

-- HOLISTIC_FLOW: turn이 NOT NULL이면 실패해야 함
INSERT INTO ai_vibe_coding_test.prompt_evaluations 
(session_id, turn, evaluation_type, details)
VALUES (1, 1, 'HOLISTIC_FLOW', '{"score": 30.0}');
-- ❌ 실패 (check_valid_turn_logic 위반)
```

### 2. Unique Index 검증
```sql
-- 동일한 세션, 턴, 평가 유형 중복 시도
INSERT INTO ai_vibe_coding_test.prompt_evaluations 
(session_id, turn, evaluation_type, details)
VALUES (1, 1, 'TURN_EVAL', '{"score": 30.0}');

INSERT INTO ai_vibe_coding_test.prompt_evaluations 
(session_id, turn, evaluation_type, details)
VALUES (1, 1, 'TURN_EVAL', '{"score": 40.0}');
-- ❌ 실패 (idx_unique_turn_eval 위반)
```

---

## 📚 참고 자료

- PostgreSQL ENUM 타입 문서: https://www.postgresql.org/docs/current/datatype-enum.html
- SQLAlchemy ENUM 문서: https://docs.sqlalchemy.org/en/20/core/type_basics.html#sqlalchemy.types.Enum
- `scripts/init-db.sql`: 현재 최신 스키마 정의
- `app/infrastructure/persistence/models/sessions.py`: SQLAlchemy 모델 정의

---

**최종 업데이트**: 2025-01-XX
**문서 버전**: 1.0


## 📋 개요

`scripts/init-db.sql` 파일의 현재 상태와 이전 버전 간의 차이점을 문서화합니다.

**비교 기준**:
- **이전 버전**: 사용자 제공 코드 (ENUM 직접 비교)
- **현재 버전**: `scripts/init-db.sql` (ENUM 텍스트 캐스팅)

---

## 🔍 주요 변경 사항

### 1. Check Constraint: `check_valid_turn_logic`

#### 이전 버전 (사용자 제공)
```sql
ALTER TABLE ai_vibe_coding_test.prompt_evaluations
ADD CONSTRAINT check_valid_turn_logic
CHECK (
    -- 경우 1: 전체 평가(HOLISTIC_FLOW)면 -> turn은 반드시 NULL
    (evaluation_type = 'HOLISTIC_FLOW' AND turn IS NULL)
    OR
    -- 경우 2: 턴 평가(TURN_EVAL)면 -> turn은 반드시 NOT NULL
    (evaluation_type = 'TURN_EVAL' AND turn IS NOT NULL)
);
```

#### 현재 버전 (`scripts/init-db.sql`)
```sql
-- 안전장치 1: Check Constraint (ENUM 값에 맞춰 수정)
-- "Holistic 평가면 turn은 NULL, Turn 평가면 turn은 NOT NULL"
-- ENUM을 텍스트로 명시적 캐스팅하여 타입 불일치 방지
ALTER TABLE ai_vibe_coding_test.prompt_evaluations
ADD CONSTRAINT check_valid_turn_logic
CHECK (
    -- 경우 1: 전체 평가(HOLISTIC_FLOW)면 -> turn은 반드시 NULL
    (evaluation_type::text = 'HOLISTIC_FLOW' AND turn IS NULL)
    OR
    -- 경우 2: 턴 평가(TURN_EVAL)면 -> turn은 반드시 NOT NULL
    (evaluation_type::text = 'TURN_EVAL' AND turn IS NOT NULL)
);
```

#### 변경 내용
- **추가**: `evaluation_type::text` 명시적 텍스트 캐스팅
- **이유**: PostgreSQL ENUM 타입과 문자열 리터럴 비교 시 타입 불일치 오류 방지
- **영향**: Check Constraint 검증 시 타입 안전성 향상

---

### 2. Unique Index: `idx_unique_turn_eval`

#### 이전 버전 (사용자 제공)
```sql
-- 안전장치 2-1: 턴 평가용 유니크 인덱스 (ENUM 값 적용)
CREATE UNIQUE INDEX idx_unique_turn_eval 
ON ai_vibe_coding_test.prompt_evaluations (session_id, turn, evaluation_type) 
WHERE evaluation_type = 'TURN_EVAL';
```

#### 현재 버전 (`scripts/init-db.sql`)
```sql
-- 안전장치 2-1: 턴 평가용 유니크 인덱스 (ENUM 값 적용)
CREATE UNIQUE INDEX idx_unique_turn_eval 
ON ai_vibe_coding_test.prompt_evaluations (session_id, turn, evaluation_type) 
WHERE evaluation_type = 'TURN_EVAL';
```

#### 변경 내용
- **변경 없음**: 동일한 구문 유지
- **참고**: WHERE 절에서 ENUM 값 직접 비교는 PostgreSQL에서 정상 작동

---

### 3. Unique Index: `idx_unique_holistic_flow_eval`

#### 이전 버전 (사용자 제공)
```sql
-- 안전장치 2-2: 전체 평가용 유니크 인덱스 (ENUM 값 적용)
CREATE UNIQUE INDEX idx_unique_holistic_flow_eval 
ON ai_vibe_coding_test.prompt_evaluations (session_id) 
WHERE evaluation_type = 'HOLISTIC_FLOW';
```

#### 현재 버전 (`scripts/init-db.sql`)
```sql
-- 안전장치 2-2: 전체 평가용 유니크 인덱스 (ENUM 값 적용)
CREATE UNIQUE INDEX idx_unique_holistic_flow_eval 
ON ai_vibe_coding_test.prompt_evaluations (session_id) 
WHERE evaluation_type = 'HOLISTIC_FLOW';
```

#### 변경 내용
- **변경 없음**: 동일한 구문 유지
- **참고**: WHERE 절에서 ENUM 값 직접 비교는 PostgreSQL에서 정상 작동

---

## 📊 변경 사항 요약

| 항목 | 이전 버전 | 현재 버전 | 변경 여부 |
|------|----------|----------|----------|
| `check_valid_turn_logic` CHECK | `evaluation_type = '...'` | `evaluation_type::text = '...'` | ✅ 변경 |
| `idx_unique_turn_eval` WHERE | `evaluation_type = 'TURN_EVAL'` | `evaluation_type = 'TURN_EVAL'` | ❌ 동일 |
| `idx_unique_holistic_flow_eval` WHERE | `evaluation_type = 'HOLISTIC_FLOW'` | `evaluation_type = 'HOLISTIC_FLOW'` | ❌ 동일 |

---

## 🔧 변경 이유 및 배경

### 문제 상황
이전 버전에서 다음과 같은 오류가 발생했습니다:

```
asyncpg.exceptions.CheckViolationError: 
new row for relation "prompt_evaluations" violates check constraint "check_valid_turn_logic"
```

### 원인 분석
1. **타입 불일치**: PostgreSQL ENUM 타입(`evaluation_type_enum`)과 문자열 리터럴(`'TURN_EVAL'`, `'HOLISTIC_FLOW'`)을 직접 비교할 때 타입 불일치 발생
2. **SQLAlchemy 동작**: Python 코드에서 문자열로 전달된 값이 ENUM 타입 컬럼과 비교될 때 암시적 캐스팅이 실패할 수 있음

### 해결 방법
- **Check Constraint**: `evaluation_type::text` 명시적 캐스팅 추가
- **인덱스 WHERE 절**: ENUM 직접 비교 유지 (PostgreSQL에서 정상 작동)

---

## 🎯 적용 시 주의사항

### 기존 DB에 적용하는 경우

1. **기존 제약 조건 삭제 후 재생성**:
```sql
-- 기존 제약 조건 삭제
ALTER TABLE ai_vibe_coding_test.prompt_evaluations
DROP CONSTRAINT IF EXISTS check_valid_turn_logic;

-- 새 제약 조건 추가 (텍스트 캐스팅 포함)
ALTER TABLE ai_vibe_coding_test.prompt_evaluations
ADD CONSTRAINT check_valid_turn_logic
CHECK (
    (evaluation_type::text = 'HOLISTIC_FLOW' AND turn IS NULL)
    OR
    (evaluation_type::text = 'TURN_EVAL' AND turn IS NOT NULL)
);
```

2. **인덱스는 변경 불필요**: WHERE 절에서 ENUM 직접 비교는 정상 작동

### 새 DB 생성 시
- `scripts/init-db.sql` 파일을 그대로 실행하면 최신 버전이 적용됩니다.

---

## 📝 관련 코드 변경 사항

### SQLAlchemy 모델 (`app/infrastructure/persistence/models/sessions.py`)

현재 모델 설정:
```python
evaluation_type: Mapped[EvaluationTypeEnum] = mapped_column(
    Enum(
        EvaluationTypeEnum,
        name="evaluation_type_enum",
        schema="ai_vibe_coding_test",
        create_type=False,  # 기존 ENUM 타입 사용 (DB에 이미 존재)
        native_enum=True   # PostgreSQL 네이티브 ENUM 사용
    ),
    nullable=False
)
```

**설명**:
- `create_type=False`: DB에 이미 존재하는 ENUM 타입 사용
- `native_enum=True`: PostgreSQL 네이티브 ENUM 타입 사용
- 이 설정으로 SQLAlchemy가 ENUM 타입을 올바르게 처리

---

## ✅ 검증 방법

### 1. Check Constraint 검증
```sql
-- TURN_EVAL: turn이 NOT NULL이어야 함
INSERT INTO ai_vibe_coding_test.prompt_evaluations 
(session_id, turn, evaluation_type, details)
VALUES (1, 1, 'TURN_EVAL', '{"score": 30.0}');
-- ✅ 성공

-- TURN_EVAL: turn이 NULL이면 실패해야 함
INSERT INTO ai_vibe_coding_test.prompt_evaluations 
(session_id, turn, evaluation_type, details)
VALUES (1, NULL, 'TURN_EVAL', '{"score": 30.0}');
-- ❌ 실패 (check_valid_turn_logic 위반)

-- HOLISTIC_FLOW: turn이 NULL이어야 함
INSERT INTO ai_vibe_coding_test.prompt_evaluations 
(session_id, turn, evaluation_type, details)
VALUES (1, NULL, 'HOLISTIC_FLOW', '{"score": 30.0}');
-- ✅ 성공

-- HOLISTIC_FLOW: turn이 NOT NULL이면 실패해야 함
INSERT INTO ai_vibe_coding_test.prompt_evaluations 
(session_id, turn, evaluation_type, details)
VALUES (1, 1, 'HOLISTIC_FLOW', '{"score": 30.0}');
-- ❌ 실패 (check_valid_turn_logic 위반)
```

### 2. Unique Index 검증
```sql
-- 동일한 세션, 턴, 평가 유형 중복 시도
INSERT INTO ai_vibe_coding_test.prompt_evaluations 
(session_id, turn, evaluation_type, details)
VALUES (1, 1, 'TURN_EVAL', '{"score": 30.0}');

INSERT INTO ai_vibe_coding_test.prompt_evaluations 
(session_id, turn, evaluation_type, details)
VALUES (1, 1, 'TURN_EVAL', '{"score": 40.0}');
-- ❌ 실패 (idx_unique_turn_eval 위반)
```

---

## 📚 참고 자료

- PostgreSQL ENUM 타입 문서: https://www.postgresql.org/docs/current/datatype-enum.html
- SQLAlchemy ENUM 문서: https://docs.sqlalchemy.org/en/20/core/type_basics.html#sqlalchemy.types.Enum
- `scripts/init-db.sql`: 현재 최신 스키마 정의
- `app/infrastructure/persistence/models/sessions.py`: SQLAlchemy 모델 정의

---

**최종 업데이트**: 2025-01-XX
**문서 버전**: 1.0

