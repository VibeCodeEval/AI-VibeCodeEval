# 🤖 AI Vibe Coding Test Worker

> LangGraph 기반 AI 코딩 테스트 평가 시스템 (FastAPI)

## 📋 프로젝트 개요

이 프로젝트는 **AI 바이브 코딩 테스트**를 위한 FastAPI 기반 AI 워커 서버입니다. 
Spring Boot 백엔드와 통합되어 동작하며, **LangGraph**를 사용하여 복잡한 AI 평가 플로우를 구현합니다.

### 핵심 기능
- 🎯 **턴 단위 프롬프트 평가 (제출 시 일괄)**: `eval_turn.yaml` 기준 **4대 루브릭(R1~R4)**·의도별 게이트(예: CREATION, DEBUGGING, FOLLOW_UP 등)
- 🔍 **의도 분류**: 채팅·턴 평가에서 **다중 의도(5-way / 세부 의도)** 로 라우팅 (구현은 `intent_analyzer`·Eval Turn 서브그래프)
- 🛡️ **가드레일**: 부적절한 요청 차단 및 교육적 피드백
- ⚖️ **제출 후 평가 파이프라인**: Judge0 실행(N5) → Radon·AST 정적 분석(N6) → 단일 LLM 코드 리뷰(N7) → **다중 에이전트 토론(N8)** → 최종 집계(N9)
- 📊 **종합 점수**: **Prompt 40% · Correctness 40% · Performance 20%** (Prompt는 턴 평균 + 토론 종합 점수 등 조합, `aggregate_final_scores` 참고)
- 🌐 **WebSocket 스트리밍**: 토큰 단위 응답 스트리밍

---

## 🏗️ 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                        Spring Boot Backend                       │
│                   (메인 API, 사용자 관리, 문제 관리)                │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP API / WebSocket
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AI Worker (FastAPI)                           │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                   LangGraph Main Flow                      │  │
│  │  1. Handle Request (상태 로드)                             │  │
│  │  2. Intent Analyzer (의도 분석 + 가드레일)                 │  │
│  │  3. Writer LLM (AI 답변 생성)                              │  │
│  │  4. Eval Turn Guard (제출 시 모든 턴 Eval Turn 서브그래프)  │  │
│  │  5. Main Router (제출 분기)                                │  │
│  │  N5 Judge0 → N6 정적분석 → N7 코드리뷰 LLM → N8 토론 → N9 집계 │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              Eval Turn SubGraph (실시간 평가)               │  │
│  │  Intent Analysis → 의도별 Evaluator → Summarize → 로그 집계  │  │
│  └───────────────────────────────────────────────────────────┘  │
└────────────────┬──────────────────────────┬─────────────────────┘
                 │                          │
                 ▼                          ▼
     ┌───────────────────┐      ┌───────────────────┐
     │   PostgreSQL      │      │      Redis        │
     │  (영구 데이터)     │      │  (세션, 턴 로그)   │
     │  - 시험 정보       │      │  - graph_state    │
     │  - 참가자          │      │  - turn_logs      │
     │  - 제출 내역       │      │  - turn_mapping   │
     └───────────────────┘      └───────────────────┘
```

---

## 📊 LangGraph 플로우 상세

### 메인 그래프 (Main Graph)

#### 일반 채팅 플로우 (is_submission=False)

```
START
  │
  ▼
┌────────────────────────────────────────┐
│  1. Handle Request Load State          │
│  - Redis에서 기존 상태 로드            │
│  - 턴 번호 증가 (current_turn++)       │
│  - 메시지 히스토리 관리                │
└────────────────────────────────────────┘
  │
  ▼
┌────────────────────────────────────────┐
│  2. Intent Analyzer                    │
│  - Gemini LLM으로 의도 분석            │
│  - 가드레일 체크:                      │
│    • 직접 답 요청 차단                 │
│    • Jailbreak 시도 차단               │
│  - 출력: PASSED_HINT / FAILED_*        │
└────────────────────────────────────────┘
  │
  ▼ (PASSED_HINT)
┌────────────────────────────────────────┐
│  3. Writer LLM                         │
│  - Socratic AI 답변 생성               │
│  - 힌트 제공 (코드 불포함)             │
└────────────────────────────────────────┘
  │
  ▼
END (즉시 응답 반환)

⚠️ 중요: 일반 채팅에서는 Eval Turn SubGraph를 실행하지 않습니다.
         평가는 제출 시에만 수행됩니다.
```

#### 제출 플로우 (is_submission=True)

```
START
  │
  ▼
