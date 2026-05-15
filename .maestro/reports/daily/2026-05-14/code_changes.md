# 코드 변경 기록 — 2026-05-14

> **범위**: Vertex AI 기본 경로·자격 증명, LLM 팩토리 통합, N8 토론 모델/로그, 시크릿·예시 env, pytest 기본값

---

## 1. Vertex AI 설정·자격 증명

| 파일 | 변경 내용 | 사유 |
|------|-----------|------|
| `app/core/config.py` | `USE_VERTEX_AI` 기본 `True`. `GOOGLE_SERVICE_ACCOUNT_JSON_PATH` 추가. `GOOGLE_PROJECT_ID` 주석 정리. | Vertex 우선, SA JSON은 파일 경로로 두기 쉽게 |
| `app/core/vertex_auth.py` | **신규** `_load_service_account_dict`, `load_vertex_credentials`, `resolve_vertex_project_id` (`.env`의 `GOOGLE_PROJECT_ID` 우선, 없으면 SA JSON의 `project_id`) | 경로/문자열/ADC 분기 한곳으로 모음 |
| `app/domain/langgraph/utils/llm_factory.py` | `USE_VERTEX_AI` 시 `ChatVertexAI`, `project=resolve_vertex_project_id()`, `credentials=load_vertex_credentials()` | Studio/Vertex 단일 진입 `create_gemini_llm` |
| `app/domain/langgraph/nodes/chat/n2_intent_analyzer.py` | 로컬 Vertex 분기 제거 → `create_gemini_llm(temperature=0.3)` | 중복 제거 |
| `app/domain/langgraph/nodes/chat/n3_writer.py` | 동일 → `create_gemini_llm(temperature=settings.LLM_TEMPERATURE, max_output_tokens=…)` | 동일 |
| `app/domain/langgraph/nodes/eval/utils.py` | 동일 → `create_gemini_llm(temperature=0.1)` | 동일 |
| `app/domain/langgraph/nodes/eval_turn/utils.py` | `get_llm_for_model` / `get_llm`이 `create_gemini_llm`만 호출 | N4·N7·N8 토론과 동일 경로 |
| `app/domain/langgraph/nodes/system/system_nodes.py` | 동일 → `create_gemini_llm(temperature=0.3)` | 동일 |
| `tests/conftest.py` | 파일 최상단 `os.environ.setdefault("USE_VERTEX_AI", "false")` | pytest 수집 전에 비Vertex로 두어 기존 `GEMINI_API_KEY` 흐름 유지 |

**운영 참고**: GCP에서 `aiplatform.endpoints.predict`·빌링·리전별 모델 가용성(`gemini-2.5-pro` 등)은 프로젝트 설정에 따름. N8 YAML의 Pro는 일부 리전에서 404일 수 있음.

---

## 2. 시크릿·문서·gitignore

| 파일 | 변경 내용 |
|------|-------------|
| `secrets/.gitkeep` | SA JSON 등 로컬 전용 디렉터리 유지 |
| `.gitignore` | `secrets/*` + `!secrets/.gitkeep` (JSON만 제외, 폴더는 추적) |
| `env.example` | Vertex 블록(`USE_VERTEX_AI`, `GOOGLE_PROJECT_ID`, `GOOGLE_SERVICE_ACCOUNT_JSON_PATH` 등) |
| `env.prod.example` | Vertex 예시·`GOOGLE_PROJECT_ID` 비우면 SA `project_id` 폴백 안내 |
| `README.md` | LLM 관련 env 표 갱신 (`GEMINI_API_KEY` 조건부, `GOOGLE_SERVICE_ACCOUNT_JSON_PATH` 등) |

---

## 3. N8 토론 (`subgraph_debate` · `debate_agents.yaml`)

| 파일 | 변경 내용 | 사유 |
|------|-----------|------|
| `app/domain/langgraph/subgraph_debate.py` | 모듈 로드 후 `_log_n8_debate_llm_registry()` — 역할별 `yaml` 모델명·LangChain 클라이언트 해석 모델·`USE_VERTEX_AI` INFO 로그 | 실제 Pro/Flash 바인딩 확인 |
| `app/domain/langgraph/prompts/debate_agents.yaml` | **성능 테스트 시** strict/neutral/verdict를 flash로 잠깐 바꿨다가 **원복: `gemini-2.5-pro`** (advocate는 계속 `gemini-2.5-flash`) | 최종 상태는 기존 Pro 설정 |

**참고**: N8 출력 JSON 스키마는 YAML이 아니라 `subgraph_debate.py`의 `AgentOpinion` / `FinalVerdict` + `with_structured_output`.

---

## 4. 그 외 (대화·작업에서만 수행, 코드 미변경 또는 일회성)

- `scripts/export_evaluation_json.py`로 `1_1`, `2_2` 등 조합보내기 실행 (경로: `data/{exam}_{participant}_평가.json`).
- Vertex 스모크: `create_gemini_llm().invoke(...)` — 빌링/IAM/모델 가용성 이슈 후 정상 통과 사례 있음.

---

## 5. 관련 모듈 맵

- LLM 설정 단일 소스: `app/core/config.py` + `.env`
- Studio/Vertex 클라이언트 조립: `app/domain/langgraph/utils/llm_factory.py` + `app/core/vertex_auth.py`
- N7 모델: `DEFAULT_LLM_MODEL` (`get_llm()`), N8 역할별 모델: `debate_agents.yaml`
