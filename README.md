# 🤖 AI Vibe Coding Test Worker

> LangGraph 기반 AI 코딩 테스트 평가 시스템 (FastAPI)

## 📋 프로젝트 개요

이 프로젝트는 **AI 바이브 코딩 테스트**를 위한 FastAPI 기반 AI 워커 서버입니다. 
Spring Boot 백엔드와 통합되어 동작하며, **LangGraph**를 사용하여 복잡한 AI 평가 플로우를 구현합니다.

### 핵심 기능
- 🎯 **실시간 프롬프트 평가**: 사용자의 각 프롬프트를 실시간으로 평가 (Claude Prompt Engineering 기준)
- 🔍 **의도 분석**: 8가지 코드 패턴(시스템 프롬프트, 규칙 설정, 생성, 최적화, 디버깅, 테스트 케이스, 힌트/질의, 후속 질문) 자동 분류
- 🛡️ **가드레일**: 부적절한 요청 차단 및 교육적 피드백 제공
- 📊 **종합 평가**: 프롬프트 활용(25%), 성능(25%), 정확성(50%)을 종합한 최종 점수 산출
- 🔄 **비동기 처리**: 백그라운드 평가로 응답 지연 최소화
- 🔗 **Chaining 분석**: 문제 분해, 피드백 수용성, 주도성, 전략적 탐색 평가
- 🌐 **WebSocket 스트리밍**: 실시간 토큰 단위 응답 스트리밍 지원

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
│  │  4. Eval Turn Guard (제출 시 평가 완료 대기)               │  │
│  │  5. Main Router (제출 여부 확인)                           │  │
│  │  6a-6d. 평가 노드들 (순차 실행: 6a→6b→6c→6d)              │  │
│  │  7. Final Score Aggregation (최종 점수)                   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              Eval Turn SubGraph (실시간 평가)               │  │
│  │  4.0 Intent Analysis (의도 분석)                           │  │
│  │  4.R/G/O/D/T/H/F (의도별 평가 노드)                        │  │
│  │  4.X Answer Summary (답변 요약)                            │  │
│  │  4.4 Turn Log Aggregation (턴 로그 집계)                   │  │
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
│  6a. Eval Holistic Flow                │
│  - Chaining 전략 평가                  │
│  - 문제 분해, 피드백 수용성             │
│  - 주도성, 전략적 탐색                  │
└────────────────────────────────────────┘
  │
  ▼
┌────────────────────────────────────────┐
│  6b. Aggregate Turn Scores             │
│  - 모든 턴 점수 집계 및 평균            │
└────────────────────────────────────────┘
  │
  ▼
┌────────────────────────────────────────┐
│  6c. Eval Code Execution                │
│  - Judge0로 코드 실행 및 평가           │
│  - 성능 평가 (실행 시간, 메모리)        │
│  - 정확성 평가 (테스트 케이스 통과율)    │
└────────────────────────────────────────┘
  │
  ▼
┌────────────────────────────────────────┐
│  7. Aggregate Final Scores              │
│  - 가중 평균 계산:                      │
│    • 프롬프트 활용: 25%                 │
│    • 성능: 25%                          │
│    • 정확성: 50%                        │
│  - 등급 산출 (A/B/C/D/F)               │
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
        │  4.0 Intent Analysis                   │
        │  - 사용자 프롬프트 의도 분석            │
        │  - 8가지 패턴 분류 (복수 선택 가능)     │
        │  - 신뢰도 점수 산출                    │
        └────────────────────────────────────────┘
                             │
        ┌────────────────────┼──────────────────────────┐
        │                    │                          │
        ▼                    ▼                          ▼
   ┌─────────┐        ┌──────────┐         ┌──────────────────┐
   │  4.SP   │        │   4.R    │   ...   │      4.F         │
   │시스템    │        │ 규칙설정  │         │   후속질문        │
   │프롬프트  │        │          │         │                  │
   └─────────┘        └──────────┘         └──────────────────┘
        │                    │                          │
        │  각 노드는 Claude Prompt Engineering 기준으로   │
        │  사용자 프롬프트의 품질을 평가 (0-100점)        │
        │  - 명확성 (Clarity)                           │
        │  - 예시 사용 (Examples)                       │
        │  - 규칙 명시 (Rules)                          │
        │  - 사고 연쇄 유도 (Chain of Thought)          │
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