┌────────────────────────────────────────┐
│  1. Handle Request Load State          │
│  - Redis에서 기존 상태 로드            │
│  - 턴 번호 증가                        │
└────────────────────────────────────────┘
  │
  ▼
┌────────────────────────────────────────┐
│  2. Intent Analyzer                    │
│  - 제출 의도 감지 (PASSED_SUBMIT)      │
└────────────────────────────────────────┘
  │
  ▼ (PASSED_SUBMIT)
┌────────────────────────────────────────┐
│  4. Eval Turn Guard                    │
│  - State의 messages에서 모든 턴 추출    │
│  - 모든 턴에 대해 Eval Turn SubGraph 실행│
│  - 동기적으로 모든 턴 평가 완료          │
│  - Redis에 turn_logs 저장              │
└────────────────────────────────────────┘
  │
  ▼
┌────────────────────────────────────────┐
│  5. Main Router                        │
│  - is_submitted == True 확인           │
└────────────────────────────────────────┘
  │
  ▼
┌────────────────────────────────────────┐
│  N5. Eval Code Execution (Judge0)      │
│  - 정확성(테스트 통과) → 통과 시 성능   │
└────────────────────────────────────────┘
  │
  ▼
┌────────────────────────────────────────┐
│  N6. Eval Static Analysis              │
│  - Radon CC, ΔCC(v1 대비), AST 패턴     │
└────────────────────────────────────────┘
  │
  ▼
┌────────────────────────────────────────┐
│  N7. Eval Code Agent                   │
│  - 제출 코드 정성 리뷰 (구조화 LLM)     │
└────────────────────────────────────────┘
  │
  ▼
┌────────────────────────────────────────┐
│  N8. Holistic Debate                   │
│  - 검사/변호인/중재자 + 최종 verdict    │
│  - holistic_flow_score, R4 세션 맥락 등 │
└────────────────────────────────────────┘
  │
  ▼
┌────────────────────────────────────────┐
│  N9. Aggregate Final Scores            │
│  - Prompt 40% / Correctness 40% / Perf 20% │
│  - 등급·DB 저장 (코드 품질 지표 반영)    │
└────────────────────────────────────────┘
  │
  ▼
END
```

**⚠️ 중요 사항**:
- **일반 채팅**: Writer LLM 후 즉시 END (응답 반환), **Eval Turn SubGraph 실행하지 않음**
- **제출**: Eval Turn Guard에서 **모든 턴에 대해 Eval Turn SubGraph를 동기적으로 실행**하여 평가 완료

### Eval Turn SubGraph (실시간 프롬프트 평가)

**⚠️ 중요**: 
- 이 서브그래프는 **사용자 프롬프트**를 평가합니다 (LLM 답변이 아님)
- **일반 채팅 시**: **실행하지 않음** (평가 없이 응답만 반환)
- **제출 시**: Eval Turn Guard에서 **모든 턴에 대해 동기적으로 실행**

```
                    4. Eval Turn SubGraph
                    (백그라운드 비동기 실행)
                             │
                             ▼
        ┌────────────────────────────────────────┐
        │  Intent Analysis                       │
        │  - 사용자 프롬프트 의도 분류            │
        │  - 의도별로 R1~R4 중 일부만 채점 (게이트) │
        └────────────────────────────────────────┘
                             │
        ┌────────────────────┼──────────────────────────┐
        │                    │                          │
        ▼                    ▼                          ▼
   (의도별 단일 Evaluator 노드 — 예: CREATION, DEBUGGING, FOLLOW_UP …)
        │                    │                          │
        │  루브릭: R1 논리·효율, R2 명확성·완전성,      │
        │         R3 구조·예시, R4 맥락 유지 (Likert)   │
        │  (세부 정의: app/domain/langgraph/prompts/eval_turn.yaml) │
        │                    │                          │
        └────────────────────┼──────────────────────────┘
                             ▼
        ┌────────────────────────────────────────┐
        │  4.X Answer Summary                    │
        │  - AI 답변 요약 (10줄 이내)            │
        │  - AI의 추론 과정 요약                  │
        │  - Chaining 평가용 참고 자료           │
        └────────────────────────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────────┐
        │  4.4 Turn Log Aggregation              │
        │  - 턴 로그 생성 및 Redis 저장           │
        │  - 턴 점수 계산:                        │
        │    • 일반: 평가 점수들의 평균           │
        │    • Guardrail 위반: 0점 강제 설정      │
        └────────────────────────────────────────┘
                             │
                             ▼
                       Redis 저장
                 (turn_logs:{session_id}:{turn})
