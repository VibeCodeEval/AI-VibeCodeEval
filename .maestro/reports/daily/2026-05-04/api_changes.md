# API·스키마 변경 기록 — 2026-05-04

---

## 1. `POST /api/chat/messages`

### 요청 본문: `context`

| 필드 | 이전 | 이후 |
|------|------|------|
| `context.specVersion` | 필수 `integer` (`Field(...)`) | **선택** `integer \| null` (미입력·`null` 허용) |

### 동작

- **`specVersion`**: DB 의미는 **`problem_specs.version`** (버전 번호).
- **미입력/`null`**: 세션의 `spec_id`(PK)로 `problem_specs` 행을 조회해 `version`을 사용. 행이 없으면 `1`.
- LangGraph `process_message`에 넘기는 식별자는 **`spec_id` (`problem_specs.spec_id`)** 만 사용. `specVersion`을 스펙 PK 대용으로 쓰지 않음.

### 오류 코드

- `SPEC_ID_MISSING` (400): 세션·`exam_participants` 모두에서 `spec_id`를 찾을 수 없을 때.

---

## 2. 내부 모델 (ORM)

- **`ProblemSpec`**: Python 속성 및 DB 컬럼 PK = **`spec_id`** (레거시 속성명 `id` 제거).
- **`SubmitCodeRequest.specId`**, 세션·제출의 `spec_id` FK: 모두 **`problem_specs.spec_id`** 참조.

---

## 3. Judge / State (참고)

- **`code_correctness_score`**: State 및 N5 출력 스케일 **0 ~ `CODE_CORRECTNESS_MAX_POINTS`** (기본 30). N9 총점에서는 0~100으로 환산 후 가중치 적용.
- **`JudgeResult`**: 선택 필드 `passed_test_cases`, `total_test_cases` (다중 TC 시).

---

## 4. Core(Spring) 연동 권장

- 가능하면 `context.specVersion`에 **`problem_specs.version`** 정수를 포함.
- 생략·`null`도 Worker가 DB로 보완 가능.
