# Submit 테스트·환경(.env)·평가 JSON·토론 덤프 가이드

> **위치**: `.maestro/DOCS/`  
> **작성 기준일**: 2026-04-05  
> **대상**: 로컬에서 Submit 평가 파이프라인을 돌리고, DB·Redis 결과를 파일로 남기려는 경우

---

## 1. 무엇을 검증하는지

- **PostgreSQL** (`ai_vibe_coding_test` 스키마): `prompt_sessions`, `prompt_messages`, `prompt_evaluations`, `submissions`, `scores` 등
- **Redis** (선택): N4 턴 로그, N8 토론 로그(`debate_log:session_{id}`) — `DEBATE_LOG_TO_REDIS=true`일 때만 N8이 기록
- **산출물**: `scripts/export_evaluation_json.py` 및 `test_scripts/check_submit_result.py`가 만드는 **통합 JSON 번들** (단일 턴 → 홀리스틱 → **Redis 토론** → 코드 점수)

---

## 2. 권장 워크플로 (요약)

1. Postgres(및 필요 시 Redis) 기동 — `docker-compose.dev.yml` 등 프로젝트 안내에 맞춤  
2. **`.env`** 에 DB·Redis·LLM 키 정합성 확인 (아래 §4)  
3. 스키마·테이블 없으면 `scripts/init-db.sql` 적용 (`setup_submit_test_data.py` 주석에 예시 있음)  
4. **`uv run python test_scripts/setup_submit_test_data.py`** 로 시험용 exam / participant / session / submission 시드 및 **`test_ids.json`** 생성  
5. 실제 **채팅·제출·평가**는 Worker/API 또는 `test_scripts/test_submit_*.py` 등으로 수행 (이 문서는 “데이터 준비 이후 결과 확인”에 초점)  
6. 결과 확인: **`uv run python test_scripts/check_submit_result.py`** 또는 **`uv run python scripts/export_evaluation_json.py --session-id <id> --stdout`**  
7. Redis에만 있는 N8 토론만 따로 받고 싶으면: **`uv run python scripts/dump_debate_redis.py --session-id <prompt_sessions.id>`**

---

## 3. `test_ids.json`

`setup_submit_test_data.py` 성공 시 **프로젝트 루트**에 생성됩니다.

예시 필드:

- `session_id`: `prompt_sessions.id` (DB 정수)
- `submission_id`: `submissions.id`
- `exam_id`, `participant_id`, `spec_id`, `exam_participant_id`

**주의**: `export_evaluation_json` / `check_submit_result`의 **`code_scores`는 “해당 세션(exam+participant+spec)의 최신 submission”** 기준입니다. 예전에 돌린 `submission_id`와 번들 안의 제출 id가 다를 수 있으며, 스크립트는 그 경우 **stderr에 경고**만 출력합니다.

---

## 4. `.env` 및 설정 (`app/core/config.py` 기준)

앱·스크립트는 **`pydantic-settings`** 로 `.env`를 읽습니다. 아래는 Submit 테스트·평가 덤프와 직접 맞닿는 항목입니다.