```

**실행 방식**:
- **일반 채팅**: `EvalService.process_message()` → Writer LLM 완료 후 → END (Eval Turn SubGraph 실행하지 않음)
- **제출**: `EvalService.submit_code()` → Eval Turn Guard → State의 messages에서 모든 턴 추출 → 각 턴에 대해 Eval Turn SubGraph 동기 실행 → 모든 턴 평가 완료 후 다음 노드로 진행

### 턴 평가: 의도 · 루브릭 (요약)

**평가 대상**: 해당 턴의 **사용자 프롬프트** (AI 답변은 보조·요약용).

| 루브릭 | 이름 (요지) |
|--------|-------------|
| **R1** | 논리·효율 (또는 탐구형 질문의 구체성) |
| **R2** | 명확성·완전성 |
| **R3** | 구조·예시 |
| **R4** | 맥락 유지 (이전 대화와의 연속성·팩트 일치) |

**의도별 게이트**: `CREATION`, `SETTING`, `REFINEMENT`, `DEBUGGING`, `EXPLORATION`, `FOLLOW_UP` 등에 따라 R1~R4 중 적용 항목과 `turn_score` 산식이 달라집니다. 상세는 `eval_turn.yaml` 및 `docs/Node4_평가_가이드.md` 참고.

**특징**: 제출 직전까지는 일반 채팅만 하고, **제출 시 Eval Turn Guard**에서 턴마다 서브그래프를 **동기 실행**해 Redis `turn_logs` 등에 저장합니다.

---

## 📁 프로젝트 구조 (Hybrid DDD)

프로젝트는 **Hybrid DDD (Domain-Driven Design)** 구조를 따릅니다. 
완전한 DDD보다는 실용적인 접근으로, 명확한 계층 분리와 협업을 위한 명명 규칙을 적용했습니다.

```
app/
├── main.py                          # FastAPI 진입점
├── core/                            # 설정 등
├── domain/langgraph/
│   ├── graph.py                     # 메인 그래프 (채팅 + 제출 후 N5~N9)
│   ├── subgraph_eval_turn.py        # 턴 평가 서브그래프 (N4에서 호출)
│   ├── subgraph_debate.py         # N8 다중 에이전트 토론
│   ├── states.py
│   ├── prompts/                   # YAML 프롬프트 (eval_turn, debate_agents 등)
│   └── nodes/
│       ├── chat/                  # n1_handle_request, n2_intent_analyzer, n3_writer, routers
│       ├── eval/                  # n4_eval_turn_guard, n5~n9 (파일명과 그래프 노드명은 코드 참고)
│       ├── eval_turn/             # (레거시 경로명) 턴 서브그래프용 노드·집계
│       ├── turn_evaluator/        # 의도 분석·루브릭 채점·가중치
│       └── system/                # handle_failure, summarize_memory
├── application/services/          # eval_service, callback_service 등
├── infrastructure/                # persistence, repositories, cache, judge0 …
├── presentation/api/routes/       # chat, session, health
├── presentation/schemas/
│
├── scripts/                                # 개발 스크립트
│   ├── init-db.sql                         # DB 초기화 스크립트
│   └── run_dev.py                          # 개발 서버 실행
│
├── test_scripts/                           # 통합 테스트 스크립트
│   ├── README.md                           # 테스트 가이드
│   ├── test_collect_turns.py              # Phase 1: Turn 수집
│   ├── test_submit_from_saved.py          # Phase 2: 제출
│   ├── test_websocket_stream.py           # WebSocket 스트리밍 테스트
│   ├── test_websocket_simple.py           # WebSocket 간단 테스트
│   ├── list_saved_sessions.py             # 세션 관리
│   ├── test_chat_flow.py                  # 전체 플로우 테스트
│   └── test_gemini.py                     # Gemini API 연결 테스트
│
├── docs/                                   # 기술 문서 (한글 파일명, 목차: 문서_인덱스.md)
├── .maestro/                               # 운영·그래프 맵·변경 로그 (docs/, agents/, reports/)
│
├── data/                                   # 테스트 데이터
│   └── turn_sessions.json                  # 저장된 세션 ID
│
├── docker-compose.yml                      # 프로덕션 Docker 구성
├── docker-compose.dev.yml                  # 개발 Docker 구성
├── Dockerfile
├── pyproject.toml                          # 프로젝트 메타데이터
├── requirements.txt                        # Python 의존성
└── README.md                               # 메인 문서
```

### 계층 설명

- **`app/domain/`**: LangGraph 그래프·노드·프롬프트·상태
- **`app/application/`**: `eval_service` 등 유스케이스
- **`app/infrastructure/`**: DB·Redis·Judge0 등
- **`app/presentation/`**: FastAPI 라우트·스키마
- **`app/core/`**: 설정·공통

---

## 🚀 시작하기

### 사전 요구사항
- Python 3.12 (`.python-version` 참고)
- Docker & Docker Compose
- Gemini API 키
- **uv** (권장) - 빠른 Python 패키지 관리자

### 1. 환경 설정

```bash
# 저장소 클론
git clone <repository-url>
cd AI-VibeCodeEval