### 8가지 코드 의도 패턴

**평가 대상**: 사용자가 작성한 프롬프트 (Claude Prompt Engineering 기준)

| 노드 | 패턴 | 설명 | 평가 항목 (예시) |
|------|------|------|-----------------|
| **4.SP** | **SYSTEM_PROMPT** | 시스템 프롬프트 설정, 역할(Persona) 부여 | AI에게 구체적인 역할과 답변 스타일을 정의했는가? |
| **4.R** | **RULE_SETTING** | 규칙/제약 조건 설정 | 제약 조건을 XML 태그나 리스트로 명시했는가? |
| **4.G** | **GENERATION** | 코드 생성 요청 | 입출력 예시(I/O Examples)를 제공했는가? |
| **4.O** | **OPTIMIZATION** | 성능 최적화 요청 | 목표 성능(O(n) 등)이나 최적화 전략을 제시했는가? |
| **4.D** | **DEBUGGING** | 오류 수정, 디버깅 | 에러 메시지, 재현 단계를 구체적으로 설명했는가? |
| **4.T** | **TEST_CASE** | 테스트 케이스 요청 | 엣지 케이스(Edge Cases)나 경계 조건을 명시했는가? |
| **4.H** | **HINT_OR_QUERY** | 힌트 요청, 질문 | 자신의 사고 과정(Chain of Thought)을 공유했는가? |
| **4.F** | **FOLLOW_UP** | 후속 질문, 추가 요청 | 이전 턴의 AI 답변을 기반으로 논리적으로 연결했는가? |

**특징**:
- 복수 의도 가능 (한 프롬프트에 여러 패턴 동시 평가)
- 병렬 실행 (LangGraph가 자동으로 관련 노드 동시 실행)
- AI 답변은 참고용, 평가는 오직 사용자 프롬프트에 집중

---

## 📁 프로젝트 구조 (Hybrid DDD)

프로젝트는 **Hybrid DDD (Domain-Driven Design)** 구조를 따릅니다. 
완전한 DDD보다는 실용적인 접근으로, 명확한 계층 분리와 협업을 위한 명명 규칙을 적용했습니다.