| 변수 | 설명 |
|------|------|
| `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | 비동기 URL은 내부에서 `POSTGRES_URL`로 조합. **Docker 포트(예: 5435)** 와 로컬 `.env`가 일치해야 함 |
| `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`(선택), `REDIS_DB` | 턴 로그·토론 로그·큐. **미기동 시** export의 `debate_redis.unavailable_reason`에 연결 실패 등이 기록될 수 있음 |
| `VIBECODE_PARTICIPANT_TABLE` | 참가자 테이블명. Core DB는 `users`, `init-db.sql` 기본은 `participants` |
| `VIBECODE_SEED_EXAM_CREATED_BY` | `exams.created_by` NOT NULL 스키마용. 비우면 시드 스크립트가 `admins` 최소 id 사용 시도 |
| `DEBATE_LOG_TO_REDIS` | `true`일 때 N8 종료 시 Redis에 `debate_log:session_{n}` 저장 (기본값 `True` in config — 운영에서 끄려면 `.env`에 `false`) |
| `CHECKPOINT_TTL_SECONDS` | Redis 키 TTL(초). 토론 로그도 동일 TTL 계열로 만료될 수 있음 (기본 86400) |
| `GEMINI_API_KEY` / `OPENAI_API_KEY`, `DEFAULT_LLM_MODEL` 등 | 평가·토론 LLM 호출에 필요 |
| `DEBUG` | `True`면 SQLAlchemy **echo** 로 쿼리가 터미널에 대량 출력됨 (`session.py`의 `create_async_engine(..., echo=settings.DEBUG)`) |

Judge0·콜백 URL 등은 제출 실행 경로에 따라 추가로 필요합니다 (`JUDGE0_API_URL` 등).

---

## 5. 스크립트 역할 정리

| 경로 | 역할 |
|------|------|
| `test_scripts/setup_submit_test_data.py` | DB 시드 + 루트 `test_ids.json` 기록 |
| `test_scripts/check_submit_result.py` | 기본: `export_evaluation_json._export_session_bundle`과 **동일 구조 JSON**을 stdout (옵션 `-o` 저장). `--summary`: 예전 텍스트 요약만 |
| `scripts/export_evaluation_json.py` | `--session-id` 또는 participant+spec/problem 조건으로 `data/*.json` 또는 `--stdout` |
| `scripts/dump_debate_redis.py` | Redis `debate_log:session_{id}` 만 단독 덤프 (`--session-id`는 숫자면 자동으로 `session_` 접두) |
| `app/infrastructure/cache/debate_redis_dump.py` | 위 Redis 덤프와 export의 **`debate_redis.dump`** 가 공유하는 로직 |

LangGraph 쪽 Redis 세션 id는 API에서 **`session_{prompt_sessions.id}`** 형태로 쓰이는 것이 일반적입니다. `dump_debate_redis.py`에 숫자만 넘기면 동일 규칙으로 정규화됩니다.

---

## 6. 통합 JSON 번들 키 순서 (요약)

`export_evaluation_json` / `check_submit_result` (기본 모드) 출력:

1. **`meta`**: 세션·시험·참가자·spec·`exported_at` 등  
2. **`single_turn_evaluation`**: `prompt_messages`, 턴별 `TURN_EVAL` (`details`, `rubrics_extracted` 등)  
3. **`whole_session_evaluation`**: `HOLISTIC_FLOW` 평가 행들 (없으면 빈 배열)  
4. **`debate_redis`**: `langgraph_session_id`, `redis_key`, **`dump`** (성공 시 `dump_debate_redis` 파일과 동일 본문 + `_dump_meta`), 실패·미기록 시 `dump: null` 및 **`unavailable_reason`**  
5. **`code_scores`**: 최신 `submission` 요약 + `scores` 행 (`rubric_json` 전체 포함 가능)

---

## 7. 자주 나오는 이슈

- **`debate_redis.dump`가 null**  
  - 평가 당시 `DEBATE_LOG_TO_REDIS=false` 이었거나, TTL 만료·Redis 재시작·키가 다른 세션 id로 저장된 경우  
- **Holistic DB 행은 없는데 토론만 Redis에 있음**  
  - 파이프라인·버전에 따라 DB `HOLISTIC_FLOW`와 Redis 토론 저장 시점이 다를 수 있음 → JSON에서 `whole_session_evaluation`과 `debate_redis`를 함께 확인  
- **SQL 로그가 너무 많음**  
  - `.env`에서 `DEBUG=false` 권장 (결과 확인 스크립트만 돌릴 때 특히)  

---

## 8. 관련 코드·문서

- `test_scripts/setup_submit_test_data.py` (상단 docstring: 스키마·Core DB 제약)  
- `scripts/export_evaluation_json.py`, `scripts/dump_debate_redis.py` (각 파일 상단 사용 예)  
- 저장소 루트 `test_scripts/README.md` (다른 통합 테스트 목록; 경로·이름은 프로젝트 진행에 따라 상이할 수 있음)

이 가이드는 **`.maestro/DOCS/`** 에만 두고, 상위 Maestro 인덱스는 `.maestro/README.md` 폴더 구조 설명을 참고하면 됩니다.