# 환경 변수 파일 생성
cp env.example .env

# .env 파일 수정 (API 키 등 설정)
GEMINI_API_KEY=your_gemini_api_key_here
POSTGRES_HOST=localhost
POSTGRES_PORT=5435
REDIS_HOST=localhost
```

### 2. 로컬 개발 (권장)

**2.1 uv 설치**

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Linux/Mac
curl -LsSf https://astral.sh/uv/install.sh | sh

# 또는 pip로 설치
pip install uv

# 설치 확인
uv --version
```

**2.2 Python 환경 및 의존성 설치**

```bash
# uv sync: Python 버전 설치 + 가상 환경 생성 + 의존성 설치 (한 번에)
uv sync

# 또는 단계별로
# 1. Python 3.12 설치 (.python-version 파일 기반)
uv python install 3.12

# 2. 의존성 설치 (pyproject.toml + uv.lock 기반)
uv sync
```

**2.3 Docker로 DB 실행**

```bash
# PostgreSQL & Redis 실행
docker-compose -f docker-compose.dev.yml up -d

# 실행 확인
docker ps
```

**2.4 개발 서버 실행**

```bash
# 방법 1: uv run 사용 (권장)
uv run scripts/run_dev.py

# 방법 2: uvicorn 직접 실행
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 방법 3: 가상 환경 활성화 후 실행 (선택사항)
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# Linux/Mac
source .venv/bin/activate

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. uv 주요 명령어

```bash
# 의존성 설치/업데이트
uv sync                    # pyproject.toml 기반 의존성 설치
uv sync --upgrade          # 모든 패키지 최신 버전으로 업그레이드
uv sync --dev              # 개발 의존성 포함 설치

# Python 버전 관리
uv python install 3.12      # Python 3.12 설치
uv python list             # 설치된 Python 버전 목록
uv python pin 3.12         # 프로젝트 Python 버전 고정

# 스크립트 실행
uv run <script>            # 가상 환경에서 스크립트 실행
uv run python <file.py>    # Python 파일 실행
uv run pytest              # 테스트 실행

# 패키지 관리
uv pip install <package>    # 패키지 설치
uv pip list                 # 설치된 패키지 목록
uv pip freeze               # requirements.txt 형식으로 출력

# 가상 환경 관리
uv venv                     # 가상 환경 생성 (.venv)
uv venv --python 3.12       # 특정 Python 버전으로 가상 환경 생성
```

### 4. pip 사용 (대안)

uv를 사용하지 않는 경우:

```bash
# 가상 환경 생성
python -m venv venv

# 가상 환경 활성화
# Windows PowerShell
.\venv\Scripts\Activate.ps1
# Linux/Mac
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

서버 실행 확인: http://localhost:8000

### 3. Docker Compose로 전체 실행

```bash
# 전체 서비스 빌드 및 실행
docker-compose up -d --build

# 로그 확인
docker-compose logs -f ai_worker

# 서비스 중지
docker-compose down
```

---

## 📡 API 엔드포인트

### 헬스 체크
- `GET /` - API 정보 및 버전
- `GET /api/health` - 헬스 체크 (DB, Redis 상태)

### 세션 관리 API
- `POST /api/session/start` - 응시자 채팅 세션 시작
  ```json
  {
    "examId": 1,
    "participantId": 100,
    "specId": 20
  }
  ```

### 메시지 API
- `POST /api/session/{sessionId}/messages` - 사용자 메시지 전송 & AI 응답
  ```json
  {
    "role": "USER",
    "content": "문제 조건을 다시 설명해줘."
  }
  ```

### 제출 API
- `POST /api/session/{sessionId}/submit` - 응시자 코드 제출 및 평가
  ```json
  {
    "code": "def fibonacci(n): ...",
    "lang": "python"
  }
  ```

