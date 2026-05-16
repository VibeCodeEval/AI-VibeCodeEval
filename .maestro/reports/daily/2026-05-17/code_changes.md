# 코드 변경 기록 — 2026-05-17

> **범위**: Judge0 Batched Submissions, Genai Vertex LLM, N5 Correctness/Performance 채점, 의존성 정리

---

## 1. Judge0 Batched Submissions (TC ≥ 2)

| 파일 | 변경 내용 | 사유 |
|------|-----------|------|
| `app/infrastructure/judge0/client.py` | `submit_batch`, `get_batch_results`, `wait_for_batch_results` 추가. `execute_test_cases`: TC 1 → 단건 `POST /submissions`, TC ≥ 2 → `POST/GET /submissions/batch`. 청크 `JUDGE0_MAX_BATCH_SIZE`(20). | RapidAPI Batched Submissions 50/일 절약, TC마다 HTTP 낭비 제거 |
| `app/domain/langgraph/nodes/eval/n5_integrated_evaluator.py` | TC 개수 로그 (단건 vs batch). | 운영 추적 |
| `app/core/config.py` | `JUDGE0_MAX_BATCH_SIZE=20` | Judge0 CE batch 상한 |
| `tests/test_judge0_client_batch.py` | **신규** Mock 단위 테스트 6건 | 분기·매핑 검증 |
| `tests/conftest.py` | `GEMINI_API_KEY` setdefault (수집 시 import 오류 방지) | pytest |

**검증**: `.env` + RapidAPI — `test_judge0_integration.py` 3 passed, batch 스모크 3/3 TC passed.

---

## 2. LLM — ChatGoogleGenerativeAI + Vertex

| 파일 | 변경 내용 | 사유 |
|------|-----------|------|
| `app/domain/langgraph/utils/llm_factory.py` | `ChatVertexAI` 제거. `USE_VERTEX_AI` 시 `ChatGoogleGenerativeAI(vertexai=True, project, location, credentials)`. Studio는 `google_api_key`만. | deprecated 제거, genai 단일 패키지 |
| `app/core/vertex_auth.py` | docstring: `ChatGoogleGenerativeAI` | |
| `pyproject.toml` | `langchain-google-vertexai` 제거, `langchain-google-genai>=4.0.0` | 의존성 슬림화 |
| `uv.lock` / `requirements.txt` | `uv lock --upgrade`, `uv sync --extra dev`, `uv export` | |

**운영**: Vertex는 **SA JSON 그대로**, `GEMINI_API_KEY` 불필요. 과금은 GCP 프로젝트(Vertex).

---

## 3. N5 점수 (Correctness / Performance)

| 파일 | 변경 내용 | 사유 |
|------|-----------|------|
| `app/core/config.py` | `CODE_CORRECTNESS_MAX_POINTS`: 30 → **100**, `CODE_PERFORMANCE_MAX_POINTS=100` | 만점 스케일·config |
| `app/domain/langgraph/nodes/eval/n5_integrated_evaluator.py` | **TC별** `passed=true`일 때만 time·memory raw(0~100). 합산 `(Σ raw / 전체 TC) × (CODE_PERFORMANCE_MAX_POINTS/100)`. 전 TC 통과 게이트 제거. | 부분 통과 TC도 맞은 케이스만 Performance 반영 |
| `app/domain/queue/adapters/base.py` | `JudgeResult.test_case_results` | per-TC time/memory |
| `app/application/workers/judge_worker.py` | batch 결과 리스트 저장 | N5 per-TC |
| `tests/test_n5_performance_gate.py` | per-TC 합산 단위 테스트 | |

---

## 4. 의존성

| 작업 | 내용 |
|------|------|
| `uv lock --upgrade` | langgraph 1.2, fastapi 0.136, pydantic 2.13 등 |
| `uv sync --extra dev` | pytest 등 dev extra |
| 제거(전이) | `langchain-google-vertexai`, gRPC/aiplatform 일부 (genai Vertex 경로로 대체) |

---

## 5. 제출 평가 E2E 타임아웃 (10분)

| 파일 | 변경 내용 | 사유 |
|------|-----------|------|
| `app/core/config.py` | `EVAL_SUBMISSION_TIMEOUT_SEC=600` | 제출 1건 LangGraph 상한 |
| `app/domain/langgraph/eval_timeout_tracking.py` | **신규** contextvars, `wrap_eval_node_tracking`, `ai-evaluation-timeout[노드]` | 타임아웃 시점 노드 로그 |
| `app/domain/langgraph/graph.py` | 메인 그래프 노드 래핑 | 현재 노드 추적 |
| `app/domain/langgraph/nodes/eval/n4_eval_turn_guard.py` | `eval_turn_subgraph:turn_{N}` | N4 서브그래프 구간 |
| `app/presentation/api/routes/session.py` | `wait_for(submit_code)`, `begin/end_eval_tracking`, `_fail_submission_evaluation_background` | 백그라운드 E2E |
| `tests/test_eval_timeout_tracking.py` | **신규** | |

**시작 시점**: `_run_submit_evaluation_background` 진입 (BE Outbox·Judge0 큐와 무관).

---

## 6. 상세 문서

- **Judge0·Genai**: `.maestro/docs/Judge0_Batch_And_Genai_Vertex.md`
- **제출 타임아웃**: `.maestro/docs/Eval_Submission_Timeout.md`
- **API·State**: `.maestro/reports/daily/2026-05-17/api_changes.md`
