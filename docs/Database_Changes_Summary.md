# 데이터베이스 변경사항 요약

## 📋 개요

LangGraph 평가 시스템의 PostgreSQL 데이터베이스 주요 변경사항을 요약한 문서입니다.

---

## 🗂️ 주요 변경사항

### 0. 공통 ENUM 타입 추가

**신규 ENUM**: `evaluation_type_enum`
- `TURN_EVAL`: 턴별 평가 (4번 노드)
- `HOLISTIC_FLOW`: 전체 플로우 평가 (6a 노드)

**용도**: 평가 유형의 타입 안정성 보장 및 잘못된 값 입력 방지

---

### 1. `prompt_evaluations` 테이블 (신규 생성 및 구조 개선)

**용도**: 평가 결과 저장
- **턴별 평가** (Node 4): 각 대화 턴의 평가 결과 저장
- **전체 평가** (Node 6a): Holistic Flow 평가 결과 저장

**주요 필드**:
- `session_id`: 세션 ID (Foreign Key → `prompt_sessions.id`)
- `turn`: 평가 대상 턴 (NULL이면 세션 전체 평가)
- `evaluation_type`: 평가 유형 (ENUM: `TURN_EVAL`, `HOLISTIC_FLOW`)
- `details`: 모든 평가 데이터 저장 (JSONB, NOT NULL)
  - `score`: 평가 점수 (0-100)
  - `analysis`: 평가 분석 텍스트
  - `intent`, `intent_types`, `rubrics`, `evaluations` 등 상세 정보

**평가 유형별 저장**:
- `TURN_EVAL`: 턴별 평가 (turn 필수, NOT NULL)
- `HOLISTIC_FLOW`: 전체 대화 흐름 평가 (turn NULL)

**제거된 컬럼** (스키마 단순화):
- `node_name`: 제거 (details에 포함 가능)
- `score`: 제거 (details에 포함)
- `analysis`: 제거 (details에 포함)

**안전장치**:
- Check Constraint: 평가 유형에 따른 turn NULL 규칙 강제
  - `TURN_EVAL` → turn NOT NULL
  - `HOLISTIC_FLOW` → turn NULL
- Unique Index: 중복 평가 결과 방지
  - 턴 평가: `(session_id, turn, evaluation_type)` WHERE `evaluation_type = 'TURN_EVAL'`
  - 전체 평가: `(session_id)` WHERE `evaluation_type = 'HOLISTIC_FLOW'`
- Foreign Key: 참조 무결성 보장
  - `session_id` → `prompt_sessions.id` (ON DELETE CASCADE)
  - `(session_id, turn)` → `prompt_messages(session_id, turn)` (turn이 NULL이 아닐 때만)

---

### 2. `prompt_sessions` 테이블 (사용 방식 변경)

**변경 내용**: 세션 종료 처리 추가

**기존**:
- `ended_at`이 항상 `NULL`로 유지
- 재시도 시 기존 세션 재사용 (데이터 혼선)

**변경 후**:
- 제출 완료 시 `ended_at` 설정 (세션 종료)
- 재시도 시 새 세션 생성 (데이터 분리)

**용도**:
- 각 시도가 독립적인 세션으로 관리됨
- 이전 시도와 새 시도의 데이터 혼선 방지

---

## 📊 데이터 흐름

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

---

## 🔍 주요 조회 예시

### 특정 세션의 모든 평가 조회
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

### 턴별 평가 점수 조회
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

### 전체 플로우 평가 조회
```sql
SELECT 
    details->>'score' AS holistic_flow_score,
    details->>'analysis' AS holistic_flow_analysis
FROM ai_vibe_coding_test.prompt_evaluations 
WHERE session_id = 123 
  AND evaluation_type = 'HOLISTIC_FLOW';
```

### 세션 종료 여부 확인
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

---

## ⚠️ 주의사항

1. **평가 유형과 turn의 관계**
   - `TURN_EVAL`: turn 필수 (NOT NULL)
   - `HOLISTIC_FLOW`: turn NULL 필수
   - Check Constraint로 강제됨

2. **details JSONB 구조**
   - 모든 평가 데이터는 `details` JSONB에 저장
   - 필수 필드: `score`, `analysis`
   - 선택 필드: `intent`, `intent_types`, `rubrics`, `evaluations`, `detailed_feedback`, `turn_score` 등
   - 조회 시 `details->>'score'` 형태로 접근

3. **중복 저장 방지**
   - Unique Index로 같은 평가가 여러 번 저장되는 것 방지
   - 저장 전 기존 평가 확인 후 업데이트 또는 생성
   - `EvaluationStorageService`에서 자동 처리

4. **세션 종료 시점**
   - 제출 완료 시에만 `ended_at` 설정
   - 평가 실패 시에는 설정 안 함 (롤백 가능)

5. **ENUM 타입 사용**
   - `evaluation_type`은 ENUM 타입으로 정의되어 타입 안정성 보장
   - SQLAlchemy 모델에서 `EvaluationTypeEnum` 사용

---

## 📚 관련 문서

- [Quick DB Guide](./Quick_DB_Guide.md) - DB 사용 가이드
- [State Flow and DB Storage](./State_Flow_and_DB_Storage.md) - State 흐름 및 저장 전략

---

## 🔄 변경 이력

| 날짜 | 변경사항 |
|------|---------|
| 2025-01-15 | `prompt_evaluations` 테이블 생성 |
| 2025-01-15 | Check Constraint 및 Unique Index 추가 |
| 2025-01-15 | 세션 종료 처리 (`ended_at` 설정) |
| 2025-01-XX | `evaluation_type_enum` ENUM 타입 추가 |
| 2025-01-XX | `prompt_evaluations` 테이블 구조 개선 |
| 2025-01-XX | `node_name`, `score`, `analysis` 컬럼 제거 (details로 통합) |
| 2025-01-XX | `evaluation_type` VARCHAR → ENUM 변경 |
| 2025-01-XX | `details` JSONB를 NOT NULL로 변경 |