### [DEPRECATED] 레거시 엔드포인트
- `POST /api/chat/message` - ⚠️ 더 이상 사용되지 않음 (대신 `/api/session/{sessionId}/messages` 사용)
- `POST /api/chat/submit` - ⚠️ 더 이상 사용되지 않음 (대신 `/api/session/{sessionId}/submit` 사용)

### WebSocket API
- `WS /api/chat/ws` - WebSocket 스트리밍 채팅
  - **특징**: LangGraph를 통한 실시간 토큰 단위 스트리밍
  - **기능**: Delta 스트리밍, 취소 기능, turnId 전달
  
  **메시지 형식**:
  
  **수신 (클라이언트 → 서버)**:
  ```json
  {
    "type": "message",
    "session_id": "session-123",
    "turn_id": 1,
    "message": "사용자 메시지",
    "exam_id": 1,
    "participant_id": 100,
    "spec_id": 10
  }
  ```
  
  ```json
  {
    "type": "cancel",
    "turn_id": 1
  }
  ```
  
  **송신 (서버 → 클라이언트)**:
  ```json
  {
    "type": "delta",
    "content": "토큰",
    "turn_id": 1
  }
  ```
  
  ```json
  {
    "type": "done",
    "turn_id": 1,
    "full_content": "전체 응답"
  }
  ```
  
  ```json
  {
    "type": "error",
    "turn_id": 1,
    "error": "에러 메시지"
  }
  ```

### API 문서
서버 실행 후 자동 생성된 문서 확인:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

**상세 API 명세**: [API_전체_명세.md](./docs/API_전체_명세.md)

---

## 🔧 환경 변수

| 변수명 | 설명 | 기본값 | 필수 |
|--------|------|--------|------|
| `DEBUG` | 디버그 모드 | `false` | ❌ |
| `POSTGRES_HOST` | PostgreSQL 호스트 | `localhost` | ✅ |
| `POSTGRES_PORT` | PostgreSQL 포트 | `5435` | ❌ |
| `POSTGRES_DB` | 데이터베이스명 | `ai_vibe_db` | ✅ |
| `POSTGRES_USER` | DB 사용자 | `ai_vibe_user` | ✅ |
| `POSTGRES_PASSWORD` | DB 비밀번호 | - | ✅ |
| `REDIS_HOST` | Redis 호스트 | `localhost` | ✅ |
| `REDIS_PORT` | Redis 포트 | `6379` | ❌ |
| `REDIS_PASSWORD` | Redis 비밀번호 | - | ❌ |
| `GEMINI_API_KEY` | Gemini API 키 | - | ✅ |
| `USE_VERTEX_AI` | Vertex AI 사용 여부 | `false` | ❌ |
| `GOOGLE_PROJECT_ID` | GCP 프로젝트 ID | - | ⚠️ (Vertex AI 사용 시) |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | 서비스 계정 JSON 문자열 | - | ⚠️ (Vertex AI 사용 시) |
| `JUDGE0_API_URL` | Judge0 API URL | `http://localhost:2358` | ✅ |
| `JUDGE0_API_KEY` | Judge0 API 키 (RapidAPI) | - | ⚠️ (RapidAPI 사용 시) |
| `JUDGE0_USE_RAPIDAPI` | RapidAPI 사용 여부 | `false` | ❌ |
| `SPRING_CALLBACK_URL` | Spring 콜백 URL | `http://localhost:8080/api/ai/callback` | ✅ |
| `DEBATE_LOG_TO_REDIS` | N8 토론 로그를 Redis에 저장 | `true` | ❌ |

---

## 🏆 평가 시스템

### 최종 점수 구성 (`aggregate_final_scores`)

| 항목 | 가중치 | 설명 | 주요 근거 |
|------|--------|------|-----------|
| **Prompt** | 40% | 턴 평균 + 세션 종합(토론) 등 | N4 턴 점수, N8 `holistic_flow_score`, (선택) `integrated_score`, N8 `r4_context_maintenance_score` 보정 |
| **Correctness** | 40% | 테스트 통과 | N5 Judge0 |
| **Performance** | 20% | 시간·메모리 | N5 Judge0 (N6 Radon CC에 따라 가산 배율 가능) |

Prompt 세부: 기본적으로 `holistic_flow_score×0.6 + aggregate_turn_score×0.4` 후, 레거시 `integrated_score`가 있으면 50:50 블렌딩, `r4_context_maintenance_score`가 있으면 Prompt에 20% 가중 반영. 상세 공식은 `docs/점수_계산_로직.md` 및 `app/domain/langgraph/nodes/eval/n9_final_scores.py` 참고.