```
ai_vibe_worker/
├── app/                                    # 메인 애플리케이션
│   ├── __init__.py
│   ├── main.py                             # FastAPI 앱 진입점
│   │
│   ├── core/                               # 핵심 설정
│   │   ├── config.py                       # 환경 변수 관리
│   │   └── security.py                     # 보안 (향후 구현)
│   │
│   ├── domain/                             # 도메인 로직 (비즈니스 규칙)
│   │   └── langgraph/                      # LangGraph 정의
│   │       ├── graph.py                     # 메인 그래프
│   │       ├── subgraph_eval_turn.py       # 턴 평가 서브그래프
│   │       ├── states.py                    # 상태 타입 정의
│   │       └── nodes/                       # 그래프 노드 구현
│   │           ├── handle_request.py        # 1. 요청 처리
│   │           ├── intent_analyzer.py       # 2. 의도 분석 (가드레일)
│   │           ├── writer.py                # 3. AI 답변 생성 (Socratic)
│   │           ├── writer_router.py          # 3.5 & 5. 라우터
│   │           ├── eval_turn_guard.py       # 4. 제출 가드 (턴 평가 대기)
│   │           ├── system_nodes.py          # 시스템 노드 (failure, summary)
│   │           ├── turn_evaluator/          # 턴별 프롬프트 평가
│   │           │   ├── analysis.py          # 4.0 의도 분석
│   │           │   ├── evaluators.py        # 4.SP~4.F 평가 노드
│   │           │   ├── routers.py           # Intent Router
│   │           │   ├── summary.py           # Answer Summary
│   │           │   ├── aggregation.py       # Turn Log 집계
│   │           │   └── utils.py             # 공통 함수
│   │           └── holistic_evaluator/      # 전체 평가 (제출 시)
│   │               ├── flow.py              # 6a. Holistic Flow (Chaining)
│   │               ├── scores.py             # 6b, 7. 점수 집계
│   │               ├── performance.py        # 6c. 성능 평가
│   │               ├── correctness.py       # 6d. 정확성 평가
│   │               └── utils.py             # 공통 함수
│   │
│   ├── application/                        # 애플리케이션 서비스 (유스케이스)
│   │   └── services/
│   │       ├── eval_service.py             # 평가 서비스 (LangGraph 실행)
│   │       └── callback_service.py         # Spring 콜백
│   │
│   ├── infrastructure/                     # 인프라스트럭처 (외부 시스템)
│   │   ├── cache/                          # 캐시 계층
│   │   │   └── redis_client.py             # Redis 클라이언트
│   │   ├── persistence/                    # 영속성 계층
│   │   │   ├── session.py                  # PostgreSQL 세션
│   │   │   └── models/                     # SQLAlchemy 모델
│   │   │       ├── enums.py                 # Enum 정의
│   │   │       ├── exams.py                 # 시험 모델
│   │   │       ├── participants.py          # 참가자 모델
│   │   │       ├── problems.py              # 문제 모델
│   │   │       ├── sessions.py              # 세션 모델
│   │   │       └── submissions.py           # 제출 모델
│   │   └── repositories/                   # 데이터 접근 계층
│   │       ├── exam_repository.py
│   │       ├── session_repository.py
│   │       ├── state_repository.py         # Redis 상태 저장/로드
│   │       └── submission_repository.py
│   │
│   └── presentation/                       # 프레젠테이션 계층 (API)
│       ├── api/                            # API 라우터
│       │   └── routes/
│       │       ├── chat.py                  # 채팅/제출 API (REST + WebSocket)
│       │       ├── session.py               # 세션 관리 API
│       │       └── health.py                # 헬스 체크
│       └── schemas/                        # Pydantic 스키마
│           ├── chat.py                     # 채팅 요청/응답
│           ├── session.py                  # 세션 요청/응답
│           └── common.py                   # 공통 스키마
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
├── docs/                                   # 문서
│   ├── API_Specification.md                # API 명세서
│   ├── Endpoint_Change_History.md          # 엔드포인트 변경 이력
│   ├── Quick_DB_Guide.md                  # DB 빠른 가이드
│   ├── Database_Changes_Summary.md         # DB 변경사항 요약
│   ├── Test_Execution_Guide.md            # 테스트 실행 가이드
│   ├── State_Flow_and_DB_Storage.md       # LangGraph State 흐름 및 DB 저장
│   ├── Docker_PostgreSQL_Setup_Guide.md   # Docker 설정 가이드
│   ├── Judge0_Complete_Guide.md           # Judge0 완전 가이드
│   ├── Vertex_AI_Setup_Guide.md           # Vertex AI 설정 가이드
│   └── archive/                            # 아카이브 문서
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

- **`domain/`**: 비즈니스 로직의 핵심. LangGraph 노드와 상태 정의
- **`application/`**: 유스케이스 구현. 도메인 로직을 조합하여 비즈니스 기능 제공
- **`infrastructure/`**: 외부 시스템 연동 (DB, Redis, 외부 API)
- **`presentation/`**: API 엔드포인트와 요청/응답 스키마
- **`core/`**: 공통 설정 및 유틸리티

---

## 🚀 시작하기

### 사전 요구사항
- Python 3.10 이상 (`.python-version` 파일에 지정됨)
- Docker & Docker Compose
- Gemini API 키
- **uv** (권장) - 빠른 Python 패키지 관리자

### 1. 환경 설정

```bash
# 저장소 클론
git clone <repository-url>
cd LangGraph_1

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
# 1. Python 3.10 설치 (.python-version 파일 기반)
uv python install 3.10

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
uv python install 3.10      # Python 3.10 설치
uv python list             # 설치된 Python 버전 목록
uv python pin 3.10         # 프로젝트 Python 버전 고정

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
uv venv --python 3.10       # 특정 Python 버전으로 가상 환경 생성
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

**상세 API 명세**: [API_Specification.md](./docs/API_Specification.md)

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

---

## 🏆 평가 시스템

### 최종 점수 구성

| 항목 | 가중치 | 설명 | 평가 방법 |
|------|--------|------|-----------|
| **프롬프트 활용** | 25% | 턴별 프롬프트 품질 + Chaining 전략 | LLM 평가 |
| **성능** | 25% | 실행 시간 및 메모리 사용량 | Judge0 |
| **정확성** | 50% | 테스트 케이스 통과율 | Judge0 |

