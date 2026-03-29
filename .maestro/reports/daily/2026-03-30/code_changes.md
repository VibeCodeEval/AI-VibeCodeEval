# 코드·스크립트·데이터 작업 (2026-03-30)

> DB 평가 스냅샷 JSON 내보내기, 시험 15·참가자 5 샘플 저장, 실패 요인 분석 보고 연계.

---

## 1. 요약

| 항목 | 내용 |
|------|------|
| 신규 스크립트 | `scripts/export_evaluation_json.py` — 세션 단위로 턴 평가·홀리스틱·코드 점수를 한 JSON에 묶어 저장 |
| 산출물 | `data/{exam_id}_{participant_id}_평가.json` (예: `data/15_5_평가.json`) |
| CLI | `--exam-id`, `--participant-id`, `--session-id`, `--spec-id` / `--problem-id`, `-o`, `--stdout` |
| 분석 보고 | `exam15_participant5_failure_analysis.md` — 동일 세션의 저점·오류 요인 정리 |

---

## 2. `scripts/export_evaluation_json.py`

### 2.1 목적

- PostgreSQL(`POSTGRES_URL`)에서 `prompt_sessions`, `prompt_messages`, `prompt_evaluations`, `submissions`, `scores` 등을 조회해 **단일 JSON**으로 내보냄.
- **키 순서(의미)**: `meta` → `single_turn_evaluation`(메시지 + TURN_EVAL) → `whole_session_evaluation`(HOLISTIC_FLOW) → `code_scores`(제출 + Judge0 연동 점수).

### 2.2 동작·회피 패턴

| 이슈 | 대응 |
|------|------|
| `prompt_messages.role`이 DB 문자열(`user`/`AI`)과 Python Enum 불일치 | ORM 대신 `role::text` **raw SQL**로 메시지 로드 |
| `problem_specs` 조회 실패 시 세션 트랜잭션 전체 abort | `problem_id`는 **`_lookup_problem_id_for_spec`**에서 **별도 DB 컨텍스트**로 조회 (export 본 트랜잭션 보호) |
| 시험·참가자로 세션 찾기 | `--exam-id` + `--participant-id` → `_find_session_ids` |

### 2.3 사용 예

```bash
uv run python scripts/export_evaluation_json.py --exam-id 15 --participant-id 5
```

기본 출력: `data/15_5_평가.json`

---

## 3. 데이터 산출물

| 파일 | 설명 |
|------|------|
| `data/15_5_평가.json` | 시험 15, 참가자 5, 세션 5 스냅샷 (export 검증용) |

---

## 4. 관련 보고 (코드 외)

| 파일 | 설명 |
|------|------|
| `exam15_participant5_failure_analysis.md` | 동일 JSON 기준 등급 F·`turn_analysis` 누락·코드 0점 등 **실패·저점 요인** 서술 |

---

## 5. 알려진 한계 (스냅샷 기준)

- `meta.problem_id`가 `null`인 경우: DB 스키마·ORM과 `problem_specs` PK 컬럼명 불일치 시 lookup 실패 가능.
- `rubric_json.integrated_evaluation.error`: `"turn_analysis 데이터가 없습니다"` — 최종 집계 시 턴 분석 데이터 미연결 시 기존 DB에 남을 수 있음 (앱 로직 이슈, 본 스크립트 범위 아님).