### 등급 (요약)

정확성 미달 시 **D/F** 우선. 정확성 만점일 때는 **ΔCC·AST·종합점수** 등에 따라 **A~C** 분기 (`n9_final_scores.py`). 단순 임계(90/80/70)만 쓰지 않을 수 있습니다.

### 턴 평가 루브릭 (V3, `eval_turn.yaml`)

**평가 대상**: 사용자 프롬프트. **R1~R4** Likert(1~5) 및 의도별 게이트로 `turn_score` 산출.

| 코드 | 이름 (요지) |
|------|----------------|
| R1 | 논리·효율 |
| R2 | 명확성·완전성 |
| R3 | 구조·예시 |
| R4 | 맥락 유지 (턴 단위) |

### 세션 종합 (N8 Holistic Debate)

제출 후 **검사(strict) / 변호인(advocate) / 중재자(neutral)** 가 라운드 토론하고 **수석 심사관(verdict)** 이 `holistic_flow_score`·분석·(세션) R4 점수 등을 확정합니다. 프롬프트는 `debate_agents.yaml`, 호출 맵은 `.maestro/docs/LangGraph_API_Call_Map.md` 참고.

---

## 🧪 테스트

### 단위 테스트
```bash
# 전체 테스트 실행
pytest tests/ -v

# 커버리지 포함
pytest tests/ -v --cov=app --cov-report=html
```

### 통합 테스트

**1. Phase 1-2 분리 테스트 (권장) ⭐**
```bash
# Phase 1: Turn 수집 (제출 안 함, API Quota 절약)
uv run python test_scripts/test_collect_turns.py

# Phase 2: 저장된 세션으로 제출
uv run python test_scripts/test_submit_from_saved.py

# 저장된 세션 목록 확인
uv run python test_scripts/list_saved_sessions.py
```

**2. WebSocket 테스트**
```bash
# 기본 스트리밍 테스트
uv run python test_scripts/test_websocket_stream.py

# 취소 기능 테스트
uv run python test_scripts/test_websocket_stream.py cancel

# 간단한 연결 테스트
uv run python test_scripts/test_websocket_simple.py
```

**3. 전체 플로우 테스트**
```bash
# 3턴 대화 + 제출 + Redis 검증 (한 번에)
uv run python test_scripts/test_chat_flow.py

# Gemini API 연결 확인
uv run python test_scripts/test_gemini.py
```

**4. 단위 테스트 (pytest)**
```bash
# 전체 테스트 실행
uv run pytest tests/ -v

# 커버리지 포함
uv run pytest tests/ -v --cov=app --cov-report=html

# 특정 테스트 파일만 실행
uv run pytest tests/test_api.py -v
```

### 테스트 가이드
- **`test_scripts/README.md`**: 테스트 스크립트 상세 가이드
- **`docs/테스트_가이드.md`**: 테스트 실행 가이드

### 주요 테스트 스크립트
- `test_submit_tsp_full_flow.py`: 외판원 문제 전체 플로우 테스트
- `test_fibonacci_full_flow.py`: 피보나치 문제 전체 플로우 테스트
- `test_submit_only.py`: 코드 제출만 테스트
- `test_judge0_with_db_problem.py`: Judge0 직접 테스트
- `check_server.py`: 서버 상태 확인
- `check_judge0_connection.py`: Judge0 연결 확인

---

## 📊 데이터베이스 구조

### Redis 데이터 구조

| Key 패턴 | 타입 | TTL | 설명 |
|----------|------|-----|------|
| `graph_state:{session_id}` | JSON | 24h | LangGraph 상태 (messages, turn_scores 등) |
| `turn_logs:{session_id}:{turn}` | JSON | 24h | 턴별 평가 로그 (intent, rubrics, reasoning) |
| `turn_mapping:{session_id}` | JSON | 24h | 턴-메시지 인덱스 매핑 |

### PostgreSQL 테이블

핵심 테이블:
- **`prompt_sessions`**: 프롬프트 세션 정보 (세션 종료 처리 포함)
- **`prompt_messages`**: 대화 메시지 기록
- **`prompt_evaluations`**: 평가 결과 저장 (턴별 평가, Holistic 평가)
- **`submissions`**: 코드 제출 정보
- **`submission_runs`**: Judge0 실행 결과
- **`scores`**: 최종 평가 점수

**상세 가이드**: [DB 설정 가이드](./docs/DB_설정_가이드.md), [테이블명세서](./docs/테이블명세서.md)

---

## 🐳 Docker 배포