### 등급 기준
- **A**: 90점 이상
- **B**: 80-89점
- **C**: 70-79점
- **D**: 60-69점
- **F**: 60점 미만

### 프롬프트 평가 기준 (Claude Prompt Engineering 기반)

**⚠️ 중요**: 평가 대상은 **사용자가 작성한 프롬프트**입니다 (AI 답변 X)

#### 기본 평가 기준

각 턴의 사용자 프롬프트를 다음 4가지 기준으로 평가합니다:

1. **명확성 (Clarity)**
   - 요청이 모호하지 않고 구체적인가?
   - 직접적이고 명확하게 의도를 전달하는가?

2. **예시 사용 (Examples)**
   - 원하는 입출력 예시나 상황을 제공했는가?
   - Few-shot 또는 Multi-shot 방식을 활용했는가?

3. **규칙 및 제약조건 (Rules)**
   - 명확한 제약 조건이나 규칙을 제시했는가?
   - XML 태그, 리스트 등으로 구조화했는가?

4. **문맥 및 사고 연쇄 (Context & Chain of Thought)**
   - 이전 대화나 배경 지식을 적절히 활용했는가?
   - 단계적 접근을 요청하거나 자신의 사고 과정을 공유했는가?

#### Chaining 평가 (Holistic Flow)

제출 시 전체 대화를 종합하여 다음을 평가합니다:

1. **문제 분해 (Problem Decomposition)**
2. **피드백 수용성 (Feedback Integration)**
3. **주도성 (Proactiveness)**
4. **전략적 탐색 (Strategic Exploration)**

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
- **`docs/Test_Execution_Guide.md`**: 테스트 실행 가이드

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

**상세 가이드**: [Quick_DB_Guide.md](./docs/Quick_DB_Guide.md), [Database_Changes_Summary.md](./docs/Database_Changes_Summary.md)

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

### 핵심 문서
- [uv 환경 설정 가이드](./docs/UV_Setup_Guide.md) - uv 설치 및 사용법 (권장)
- [API 명세서](./docs/API_Specification.md) - REST API 상세 명세
- [DB 가이드](./docs/Quick_DB_Guide.md) - 데이터베이스 사용 가이드
- [테스트 가이드](./docs/Test_Execution_Guide.md) - 테스트 실행 방법
- [Judge0 가이드](./docs/Judge0_Complete_Guide.md) - Judge0 설정 및 사용
- [Vertex AI 가이드](./docs/Vertex_AI_Setup_Guide.md) - Vertex AI 설정

### 추가 문서
- [엔드포인트 변경 이력](./docs/Endpoint_Change_History.md)
- [DB 변경사항](./docs/Database_Changes_Summary.md)
- [LangGraph State 흐름](./docs/State_Flow_and_DB_Storage.md)
- [Docker 설정](./docs/Docker_PostgreSQL_Setup_Guide.md)

---

## 📚 기술 스택

### 백엔드
- **FastAPI** (0.109+): 비동기 웹 프레임워크
- **Python** (3.10+): 프로그래밍 언어
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
- [x] LangGraph 메인 플로우 구현
- [x] Eval Turn SubGraph (8가지 의도별 사용자 프롬프트 평가)
- [x] Redis 세션 상태 관리 (graph_state, turn_logs, turn_mapping)
- [x] PostgreSQL 연동 (Spring Boot 공유 DB)
- [x] Gemini LLM 통합 (Gemini 2.0 Flash)
- [x] Vertex AI 지원 (GCP Vertex AI, ADC 인증)
- [x] LLM Factory Pattern (중앙화된 LLM 관리)
- [x] Judge0 연동 (코드 실행 및 테스트 케이스 평가)
- [x] Judge0 Worker (비동기 코드 실행 처리)
- [x] 가드레일 시스템 (직접 답 요청 차단, Jailbreak 방지)
- [x] 실시간 프롬프트 평가 (Claude Prompt Engineering 기준)
- [x] 제출 시 Eval Turn Guard (누락 턴 재평가 + 대기 메커니즘)
- [x] Holistic Flow 평가 (Chaining 전략, 고급 프롬프트 기법)
- [x] 최종 평가 시스템 (프롬프트 25%, 성능 25%, 정확성 50%)
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
