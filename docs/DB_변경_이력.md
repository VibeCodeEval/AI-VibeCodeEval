# DB 변경 이력

> **최종 통합일**: 2026-03-27 | **원본**: Database_Changes_Summary.md, DB_Schema_Changes.md

---

## 변경 요약

### 개요

LangGraph 평가 시스템의 PostgreSQL 데이터베이스 주요 변경사항을 요약합니다. 평가 저장 구조(`prompt_evaluations`), 세션 종료 정책(`prompt_sessions.ended_at`), 그리고 `evaluation_type` ENUM·제약 조건이 핵심입니다.

### 주요 변경사항

#### 0. 공통 ENUM 타입 추가

**신규 ENUM**: `evaluation_type_enum`

- `TURN_EVAL`: 턴별 평가 (4번 노드)
- `HOLISTIC_FLOW`: 전체 플로우 평가 (6a 노드)

**용도**: 평가 유형의 타입 안정성 보장 및 잘못된 값 입력 방지

#### 1. `prompt_evaluations` 테이블 (신규 생성 및 구조 개선)

**용도**: 평가 결과 저장

- **턴별 평가** (Node 4): 각 대화 턴의 평가 결과 저장
- **전체 평가** (Node 6a): Holistic Flow 평가 결과 저장

**주요 필드**:

- `session_id`: 세션 ID (Foreign Key → `prompt_sessions.id`)
- `turn`: 평가 대상 턴 (NULL이면 세션 전체 평가)
- `evaluation_type`: 평가 유형 (ENUM: `TURN_EVAL`, `HOLISTIC_FLOW`)
- `details`: 모든 평가 데이터 저장 (JSONB, NOT NULL)
  - `score`: 평가 점수 (0–100)
  - `analysis`: 평가 분석 텍스트
  - `intent`, `intent_types`, `rubrics`, `evaluations` 등 상세 정보

**평가 유형별 저장**:

- `TURN_EVAL`: 턴별 평가 (turn 필수, NOT NULL)
- `HOLISTIC_FLOW`: 전체 대화 흐름 평가 (turn NULL)

**제거된 컬럼** (스키마 단순화):

- `node_name`: 제거 (`details`에 포함 가능)
- `score`: 제거 (`details`에 포함)
- `analysis`: 제거 (`details`에 포함)