### 개발 환경
```bash
docker-compose -f docker-compose.dev.yml up -d
```

### 프로덕션 환경
```bash
# 이미지 빌드
docker build -t ai-vibe-worker:latest .

# 컨테이너 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f ai_worker
```

---

## 📚 문서

### 핵심 문서 (`docs/`)
- [문서 인덱스](./docs/문서_인덱스.md) — 전체 목차
- [API 전체 명세](./docs/API_전체_명세.md) · [API 현재 구현](./docs/API_현재_구현.md)
- [State 흐름 및 DB 저장](./docs/State_흐름_및_DB_저장.md) · [점수 계산 로직](./docs/점수_계산_로직.md)
- [Node4 평가 가이드](./docs/Node4_평가_가이드.md) · [Judge0 가이드](./docs/Judge0_가이드.md)
- [UV 설정 가이드](./docs/UV_설정_가이드.md) · [테스트 가이드](./docs/테스트_가이드.md)

### 운영·그래프 참고 (`.maestro/`)
- [LangGraph API·호출 맵](./.maestro/docs/LangGraph_API_Call_Map.md)
- [V2.1 변경 로그](./.maestro/docs/V2.1_Change_Log.md) · [DOCS_REFERENCE](./.maestro/DOCS_REFERENCE.md)

---

## 📚 기술 스택

### 백엔드
- **FastAPI** (0.109+): 비동기 웹 프레임워크
- **Python** (3.12): 프로그래밍 언어
- **uv**: 빠른 Python 패키지 관리자 (pip 대체)

### AI/LLM
- **LangGraph** (0.6+): AI 워크플로우 오케스트레이션
- **LangChain** (0.3+): LLM 통합 프레임워크
- **Gemini API**: Google의 생성형 AI 모델 (Google AI Studio)
- **Vertex AI**: GCP Vertex AI 지원 (ADC 인증)
- **LLM Factory Pattern**: 중앙화된 LLM 관리

### 데이터베이스
- **PostgreSQL** (14+): 영구 데이터 저장소 (Spring Boot와 공유)
- **Redis** (7+): 세션 및 상태 관리
- **SQLAlchemy** (2.0+): 비동기 ORM

### 코드 실행 및 평가
- **Judge0**: 코드 실행 및 테스트 케이스 평가 (RapidAPI 또는 로컬)
- **Judge0 Worker**: 비동기 코드 실행 처리

### 유틸리티
- **Pydantic** (2.0+): 데이터 검증
- **httpx**: 비동기 HTTP 클라이언트
- **websockets**: WebSocket 지원
- **uv**: Python 패키지 관리 (pip 대체, 10-100배 빠름)

---

## 📈 현재 상태 및 수정 사항

### ✅ 완료된 기능
- [x] LangGraph 메인 플로우 (채팅 루프 + 제출 후 N5→N9)
- [x] Eval Turn SubGraph (제출 시 턴별 동기 평가, V3 루브릭 R1~R4·의도 게이트)
- [x] 제출 파이프라인: Judge0(N5) → Radon/AST(N6) → 코드 리뷰 LLM(N7) → 다중 에이전트 토론(N8) → 집계(N9)
- [x] Redis 세션 상태 관리 (graph_state, turn_logs, turn_mapping, 선택적 debate 로그)
- [x] PostgreSQL 연동 (Spring Boot 공유 DB)
- [x] Gemini / Vertex AI (LLM Factory)
- [x] Judge0 연동 및 Worker
- [x] 가드레일 (직접 답·Jailbreak 등)
- [x] 최종 평가 가중치 **Prompt 40% / Correctness 40% / Performance 20%**
- [x] RESTful API 엔드포인트 (`/api/session/start`, `/api/session/{id}/messages`, `/api/session/{id}/submit`)
- [x] WebSocket 스트리밍 (LangGraph 기반 토큰 단위 스트리밍)
- [x] 메시지 저장 (PostgreSQL `prompt_messages`)
- [x] 평가 결과 저장 (PostgreSQL `prompt_evaluations`)
- [x] 세션 종료 처리 (`prompt_sessions.ended_at`)
- [x] Hybrid DDD 구조 마이그레이션
- [x] Docker 지원 (PostgreSQL, Redis, Worker)
- [x] 로깅 시스템

### 🔜 다음 단계 (우선순위 순)

#### P1 (높음)
- [ ] **Usage Callback 구현** - 토큰 사용량을 Spring Boot로 전송
- [ ] **Rate Limiter 구현** - API 호출 제한 관리
- [ ] **인증 시스템** - Authorization 토큰 기반 인증

