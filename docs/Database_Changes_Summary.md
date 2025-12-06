# 데이터베이스 변경사항 요약

## 📋 개요

LangGraph 평가 시스템의 PostgreSQL 데이터베이스 주요 변경사항을 요약한 문서입니다.

---

## 🗂️ 주요 변경사항

### 1. `prompt_evaluations` 테이블 (신규 생성)

**용도**: 평가 결과 저장
- **턴별 평가** (Node 4): 각 대화 턴의 평가 결과 저장
- **전체 평가** (Node 6a, 6c): Holistic Flow 및 Performance 평가 결과 저장

**주요 필드**:
- `session_id`: 세션 ID (Foreign Key)
- `turn`: 평가 대상 턴 (NULL이면 세션 전체 평가)
- `evaluation_type`: 평가 유형 (`turn_eval`, `holistic_flow`, `holistic_performance`)
- `score`: 평가 점수 (0-100)
- `analysis`: 평가 분석 텍스트
- `details`: 상세 결과 (JSONB)

**평가 유형별 저장**:
- `turn_eval`: 턴별 평가 (turn 필수)
- `holistic_flow`: 전체 대화 흐름 평가 (turn NULL)
- `holistic_performance`: 코드 실행 성능 평가 (turn NULL)

**안전장치**:
- Check Constraint: 평가 유형에 따른 turn NULL 규칙 강제
- Unique Index: 중복 평가 결과 방지
- Foreign Key: 참조 무결성 보장

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

3. 평가 진행 (백그라운드 또는 제출 시)
   └─ prompt_evaluations INSERT
      ├─ turn_eval (턴별 평가)
      ├─ holistic_flow (전체 흐름 평가)
      └─ holistic_performance (성능 평가)

4. 제출 완료
   └─ prompt_sessions.ended_at 설정 (세션 종료)
```

---

## 🔍 주요 조회 예시

### 특정 세션의 모든 평가 조회
```sql
SELECT * FROM ai_vibe_coding_test.prompt_evaluations 
WHERE session_id = 123 
ORDER BY turn NULLS LAST, created_at;
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
   - `turn_eval`: turn 필수 (NOT NULL)
   - `holistic_flow`, `holistic_performance`: turn NULL 필수

2. **중복 저장 방지**
   - Unique Index로 같은 평가가 여러 번 저장되는 것 방지
   - 저장 전 기존 평가 확인 후 업데이트 또는 생성

3. **세션 종료 시점**
   - 제출 완료 시에만 `ended_at` 설정
   - 평가 실패 시에는 설정 안 함 (롤백 가능)

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