**안전장치** (DDL·이전 정의와의 차이는 아래 [상세 스키마 변경 이력](#상세-스키마-변경-이력-init-dbsql-대비) 참고):

- **Check Constraint**: 평가 유형에 따른 turn NULL 규칙 (`TURN_EVAL` → turn NOT NULL, `HOLISTIC_FLOW` → turn NULL). 현재 `scripts/init-db.sql`에서는 `evaluation_type::text` 캐스팅을 사용합니다.
- **Unique Index**: 중복 평가 방지 — 턴 평가 `(session_id, turn, evaluation_type)` WHERE `TURN_EVAL`, 전체 평가 `(session_id)` WHERE `HOLISTIC_FLOW`.
- **Foreign Key**: `session_id` → `prompt_sessions.id` (ON DELETE CASCADE); turn이 NULL이 아닐 때 `(session_id, turn)` → `prompt_messages(session_id, turn)`.

#### 2. `prompt_sessions` 테이블 (사용 방식 변경)

**변경 내용**: 세션 종료 처리 추가

| 구분 | 내용 |
|------|------|
| **기존** | `ended_at`이 항상 NULL, 재시도 시 기존 세션 재사용(데이터 혼선) |
| **변경 후** | 제출 완료 시 `ended_at` 설정, 재시도 시 새 세션 생성(데이터 분리) |

**용도**: 각 시도가 독립적인 세션으로 관리되고, 이전 시도와 새 시도의 데이터 혼선을 방지합니다.

### 데이터 흐름

```
1. 세션 생성 (첫 메시지)
   └─ prompt_sessions INSERT (ended_at: NULL)

2. 대화 진행 (매 메시지)
   └─ prompt_messages INSERT

3. 평가 진행 (제출 시)
   └─ prompt_evaluations INSERT
      ├─ TURN_EVAL (턴별 평가) - 모든 턴 평가
      └─ HOLISTIC_FLOW (전체 흐름 평가) - 체이닝 전략 평가

4. 제출 완료
   └─ prompt_sessions.ended_at 설정 (세션 종료)
```

### 주요 조회 예시

#### 특정 세션의 모든 평가 조회

```sql
SELECT 
    id,
    session_id,
    turn,
    evaluation_type,
    details->>'score' AS score,
    details->>'analysis' AS analysis,
    created_at
FROM ai_vibe_coding_test.prompt_evaluations 
WHERE session_id = 123 
ORDER BY turn NULLS LAST, created_at;
```

#### 턴별 평가 점수 조회

```sql
SELECT 
    turn,
    details->>'score' AS score,
    details->>'analysis' AS analysis,
    details->'intent_types' AS intent_types
FROM ai_vibe_coding_test.prompt_evaluations 
WHERE session_id = 123 
  AND evaluation_type = 'TURN_EVAL'
ORDER BY turn;
```

#### 전체 플로우 평가 조회

```sql
SELECT 
    details->>'score' AS holistic_flow_score,
    details->>'analysis' AS holistic_flow_analysis
FROM ai_vibe_coding_test.prompt_evaluations 
WHERE session_id = 123 
  AND evaluation_type = 'HOLISTIC_FLOW';
```

#### 세션 종료 여부 확인

```sql
SELECT 
    id,
    started_at,
    ended_at,
    CASE 
        WHEN ended_at IS NULL THEN '진행 중'
        ELSE '종료됨'
    END AS status
FROM ai_vibe_coding_test.prompt_sessions
WHERE exam_id = 1 AND participant_id = 1
ORDER BY started_at DESC;
```

### 주의사항 (운영·애플리케이션)

1. **평가 유형과 turn의 관계**: `TURN_EVAL`은 turn 필수, `HOLISTIC_FLOW`는 turn NULL — Check Constraint로 강제됩니다.
2. **`details` JSONB**: 필수 `score`, `analysis`; 선택적으로 `intent`, `intent_types`, `rubrics`, `evaluations`, `detailed_feedback`, `turn_score` 등. 조회는 `details->>'score'` 형태.
3. **중복 저장 방지**: Unique Index와 `EvaluationStorageService`에서 처리.
4. **세션 종료**: 제출 완료 시에만 `ended_at` 설정; 평가 실패 시에는 미설정(롤백 가능).
5. **ENUM**: `evaluation_type`은 DB·SQLAlchemy에서 `EvaluationTypeEnum`으로 일관되게 사용합니다.

기존 DB에 제약 조건을 맞추는 마이그레이션 단계는 [적용 시 주의사항](#적용-시-주의사항)을 참고하세요.

### 변경 이력 (기능·스키마 진화)

| 날짜 | 변경사항 |
|------|---------|
| 2025-01-15 | `prompt_evaluations` 테이블 생성 |
| 2025-01-15 | Check Constraint 및 Unique Index 추가 |
| 2025-01-15 | 세션 종료 처리 (`ended_at` 설정) |
| 2025-01-XX | `evaluation_type_enum` ENUM 타입 추가 |
| 2025-01-XX | `prompt_evaluations` 테이블 구조 개선 |
| 2025-01-XX | `node_name`, `score`, `analysis` 컬럼 제거 (`details`로 통합) |
| 2025-01-XX | `evaluation_type` VARCHAR → ENUM 변경 |
| 2025-01-XX | `details` JSONB를 NOT NULL로 변경 |

### 관련 문서

- [Quick DB Guide](./Quick_DB_Guide.md) — DB 사용 가이드
- [State Flow and DB Storage](./State_Flow_and_DB_Storage.md) — State 흐름 및 저장 전략
- `scripts/init-db.sql` — 현재 최신 스키마 정의
- `app/infrastructure/persistence/models/sessions.py` — SQLAlchemy 모델 정의

---

## 상세 스키마 변경 이력 (init-db.sql 대비)

### 개요

`scripts/init-db.sql` 기준으로, **초기 사용자 제공 DDL**(ENUM과 문자열 리터럴 직접 비교)과 **현재 `init-db.sql`**(Check Constraint에서 ENUM 텍스트 캐스팅)의 차이를 정리합니다.

**문서화 시점 참고**: 2025-12-08 01:15

**비교 기준**:

- **이전 버전**: 사용자 제공 코드 (ENUM 직접 비교)
- **현재 버전**: `scripts/init-db.sql` (ENUM 텍스트 캐스팅)

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

**변경 내용**

- 추가: `evaluation_type::text` 명시적 텍스트 캐스팅
- 이유: PostgreSQL ENUM과 문자열 리터럴 비교 시 타입 불일치 오류 방지
- 영향: Check Constraint 검증 시 타입 안전성 향상

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

**변경 내용**: 구문 동일. WHERE 절의 ENUM 직접 비교는 PostgreSQL에서 정상 동작합니다.

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

**변경 내용**: 구문 동일.

### init-db.sql 대비 요약 표

| 항목 | 이전 버전 | 현재 버전 | 변경 여부 |
|------|----------|----------|----------|
| `check_valid_turn_logic` CHECK | `evaluation_type = '...'` | `evaluation_type::text = '...'` | 변경 |
| `idx_unique_turn_eval` WHERE | `evaluation_type = 'TURN_EVAL'` | `evaluation_type = 'TURN_EVAL'` | 동일 |
| `idx_unique_holistic_flow_eval` WHERE | `evaluation_type = 'HOLISTIC_FLOW'` | `evaluation_type = 'HOLISTIC_FLOW'` | 동일 |

### 변경 이유 및 배경

#### 문제 상황

이전 버전에서 다음과 같은 오류가 보고되었습니다:

```
asyncpg.exceptions.CheckViolationError: 
new row for relation "prompt_evaluations" violates check constraint "check_valid_turn_logic"
```

#### 원인 분석

1. **타입 불일치**: PostgreSQL ENUM(`evaluation_type_enum`)과 문자열 리터럴(`'TURN_EVAL'`, `'HOLISTIC_FLOW'`)을 직접 비교할 때 타입 불일치가 발생할 수 있음
2. **SQLAlchemy**: Python에서 문자열로 전달된 값이 ENUM 컬럼과 비교될 때 암시적 캐스팅이 실패할 수 있음

#### 해결 방법

- **Check Constraint**: `evaluation_type::text` 명시적 캐스팅
- **인덱스 WHERE 절**: ENUM 직접 비교 유지(PostgreSQL에서 정상 작동)

### 적용 시 주의사항

#### 기존 DB에 적용하는 경우

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

2. **인덱스**: WHERE 절 ENUM 비교는 그대로 두어도 됩니다.

#### 새 DB 생성 시

- `scripts/init-db.sql`을 실행하면 위 최신 정의가 적용됩니다.

### 관련 코드 (SQLAlchemy)

`app/infrastructure/persistence/models/sessions.py`:

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

- `create_type=False`: DB에 이미 존재하는 ENUM 사용
- `native_enum=True`: PostgreSQL 네이티브 ENUM 사용

### 검증 방법

#### Check Constraint

```sql
-- TURN_EVAL: turn이 NOT NULL이어야 함
INSERT INTO ai_vibe_coding_test.prompt_evaluations 
(session_id, turn, evaluation_type, details)
VALUES (1, 1, 'TURN_EVAL', '{"score": 30.0}');
-- 성공

-- TURN_EVAL: turn이 NULL이면 실패해야 함
INSERT INTO ai_vibe_coding_test.prompt_evaluations 
(session_id, turn, evaluation_type, details)
VALUES (1, NULL, 'TURN_EVAL', '{"score": 30.0}');
-- 실패 (check_valid_turn_logic 위반)

-- HOLISTIC_FLOW: turn이 NULL이어야 함
INSERT INTO ai_vibe_coding_test.prompt_evaluations 
(session_id, turn, evaluation_type, details)
VALUES (1, NULL, 'HOLISTIC_FLOW', '{"score": 30.0}');
-- 성공

-- HOLISTIC_FLOW: turn이 NOT NULL이면 실패해야 함
INSERT INTO ai_vibe_coding_test.prompt_evaluations 
(session_id, turn, evaluation_type, details)
VALUES (1, 1, 'HOLISTIC_FLOW', '{"score": 30.0}');
-- 실패 (check_valid_turn_logic 위반)
```

#### Unique Index

```sql
-- 동일한 세션, 턴, 평가 유형 중복 시도
INSERT INTO ai_vibe_coding_test.prompt_evaluations 
(session_id, turn, evaluation_type, details)
VALUES (1, 1, 'TURN_EVAL', '{"score": 30.0}');

INSERT INTO ai_vibe_coding_test.prompt_evaluations 
(session_id, turn, evaluation_type, details)
VALUES (1, 1, 'TURN_EVAL', '{"score": 40.0}');
-- 실패 (idx_unique_turn_eval 위반)
```

### 참고 자료

- [PostgreSQL ENUM 타입](https://www.postgresql.org/docs/current/datatype-enum.html)
- [SQLAlchemy Enum](https://docs.sqlalchemy.org/en/20/core/type_basics.html#sqlalchemy.types.Enum)

---

**문서 메타**: 상세 스키마 절 원본 갱신일 표기는 `2025-01-XX` 수준이었으며, 본 통합본의 상단 블록에 최종 통합일을 명시합니다.