#### P2 (중간)
- [ ] **Langsmith 추적 활성화** - LLM 호출 추적 및 디버깅
- [ ] **성능 최적화** - LLM 호출 최소화, 캐싱 전략
- [ ] **테스트 케이스 확장** - 다중 테스트 케이스 지원

#### P3 (낮음)
- [ ] **보안 강화** - API 키 관리, 입력 검증
- [ ] **테스트 커버리지 확대** - 80% 이상 목표
- [ ] **개발자 가이드 작성** - 노드 추가 방법, 커스터마이징 가이드

---

## 📝 변경 이력

### 2026-04 — 평가 파이프라인 개편 (현재 브랜치 기준)

- 제출 후 **통합 평가 노드 선행 → Holistic 단일 플로우** 순서를 **Judge0 → 정적 분석 → 코드 에이전트 → 토론 → 최종 집계**로 재구성.
- 턴 평가 **V3 루브릭(R1~R4)** 및 N8 **다중 에이전트 토론**(`subgraph_debate.py`, `debate_agents.yaml`) 도입.
- 최종 가중치 **40 / 40 / 20** 및 Prompt 내부 블렌딩·R4 세션 보정은 `n9_final_scores.py` 기준.

### v0.6.0 (2025-12-06)
- **RESTful API 리팩토링**: 
  * `/api/session/start` - 세션 시작
  * `/api/session/{sessionId}/messages` - 메시지 전송
  * `/api/session/{sessionId}/submit` - 코드 제출
- **Judge0 연동 완료**: 코드 실행 및 테스트 케이스 평가
- **Judge0 Worker 구현**: 비동기 코드 실행 처리
- **Vertex AI 지원**: GCP Vertex AI 통합 (ADC 인증)
- **LLM Factory Pattern**: 중앙화된 LLM 관리
- **평가 결과 저장**: `prompt_evaluations` 테이블 추가
- **세션 종료 처리**: `prompt_sessions.ended_at` 설정
- **문서 통합**: API, DB, Test, Graph, Docker 가이드 통합

### v0.5.0 (2025-12-XX)
- **메시지 저장 구현**: PostgreSQL `prompt_messages` 저장
- **세션 관리 개선**: 세션 생성 및 관리 로직 개선

### v0.4.0 (2025-12-XX)
- **WebSocket 스트리밍 구현**: LangGraph 기반 실시간 토큰 스트리밍
- **Hybrid DDD 구조 마이그레이션**: 
  * `domain/` - 도메인 로직 (LangGraph)
  * `application/` - 애플리케이션 서비스
  * `infrastructure/` - 인프라 (DB, Redis, Repository)
  * `presentation/` - 프레젠테이션 (API, Schemas)
- **파일 구조 개선**: 명확한 계층 분리 및 협업을 위한 명명 규칙 적용
- **WebSocket 테스트 스크립트 추가**: `test_websocket_stream.py`, `test_websocket_simple.py`

### v0.3.0 (2025-11-28)
- **프로젝트 구조 재구성**: 루트 디렉토리 정리
- **README 추가**: 각 폴더에 README.md 추가로 사용 가이드 제공

### v0.2.0 (2025-11-27 - 오후)
- **평가 대상 재정의**: LLM 답변 평가 → 사용자 프롬프트 평가로 변경
- **8가지 의도 패턴**: SYSTEM_PROMPT 추가 (기존 7개 → 8개)
- **Claude Prompt Engineering 기준 적용**
- **Holistic Flow 평가 추가**

### v0.1.0 (2025-11-27 - 오전)
- 초기 버전 릴리스
- LangGraph 메인 플로우 구현
- Eval Turn SubGraph 구현
- Redis 세션 관리
- PostgreSQL 연동
- Gemini LLM 통합

---

## 🤝 기여 가이드

### 새 노드 추가하기

1. `app/domain/langgraph/nodes/` 에 새 파일 생성
2. 노드 함수 정의 (입력: `MainGraphState`, 출력: `Dict[str, Any]`)
3. `app/domain/langgraph/graph.py` 에 노드 등록
4. 엣지 연결

### 코드 스타일
- Black으로 포맷팅: `black app/`
- isort로 import 정리: `isort app/`
- Type hints 사용 권장

---

## 📞 문의 및 지원

프로젝트 관련 문의사항은 팀 채널을 통해 문의해주세요.

---

## 📄 라이선스

Private - 내부 사용 전용

---

**Made with 🤖 by AI Vibe Team**
