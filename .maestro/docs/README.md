# Maestro 전용 문서 (`.maestro/docs/`)

프로젝트 루트 `docs/` 와 별도로, **운영·테스트·에이전트 온보딩**을 Maestro 쪽에 모아 둔 폴더입니다.

---

## 먼저 볼 문서 (순서 권장)

| 순서 | 문서 | 용도 |
|------|------|------|
| 1 | [평가_파이프라인_플로우.md](./평가_파이프라인_플로우.md) | **제출 평가 N4~N9** 노드 순서·텍스트 다이어그램·노드별 입출력·N8 서브그래프·N9 공식 (그래프 이해 최우선) |
| 2 | [Judge0_Batch_And_Genai_Vertex.md](./Judge0_Batch_And_Genai_Vertex.md) | **N5 Judge0 Batch API**, **Genai Vertex LLM** (2026-05-17) |
| 3 | [Eval_Submission_Timeout.md](./Eval_Submission_Timeout.md) | **제출 평가 E2E 10분**, `ai-evaluation-timeout[노드]` |
| 4 | [Submit_테스트_ENV_평가덤프_가이드.md](./Submit_테스트_ENV_평가덤프_가이드.md) | Submit 테스트, `.env`, 평가 JSON·Redis 토론 덤프 |
| 5 | [DB_Save_Path_Audit.md](./DB_Save_Path_Audit.md) | `prompt_messages.meta`·Redis turn 정규화·가드레일 백필 (2026-05-19) |
| 6 | [../DOCS_REFERENCE.md](../DOCS_REFERENCE.md) | 루트 `docs/` 22개 파일별 참조 시점 |
| 7 | [../agents/submit_test_agent.md](../agents/submit_test_agent.md) | Submit·덤프 유지보수 담당 에이전트 프롬프트 |

V2.1 단계별 작업 지시는 `V2.1_Step_*.md`, 변경 이력은 `V2.1_Change_Log.md` 등을 본다.

---

## 문서 목록

| 문서 | 내용 |
|------|------|
| [N4_V3_1_프롬프트_이력_및_미사용_YAML.md](./N4_V3_1_프롬프트_이력_및_미사용_YAML.md) | N4 eval_turn v3.1·의도 단일 LLM 변경 요약, `prompts/*.yaml` 런타임 사용 여부·미사용 파일 목록 (2026-04-19) |
| [평가_파이프라인_플로우.md](./평가_파이프라인_플로우.md) | LangGraph 평가 파이프라인 한 장 요약 (루트 `docs/평가_파이프라인_플로우.md` 와 동기화) |
| [Judge0_Batch_And_Genai_Vertex.md](./Judge0_Batch_And_Genai_Vertex.md) | Judge0 Batched Submissions(TC≥2), ChatGoogleGenerativeAI+Vertex, N5 TC별 Performance |
| [Eval_Submission_Timeout.md](./Eval_Submission_Timeout.md) | `EVAL_SUBMISSION_TIMEOUT_SEC`, 백그라운드 E2E, 노드 추적·타임아웃 로그 |
| [Submit_테스트_ENV_평가덤프_가이드.md](./Submit_테스트_ENV_평가덤프_가이드.md) | Submit 테스트 절차, `test_ids.json`, `.env` 관련 변수, 평가 JSON·Redis 토론 덤프 사용법 |
| [DB_Save_Path_Audit.md](./DB_Save_Path_Audit.md) | PG/Redis 저장 순서, conversation vs storage turn, 가드레일 meta·백필 |
| [../agents/submit_test_agent.md](../agents/submit_test_agent.md) | 위 주제를 코드·문서로 유지보수하는 Maestro 에이전트 시스템 프롬프트 |

업데이트 시기: 코드·스크립트 동작이 바뀌면 해당 가이드의 날짜·절차를 함께 수정합니다. **평가 노드 구조**가 바뀌면 `평가_파이프라인_플로우.md`를 루트 `docs/` 사본과 함께 갱신합니다.
