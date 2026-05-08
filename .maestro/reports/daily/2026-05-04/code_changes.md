# 코드 변경 기록 — 2026-05-04

> **범위**: problem_specs ORM 정합성, Judge0/N5 TC·점수, 큐 결과, 채팅 `context.specVersion` 처리

---

## 1. DB 스키마 vs SQLAlchemy (`problem_specs` PK)

| 파일 | 변경 내용 | 사유 |
|------|-----------|------|
| `app/infrastructure/persistence/models/problems.py` | `ProblemSpec` PK를 `id` → **`spec_id`**로 매핑. `Problem.current_spec_id` FK 대상을 `problem_specs.spec_id`로 수정. | `scripts/init-db.sql` 실제 DDL은 `spec_id BIGSERIAL PRIMARY KEY`. ORM이 `problem_specs.id`를 조회해 `UndefinedColumnError` 발생 및 `get_problem_info` 폴백(TSP 더미) 유발. |
| `app/infrastructure/persistence/models/exams.py` | `ExamParticipant.spec_id` FK → `problem_specs.spec_id` | 동일 |
| `app/infrastructure/persistence/models/sessions.py` | `PromptSession.spec_id` FK → `problem_specs.spec_id` | 동일 |
| `app/infrastructure/persistence/models/submissions.py` | `Submission.spec_id` FK → `problem_specs.spec_id` | 동일 |
| `app/infrastructure/repositories/exam_repository.py` | `ProblemSpec.spec_id == spec_id` 조회, docstring 정리 | 조회 조건을 실제 PK에 맞춤 |
| `app/domain/langgraph/utils/problem_info.py` | `get_problem_info` doc: PK = `spec_id`. `spec_row`만 있으면 `problem` 없이도 DB 컨텍스트 로드 | 조인 실패 시 전체 폴백 방지 |
| `tests/test_problem_spec_model.py` | PK 컬럼명·FK 타깃 단위 테스트 | 회귀 방지 |
| `scripts/export_evaluation_json.py` | `--spec-id` help 문구 | 용어 통일 |

---

## 2. N5 Judge0 · Correctness 점수 · 큐

| 파일 | 변경 내용 | 사유 |
|------|-----------|------|
| `app/domain/langgraph/nodes/eval/n5_integrated_evaluator.py` | `problem_context`의 **전체 `test_cases`**를 `JudgeTask`에 전달. `_scores_from_correctness_result`에서 `passed_test_cases`/`total_test_cases` 기반 **부분 점수**. 만점은 `settings.CODE_CORRECTNESS_MAX_POINTS`(기본 **30**): `(통과/총 TC)×30`. 스마트 게이트·TC 없음 경로 동일 스케일 정리. | 기존 첫 TC만 사용·전부 통과만 100점 문제. 루브릭 만점 30 기준 반영. |
| `app/domain/queue/adapters/base.py` | `JudgeResult`에 `passed_test_cases`, `total_test_cases` | 부분 통과 집계 |
| `app/application/workers/judge_worker.py` | 다중 TC 시 위 필드 설정 | N5와 연동 |
| `app/domain/queue/adapters/redis.py` | 결과 직렬화에 필드 추가. 저장 후 상태 항상 **`completed`** | `status=error`인 부분 통과도 결과 조회 가능 |
| `app/domain/queue/adapters/memory.py` | 저장 후 상태 **`completed`** | Redis와 동일 |
| `app/core/config.py` | `CODE_CORRECTNESS_MAX_POINTS` (기본 30) | 환경 변수로 조정 가능 |
| `app/domain/langgraph/nodes/eval/n9_final_scores.py` | `code_correctness_score`를 0~30으로 보고 총점용 **`(raw/30)×100`** 환산. 구버전 0~100 체크포인트 호환. | 프롬프트/퍼포먼스 축과 가중치 일관 |
| `app/domain/langgraph/subgraph_debate.py` | Judge0 블록에 정확성 `x / CODE_CORRECTNESS_MAX_POINTS` 표기 | 토론 컨텍스트 명확화 |

**참고**: Judge0 CE는 제출당 stdin/expected 한 세트이므로, `execute_test_cases`는 **TC마다 별도 submission** (순차). API 한 번에 10 TC 묶음은 표준 Judge0에 없음.

---

## 3. 채팅 API — `context.specVersion`

| 파일 | 변경 내용 | 사유 |
|------|-----------|------|
| `app/presentation/schemas/chat.py` | `ProblemContext.specVersion`을 **`Optional[int] = None`** | Core가 `null` 전달 시 Pydantic 오류 방지 |
| `app/presentation/api/routes/chat.py` | `_resolve_spec_id_and_version_for_message`: `spec_id`는 세션·`exam_participants`, `specVersion`은 요청값 또는 **`problem_specs.version`**. LangGraph에는 **`spec_id`만** 전달. | 기존 `session.spec_id or request.context.specVersion`은 **버전을 PK처럼 쓰는 버그** |

---

## 4. 기타 문서·스키마 설명

| 파일 | 변경 내용 |
|------|-----------|
| `app/presentation/schemas/chat.py` | `specId` 필드 설명: `problem_specs.spec_id` |
| `app/domain/langgraph/utils/problem_info.py` | API `spec_id` = 테이블 PK `spec_id` 명시 |

---

## 5. 관련 Step

- 평가 파이프라인 N5~N9, DB 영속성(`problem_specs`), `POST /api/chat/messages`.
