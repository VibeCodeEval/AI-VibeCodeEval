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

---

## 🏗️ 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                        Spring Boot Backend                       │
│                   (메인 API, 사용자 관리, 문제 관리)                │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP API
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
│  │  6a-6d. 평가 노드들 (병렬 평가)                            │  │
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
        │    • 제출 의도 감지                    │
        │  - 출력: PASSED_*/FAILED_*             │
        └────────────────────────────────────────┘
                    │          │         │
        ┌───────────┘          │         └─────────────┐
        │                      │                       │
   PASSED_HINT          PASSED_SUBMIT           FAILED_*
        │                      │                       │
        ▼                      │                       ▼
┌────────────────┐             │            ┌──────────────────┐
│ 3. Writer LLM  │             │            │ Handle Failure   │
│ - Socratic AI  │             │            │ - 교육적 피드백   │
│ - 힌트 제공    │             │            └──────────────────┘
│ - 코드 불포함  │             │
└────────────────┘             │
        │                      │
        │ (백그라운드)           │
        ▼                      ▼
 ┌──────────────┐     ┌──────────────────────┐
 │ 4. Eval Turn │     │ 4. Eval Turn Guard   │
 │  SubGraph    │     │ - 모든 턴 평가 대기   │
 │ (비동기 실행) │     │ - 누락 턴 재평가      │
 └──────────────┘     └──────────────────────┘
        │                      │
        └──────────┬───────────┘
  ▼
        ┌────────────────────────────────────────┐
        │  5. Main Router (조건부 분기)          │
        │  - is_submitted == True?               │
        └────────────────────────────────────────┘
                   │          │
          제출 완료 │          │ 대화 계속
                   ▼          └──▶ END
        ┌──────────────────────────────────────┐
        │  6a. Eval Holistic Flow              │
        │  - Chaining 전략 평가                │
        │  - 문제 분해, 피드백 수용성           │
        │  - 주도성, 전략적 탐색                │
        └──────────────────────────────────────┘
                   │
                   ▼
        ┌──────────────────────────────────────┐
        │  6b. Aggregate Turn Scores           │
        │  - 모든 턴 점수 집계 및 평균          │
        └──────────────────────────────────────┘
                   │
                   ▼
        ┌──────────────────────────────────────┐
        │  6c. Eval Code Performance           │
        │  - 시간 복잡도, 공간 복잡도           │
        │  - (현재: LLM Mock, 향후: Judge0)    │
        └──────────────────────────────────────┘
                   │
                   ▼
        ┌──────────────────────────────────────┐
        │  6d. Eval Code Correctness           │
        │  - 테스트 케이스 통과율               │
        │  - (현재: LLM Mock, 향후: Judge0)    │
        └──────────────────────────────────────┘
  │
  ▼
        ┌──────────────────────────────────────┐
        │  7. Aggregate Final Scores           │
        │  - 가중 평균 계산:                    │
        │    • 프롬프트 활용: 25%               │
        │    • 성능: 25%                        │
        │    • 정확성: 50%                      │
        │  - 등급 산출 (A/B/C/D/F)             │
        └──────────────────────────────────────┘
  │
  ▼
 END
```

### Eval Turn SubGraph (실시간 프롬프트 평가)

**⚠️ 중요**: 이 서브그래프는 **사용자 프롬프트**를 평가합니다 (LLM 답변이 아님)

```
                    4. Eval Turn SubGraph
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

## 📁 프로젝트 구조

```
ai_vibe_worker/
├── app/                                 # 메인 애플리케이션
│   ├── __init__.py
│   ├── main.py                          # FastAPI 앱 진입점
│   │
│   ├── api/                             # API 라우터
│   │   └── routes/
│   │       ├── chat.py                  # 채팅/제출 API
│   │       ├── session.py               # 세션 관리 API
│   │       └── health.py                # 헬스 체크
│   │
│   ├── core/                            # 핵심 설정
│   │   ├── config.py                    # 환경 변수 관리
│   │   └── security.py                  # 보안 (향후 구현)
│   │
│   ├── db/                              # 데이터베이스
│   │   ├── session.py                   # PostgreSQL 세션
│   │   ├── redis_client.py              # Redis 클라이언트
│   │   ├── models/                      # SQLAlchemy 모델
│   │   │   ├── enums.py                 # Enum 정의
│   │   │   ├── exams.py                 # 시험 모델
│   │   │   ├── participants.py          # 참가자 모델
│   │   │   ├── problems.py              # 문제 모델
│   │   │   ├── sessions.py              # 세션 모델
│   │   │   └── submissions.py           # 제출 모델
│   │   └── repositories/                # 데이터 접근 계층
│   │       ├── exam_repo.py
│   │       ├── session_repo.py
│   │       ├── state_repo.py            # Redis 상태 저장/로드
│   │       └── submission_repo.py
│   │
│   ├── langgraph/                       # LangGraph 정의
│   │   ├── graph.py                     # 메인 그래프
│   │   ├── subgraph_eval_turn.py        # 턴 평가 서브그래프
│   │   ├── states.py                    # 상태 타입 정의
│   │   └── nodes/                       # 그래프 노드 구현
│   │       ├── handle_request.py        # 1. 요청 처리
│   │       ├── intent_analyzer.py       # 2. 의도 분석 (가드레일)
│   │       ├── writer.py                # 3. AI 답변 생성 (Socratic)
│   │       ├── writer_router.py         # 3.5 & 5. 라우터
│   │       ├── eval_turn_guard.py       # 4. 제출 가드 (턴 평가 대기)
│   │       ├── system_nodes.py          # 시스템 노드 (failure, summary)
│   │       ├── turn_evaluator/          # 턴별 프롬프트 평가
│   │       │   ├── analysis.py          # 4.0 의도 분석
│   │       │   ├── evaluators.py        # 4.SP~4.F 평가 노드
│   │       │   ├── routers.py           # Intent Router
│   │       │   ├── summary.py           # Answer Summary
│   │       │   ├── aggregation.py       # Turn Log 집계
│   │       │   └── utils.py             # 공통 함수
│   │       └── holistic_evaluator/      # 전체 평가 (제출 시)
│   │           ├── flow.py              # 6a. Holistic Flow (Chaining)
│   │           ├── scores.py            # 6b, 7. 점수 집계
│   │           ├── performance.py       # 6c. 성능 평가
│   │           ├── correctness.py       # 6d. 정확성 평가
│   │           └── utils.py             # 공통 함수
│   │
│   ├── services/                        # 비즈니스 로직
│   │   ├── eval_service.py              # 평가 서비스 (LangGraph 실행)
│   │   └── callback_service.py          # Spring 콜백
│   │
│   └── schemas/                         # Pydantic 스키마
│       ├── chat.py                      # 채팅 요청/응답
│       ├── session.py                   # 세션 요청/응답
│       └── common.py                    # 공통 스키마
│
├── scripts/                             # 개발 스크립트
│   ├── init-db.sql                      # DB 초기화 스크립트
│   └── run_dev.py                       # 개발 서버 실행
│
├── tests/                               # 단위 테스트
│   ├── conftest.py                      # pytest 설정
│   └── test_api.py                      # API 테스트
│
├── test_scripts/                        # 통합 테스트 스크립트
│   ├── README.md                        # 테스트 가이드
│   ├── test_collect_turns.py           # Phase 1: Turn 수집
│   ├── test_submit_from_saved.py       # Phase 2: 제출
│   ├── list_saved_sessions.py          # 세션 관리
│   ├── test_chat_flow.py               # 전체 플로우 테스트
│   └── test_gemini.py                   # Gemini API 연결 테스트
│
├── docs/                                # 문서
│   ├── README.md                        # 문서 가이드
│   ├── Test_Guide.txt                   # 테스트 및 디버깅 가이드
│   ├── Change_11_27_graph.txt           # 그래프 변경 이력
│   ├── Timing_Issue_Analysis.md         # 타이밍 이슈 분석
│   └── main_example.py                  # LangGraph 학습 예제
│
├── data/                                # 테스트 데이터
│   └── turn_sessions.json               # 저장된 세션 ID
│
├── docker-compose.yml                   # 프로덕션 Docker 구성
├── docker-compose.dev.yml               # 개발 Docker 구성
├── Dockerfile
├── pyproject.toml                       # 프로젝트 메타데이터
├── requirements.txt                     # Python 의존성
└── README.md                            # 메인 문서
```

---

## 🚀 시작하기

### 사전 요구사항
- Python 3.10 이상
- Docker & Docker Compose
- Gemini API 키

### 1. 환경 설정

```bash
# 저장소 클론
git clone <repository-url>
cd ai_vibe_worker

# 환경 변수 파일 생성
cp env.example .env

# .env 파일 수정 (API 키 등 설정)
GEMINI_API_KEY=your_gemini_api_key_here
POSTGRES_HOST=localhost
REDIS_HOST=localhost
```

### 2. 로컬 개발 (권장)

**2.1 Docker로 DB만 실행**
```bash
# PostgreSQL & Redis 실행
docker-compose -f docker-compose.dev.yml up -d

# 실행 확인
docker ps
```

**2.2 Python 환경 설정**
```bash
# 가상환경 생성
python -m venv venv

# 가상환경 활성화
.\venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 의존성 설치
pip install -r requirements.txt

# 또는 uv 사용 (권장)
pip install uv
uv sync
```

**2.3 개발 서버 실행**
```bash
# 방법 1: 스크립트 사용 (권장)
python scripts/run_dev.py

# 방법 2: uvicorn 직접 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 방법 3: uv 사용
uv run scripts/run_dev.py
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
- `GET /health` - 헬스 체크 (DB, Redis 상태)

### 채팅 API
- `POST /api/chat/message` - 메시지 전송
  ```json
  {
    "session_id": "session-123",
    "exam_id": 1,
    "participant_id": 100,
    "spec_id": 10,
    "message": "피보나치 수열을 계산하는 함수를 작성해주세요."
  }
  ```

- `POST /api/chat/submit` - 코드 제출
  ```json
  {
    "session_id": "session-123",
    "exam_id": 1,
    "participant_id": 100,
    "spec_id": 10,
    "code": "def fibonacci(n): ...",
    "lang": "python"
  }
  ```

### 세션 API
- `GET /api/session/{session_id}/state` - 세션 상태 조회
- `GET /api/session/{session_id}/scores` - 점수 조회
- `GET /api/session/{session_id}/history` - 대화 히스토리
- `DELETE /api/session/{session_id}` - 세션 삭제

### API 문서
서버 실행 후 자동 생성된 문서 확인:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

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
| `SPRING_CALLBACK_URL` | Spring 콜백 URL | `http://localhost:8080/api/ai/callback` | ✅ |

---

## 📊 데이터베이스 구조 (ERD)

### 테이블 관계도

```
┌────────────────────────────────────────────────────────────────────────┐
│                           시험 관리 영역                                │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  exams ────┬──── exam_participants ──── participants                  │
│            │                                                           │
│            ├──── exam_statistics                                      │
│            │                                                           │
│            └──── problem_specs ──── problems                          │
│                       │                                                │
└───────────────────────┼────────────────────────────────────────────────┘
                        │
┌───────────────────────┼────────────────────────────────────────────────┐
│                       │         세션 관리 영역                         │
├───────────────────────┼────────────────────────────────────────────────┤
│                       │                                                │
│                prompt_sessions ────┬──── prompt_messages              │
│                       │            │                                   │
│                       │            └──── submissions                   │
│                       │                       │                        │
│                       │                       ├──── submission_runs    │
│                       │                       │                        │
│                       │                       └──── scores             │
│                       │                                                │
└───────────────────────┼────────────────────────────────────────────────┘
                        │
┌───────────────────────┼────────────────────────────────────────────────┐
│                       │        문제 관리 영역                          │
├───────────────────────┼────────────────────────────────────────────────┤
│                       │                                                │
│                problem_sets ──── problem_set_items                    │
│                       │                                                │
│                entry_codes                                            │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### 핵심 테이블 상세

#### 1️⃣ **prompt_sessions** - 프롬프트 세션

사용자의 코딩 테스트 세션 정보를 추적합니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | BigInteger | Primary Key (자동 증가) |
| `exam_id` | BigInteger | 시험 ID (FK → exams) |
| `participant_id` | BigInteger | 참가자 ID (FK → participants) |
| `spec_id` | BigInteger | 문제 스펙 ID (FK → problem_specs) |
| `started_at` | DateTime | 세션 시작 시간 |
| `ended_at` | DateTime | 세션 종료 시간 (NULL = 진행 중) |
| `total_tokens` | Integer | 총 사용 토큰 수 |

**현재 구현 상태:**
- ✅ Model 정의 완료 (`app/db/models/sessions.py`)
- ✅ Repository 구현 완료 (`SessionRepository`)
- ⏳ API 연동 대기 (향후 `submit_code()` 시 저장)

**Redis와의 관계:**
- **Redis**: `graph_state:{session_id}` - 실시간 상태 (임시)
- **PostgreSQL**: `prompt_sessions` - 영구 기록

**생명주기:**
1. 세션 시작: PostgreSQL에 레코드 생성 (`started_at` 기록)
2. 대화 진행: Redis에서 실시간 상태 관리
3. 제출 완료: PostgreSQL 업데이트 (`ended_at`, `total_tokens`)

---

#### 2️⃣ **prompt_messages** - 대화 메시지

사용자와 AI의 모든 대화를 턴별로 기록합니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | BigInteger | Primary Key |
| `session_id` | BigInteger | 세션 ID (FK → prompt_sessions) |
| `turn` | Integer | 턴 번호 (1, 2, 3...) |
| `role` | Enum | `USER` / `ASSISTANT` / `SYSTEM` |
| `content` | Text | 메시지 내용 |
| `token_count` | Integer | 토큰 사용량 |
| `meta` | JSONB | 메타데이터 (intent_type, guardrail 등) |
| `created_at` | DateTime | 생성 시간 |

**현재 구현 상태:**
- ✅ Model 정의 완료 (`app/db/models/sessions.py`)
- ✅ Repository 구현 완료 (`SessionRepository` - 메시지 조회 포함)
- ⏳ API 연동 대기 (메시지 저장 메서드 추가 필요)

**Redis와의 관계:**
- **Redis**: `turn_logs:{session_id}:{turn}` - 평가 결과 포함 (임시)
- **PostgreSQL**: `prompt_messages` - 순수 메시지 기록 (영구)

**메시지 저장 구조:**
```json
// Turn 1
{"turn": 1, "role": "USER", "content": "두 수의 합을 구하는 함수를 만들어줘"}
{"turn": 1, "role": "ASSISTANT", "content": "좋습니다. 먼저..."}

// Turn 2
{"turn": 2, "role": "USER", "content": "시간 복잡도를 O(1)로 개선하려면?"}
{"turn": 2, "role": "ASSISTANT", "content": "좋은 질문입니다..."}
```

**meta 필드 활용 예시:**
```json
{
  "intent_type": "OPTIMIZATION",
  "is_guardrail_failed": false,
  "llm_model": "gemini-2.0-flash-exp",
  "timestamp": "2025-11-27T10:30:45Z"
}
```

---

#### 3️⃣ **submissions** - 코드 제출

참가자의 최종 코드 제출 정보를 저장합니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | UUID | Primary Key |
| `exam_id` | BigInteger | 시험 ID (FK → exams) |
| `participant_id` | BigInteger | 참가자 ID (FK → participants) |
| `spec_id` | BigInteger | 문제 스펙 ID (FK → problem_specs) |
| `lang` | String | 프로그래밍 언어 (python, javascript 등) |
| `status` | Enum | `PENDING` / `EVALUATING` / `COMPLETED` / `ERROR` |
| `code_inline` | Text | 제출 코드 전문 |
| `code_sha256` | String | 코드 해시 (중복 검증) |
| `code_bytes` | Integer | 코드 바이트 크기 |
| `code_loc` | Integer | 코드 줄 수 (Lines of Code) |
| `created_at` | DateTime | 제출 시간 |
| `updated_at` | DateTime | 최종 업데이트 시간 |

**현재 구현 상태:**
- ✅ Model 정의 완료 (`app/db/models/submissions.py`)
- ✅ Repository 구현 완료 (`SubmissionRepository`)
- ⏳ API 연동 대기 (`submit_code()` 시 저장 필요)

---

#### 4️⃣ **submission_runs** - 실행 결과

제출된 코드의 테스트 케이스별 실행 결과입니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | BigInteger | Primary Key |
| `submission_id` | UUID | 제출 ID (FK → submissions) |
| `case_index` | Integer | 테스트 케이스 인덱스 |
| `grp` | Enum | `SAMPLE` / `HIDDEN` (공개/비공개 케이스) |
| `verdict` | Enum | 결과 (ACCEPTED, WRONG_ANSWER, TLE 등) |
| `time_ms` | Integer | 실행 시간 (밀리초) |
| `mem_kb` | Integer | 메모리 사용량 (KB) |
| `stdout_bytes` | Integer | 표준 출력 크기 |
| `stderr_bytes` | Integer | 에러 출력 크기 |
| `created_at` | DateTime | 실행 시간 |

**Judge0 연동 계획:**
- 현재: LLM Mock으로 평가
- 향후: Judge0 API로 실제 코드 실행 및 채점

**Verdict 종류:**
- `ACCEPTED`: 정답
- `WRONG_ANSWER`: 오답
- `TIME_LIMIT_EXCEEDED`: 시간 초과
- `MEMORY_LIMIT_EXCEEDED`: 메모리 초과
- `RUNTIME_ERROR`: 런타임 에러
- `COMPILATION_ERROR`: 컴파일 에러
- `INTERNAL_ERROR`: 내부 에러

---

#### 5️⃣ **scores** - 평가 점수

최종 평가 점수를 저장합니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `submission_id` | UUID | Primary Key (FK → submissions) |
| `prompt_score` | Numeric(5,2) | 프롬프트 점수 (0~100) |
| `perf_score` | Numeric(5,2) | 성능 점수 (0~100) |
| `correctness_score` | Numeric(5,2) | 정확성 점수 (0~100) |
| `total_score` | Numeric(5,2) | 최종 점수 (0~100) |
| `rubric_json` | JSONB | 평가 루브릭 상세 |
| `created_at` | DateTime | 생성 시간 |

**현재 구현 상태:**
- ✅ Model 정의 완료 (`app/db/models/submissions.py`)
- ✅ Repository 구현 완료 (`SubmissionRepository.create_or_update_score()`)
- ⏳ API 연동 대기

**점수 계산 공식:**
```python
total_score = (
    prompt_score * 0.25 +
    perf_score * 0.25 +
    correctness_score * 0.50
)
```

**rubric_json 구조 예시:**
```json
{
  "prompt": {
    "turn_scores": {
      "1": 96.7,
      "2": 88.5,
      "3": 92.3
    },
    "holistic_flow": {
      "problem_decomposition": 95.0,
      "feedback_integration": 90.0,
      "proactiveness": 85.0,
      "strategic_exploration": 88.0
    }
  },
  "performance": {
    "time_complexity": "O(n log n)",
    "space_complexity": "O(n)",
    "score": 85.0
  },
  "correctness": {
    "total_cases": 10,
    "passed_cases": 9,
    "score": 90.0
  }
}
```

---

### Redis 데이터 구조

Redis는 실시간 처리를 위한 임시 저장소로 사용합니다.

| Key 패턴 | 타입 | TTL | 설명 |
|----------|------|-----|------|
| `graph_state:{session_id}` | JSON | 24h | LangGraph 상태 (messages, turn_scores 등) |
| `turn_logs:{session_id}:{turn}` | JSON | 24h | 턴별 평가 로그 (intent, rubrics, reasoning) |
| `turn_mapping:{session_id}` | JSON | 24h | 턴-메시지 인덱스 매핑 |

**데이터 흐름:**
```
1. 사용자 메시지 입력
   ↓
2. Redis에 graph_state 업데이트 (실시간)
   ↓
3. LangGraph 실행 (Intent Analyzer → Writer → 백그라운드 평가)
   ↓
4. Redis에 turn_logs 저장 (평가 결과)
   ↓
5. 제출 시 PostgreSQL 동기화 (SessionRepository, SubmissionRepository)
   ├─ prompt_sessions 업데이트 (세션 종료)
   ├─ prompt_messages 저장 (대화 기록)
   ├─ submissions 저장 (코드)
   ├─ submission_runs 저장 (실행 결과)
   └─ scores 저장 (최종 점수)
```

---

### 향후 개선 사항

#### Priority P1 (높음)
1. **`submit_code()` API에서 PostgreSQL 저장 구현**
   - `SessionRepository`에 세션 종료 및 메시지 저장 메서드 추가
   - `SubmissionRepository.create_submission()` 호출
   - `SubmissionRepository.create_or_update_score()` 호출

2. **Judge0 API 연동**
   - 실제 코드 실행 및 테스트
   - `submission_runs` 테이블에 결과 저장

3. **토큰 사용량 추적 개선**
   - 각 LLM 호출 시 `SessionRepository`에서 토큰 수 업데이트
   - `prompt_messages.token_count` 정확히 기록

#### Priority P2 (중간)
1. **세션 관리 API 추가**
   - `POST /api/session/start`: 세션 시작 (PostgreSQL 레코드 생성)
   - `GET /api/session/{session_id}/messages`: 메시지 기록 조회

2. **Redis ↔ PostgreSQL 동기화 보장**
   - 제출 시 Redis 데이터를 PostgreSQL로 완전 이관
   - 데이터 불일치 검증 로직 추가

3. **메시지 검색 기능**
   - `prompt_messages.fts` (Full-Text Search) 활용
   - 프롬프트 품질 분석 도구 구축

---

## 🏆 평가 시스템

### 최종 점수 구성

| 항목 | 가중치 | 설명 | 평가 방법 |
|------|--------|------|-----------|
| **프롬프트 활용** | 25% | 턴별 프롬프트 품질 + Chaining 전략 | LLM 평가 |
| **성능** | 25% | 시간/공간 복잡도 | Judge0 (예정) |
| **정확성** | 50% | 테스트 케이스 통과율 | Judge0 (예정) |

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
   - 예: "두 수의 합을 구하는 함수를 만들어줘" (명확) vs "뭔가 계산하는 거 만들어줘" (모호)

2. **예시 사용 (Examples)**
   - 원하는 입출력 예시나 상황을 제공했는가?
   - Few-shot 또는 Multi-shot 방식을 활용했는가?
   - 예: "입력: [1,2,3], 출력: 6" (좋음) vs 예시 없음 (보통)

3. **규칙 및 제약조건 (Rules)**
   - 명확한 제약 조건이나 규칙을 제시했는가?
   - XML 태그, 리스트 등으로 구조화했는가?
   - 예: "<constraint>시간 복잡도 O(n)</constraint>" (좋음)

4. **문맥 및 사고 연쇄 (Context & Chain of Thought)**
   - 이전 대화나 배경 지식을 적절히 활용했는가?
   - 단계적 접근을 요청하거나 자신의 사고 과정을 공유했는가?

#### 의도별 추가 평가 기준

각 의도 패턴마다 특화된 평가 기준이 추가로 적용됩니다:

- **SYSTEM_PROMPT**: Persona 정의, Scope 명시, Tone & Style 설정
- **RULE_SETTING**: 제약조건 명확성, XML 태그 활용
- **GENERATION**: I/O 예시 제공, 구현 조건 상세도
- **OPTIMIZATION**: 현재 병목 지적, 목표 성능 명시
- **DEBUGGING**: 에러 메시지, 재현 단계 구체성
- **TEST_CASE**: Edge Cases, Boundary Conditions 명시
- **HINT_OR_QUERY**: 사고 과정 공유, 막힌 부분 구체화
- **FOLLOW_UP**: 이전 턴 연결성, 논리적 전개

#### Chaining 평가 (Holistic Flow)

제출 시 전체 대화를 종합하여 다음을 평가합니다:

1. **문제 분해 (Problem Decomposition)**
   - 전체 문제를 작은 단위로 나누어 접근했는가?

2. **피드백 수용성 (Feedback Integration)**
   - 이전 턴의 AI 힌트를 다음 턴에 반영했는가?

3. **주도성 (Proactiveness)**
   - AI의 오류를 지적하고 능동적으로 개선 방향을 제시했는가?

4. **전략적 탐색 (Strategic Exploration)**
   - 의도가 HINT → OPTIMIZATION → TEST_CASE 등으로 전략적으로 변화했는가?

5. **고급 프롬프트 기법 (Advanced Techniques Bonus)**
   - SYSTEM_PROMPT 활용, XML 태그 사용, Few-shot 예시 제공
   - 이 항목들을 활용하면 **가산점**으로 90점 이상 고득점 가능

---

## 🧪 테스트

### 단위 테스트
```bash
# 전체 테스트 실행
pytest tests/ -v

# 커버리지 포함
pytest tests/ -v --cov=app --cov-report=html

# 특정 테스트만 실행
pytest tests/test_api.py::test_health_check -v
```

### 통합 테스트

프로젝트에는 두 가지 통합 테스트 전략이 제공됩니다:

**1. Phase 1-2 분리 테스트 (권장) ⭐**
```bash
# Phase 1: Turn 수집 (제출 안 함, API Quota 절약)
uv run python test_scripts/test_collect_turns.py

# Phase 2: 저장된 세션으로 제출
uv run python test_scripts/test_submit_from_saved.py

# 저장된 세션 목록 확인
uv run python test_scripts/list_saved_sessions.py
```

**장점**:
- Gemini API Quota 절약 (15 RPM 제한 회피)
- 각 단계별 독립적 디버깅
- Phase 1 실패 시 Phase 2 재실행 불필요

**2. 전체 플로우 테스트 (빠른 검증)**
```bash
# 3턴 대화 + 제출 + Redis 검증 (한 번에)
uv run python test_scripts/test_chat_flow.py

# Gemini API 연결 확인
uv run python test_scripts/test_gemini.py
```

### 테스트 가이드
- **`test_scripts/README.md`**: 테스트 스크립트 상세 가이드
- **`docs/Test_Guide.txt`**: 로그 확인 및 디버깅 가이드
  * 서버 로그 확인 방법
  * Docker 로그 확인 방법
  * Redis 데이터 확인 방법
  * PostgreSQL 데이터 확인 방법

---

## 📊 Redis 데이터 구조

### 1. Graph State
```
키: graph_state:{session_id}
TTL: 24시간
구조: {
  "session_id": "session-123",
  "current_turn": 3,
  "messages": [...],
  "is_submitted": false,
  "turn_scores": {},
  ...
}
```

### 2. Turn Logs (턴별 프롬프트 평가 로그)
```
키: turn_logs:{session_id}:{turn}
TTL: 24시간
구조: {
  "turn_number": 1,
  "user_prompt_summary": "사용자 프롬프트 요약 (10줄 이내)",
  "prompt_evaluation_details": {
    "intent": "GENERATION",  // 분류된 의도
    "score": 85.5,  // 프롬프트 점수 (0-100)
    "rubrics": [  // 평가 루브릭
      {
        "criterion": "명확성 (Clarity)",
        "score": 90,
        "reasoning": "요구사항이 명확히 제시됨"
      },
      ...
    ],
    "final_reasoning": "전체 평가 근거"
  },
  "llm_answer_summary": "AI 답변 요약",
  "llm_answer_reasoning": "AI의 추론 과정 (Chaining 평가용)"
}
```

**⚠️ 주의**: `prompt_evaluation_details`는 **사용자 프롬프트**를 평가한 결과입니다

### 3. Turn Mapping (메시지 인덱스 매핑)
```
키: turn_mapping:{session_id}
TTL: 24시간
구조: {
  "1": {"start_msg_idx": 0, "end_msg_idx": 1},
  "2": {"start_msg_idx": 2, "end_msg_idx": 3},
  ...
}
```

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

## 📚 기술 스택

### 백엔드
- **FastAPI** (0.109+): 비동기 웹 프레임워크
- **Python** (3.10+): 프로그래밍 언어

### AI/LLM
- **LangGraph** (0.6+): AI 워크플로우 오케스트레이션
- **LangChain** (0.3+): LLM 통합 프레임워크
- **Gemini API**: Google의 생성형 AI 모델

### 데이터베이스
- **PostgreSQL** (14+): 영구 데이터 저장소 (Spring Boot와 공유)
- **Redis** (7+): 세션 및 상태 관리
- **SQLAlchemy** (2.0+): 비동기 ORM

### 유틸리티
- **Pydantic** (2.0+): 데이터 검증
- **httpx**: 비동기 HTTP 클라이언트
- **tenacity**: 재시도 로직

---

## 📈 현재 상태 및 수정 사항

### ✅ 완료된 기능
- [x] LangGraph 메인 플로우 구현
- [x] Eval Turn SubGraph (8가지 의도별 사용자 프롬프트 평가)
- [x] Redis 세션 상태 관리 (graph_state, turn_logs, turn_mapping)
- [x] PostgreSQL 연동 (Spring Boot 공유 DB)
- [x] SessionRepository 구현 (세션 생성, 메시지 저장, 토큰 추적)
- [x] Gemini LLM 통합 (Gemini 2.0 Flash)
- [x] 가드레일 시스템 (직접 답 요청 차단, Jailbreak 방지)
- [x] 실시간 프롬프트 평가 (Claude Prompt Engineering 기준)
- [x] 제출 시 Eval Turn Guard (누락 턴 재평가 + 대기 메커니즘)
- [x] Holistic Flow 평가 (Chaining 전략, 고급 프롬프트 기법)
- [x] 최종 평가 시스템
- [x] API 엔드포인트 (채팅, 제출, 세션 관리)
- [x] Docker 지원
- [x] 로깅 시스템

### 🚧 알려진 이슈
1. **Turn 1 백그라운드 평가 누락**
   - 현상: Turn 1의 평가가 완료되지 않는 경우 발생
   - 원인: 서버 auto-reload 또는 LLM API 타이밍 이슈
   - 해결: `eval_turn_guard`에서 재평가로 보완됨

2. **API Rate Limit (15 RPM)**
   - 현상: 연속된 LLM 호출 시 429 에러
   - 대책: 턴 간 대기 시간 추가 (10초), 두 단계 테스트 전략

3. **aggregate_turn_scores 타입 불일치**
   - 현상: float vs dict 타입 충돌
   - 해결: float 타입도 지원하도록 수정 완료 (최신 커밋에 반영 예정)

### 🔜 다음 단계 (우선순위 순)

#### P1 (높음)
- [ ] **Judge0 API 연동** - 코드 성능/정확성 평가를 LLM Mock에서 실제 실행 환경으로 전환
- [ ] **Rate Limiter 구현** - API 호출 제한 관리
- [ ] **에러 처리 강화** - LLM API 실패 시 재시도 로직 개선
- [ ] **PostgreSQL ERD 문서화** - DB 스키마 문서 작성

#### P2 (중간)
- [ ] **Langsmith 추적 활성화** - LLM 호출 추적 및 디버깅
- [ ] **Redis 키 구조 표준화** - 일관된 TTL 정책 수립
- [ ] **API 응답 형식 표준화** - 에러 응답 구조 통일
- [ ] **성능 최적화** - LLM 호출 최소화, 캐싱 전략

#### P3 (낮음)
- [ ] **보안 강화** - API 키 관리, 입력 검증
- [ ] **테스트 커버리지 확대** - 80% 이상 목표
- [ ] **개발자 가이드 작성** - 노드 추가 방법, 커스터마이징 가이드
- [ ] **모니터링 대시보드** - 실시간 평가 현황 시각화

---

## 🤝 기여 가이드

### 새 노드 추가하기

1. `app/langgraph/nodes/` 에 새 파일 생성
2. 노드 함수 정의 (입력: `MainGraphState`, 출력: `Dict[str, Any]`)
3. `app/langgraph/graph.py` 에 노드 등록
4. 엣지 연결

예시:
```python
# app/langgraph/nodes/my_node.py
async def my_custom_node(state: MainGraphState) -> Dict[str, Any]:
    """내 커스텀 노드"""
    # 로직 구현
    return {
        "my_field": "value",
        "updated_at": datetime.utcnow().isoformat()
    }
```

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

## 📝 변경 이력

### v0.3.0 (2025-11-28)
- **프로젝트 구조 재구성**: 루트 디렉토리 정리
  * `test_scripts/` 폴더 생성: 통합 테스트 스크립트 통합
  * `docs/` 폴더 생성: 문서 및 예제 파일 통합
  * `data/` 폴더 생성: 테스트 데이터 분리
  * 불필요한 파일 삭제 (requirement.txt, fix_emoji.py, 중복 테스트 파일)
- **README 추가**: 각 폴더에 README.md 추가로 사용 가이드 제공
- **경로 수정**: 테스트 스크립트들이 `../data/` 폴더 참조하도록 업데이트

### v0.2.0 (2025-11-27 - 오후)
- **평가 대상 재정의**: LLM 답변 평가 → 사용자 프롬프트 평가로 변경
- **파일 구조 모듈화**: `evaluators.py` → `turn_evaluator/` + `holistic_evaluator/`로 분리
- **8가지 의도 패턴**: SYSTEM_PROMPT 추가 (기존 7개 → 8개)
- **Claude Prompt Engineering 기준 적용**: 명확성, 예시, 규칙, 사고 연쇄
- **Holistic Flow 평가 추가**: Chaining 전략, 고급 프롬프트 기법 가산점
- **SessionRepository 완성**: `create_session()`, `save_messages_batch()` 메서드 추가
- **상세 주석 추가**: 
  * README.md 전면 개편
  * SessionRepository 전체 메서드 주석
  * eval_service.py, graph.py, chat.py 주석 추가
- **ERD 문서화**: PostgreSQL 테이블 구조 및 Redis 관계 명시

### v0.1.0 (2025-11-27 - 오전)
- 초기 버전 릴리스
- LangGraph 메인 플로우 구현
- Eval Turn SubGraph 구현
- Redis 세션 관리
- PostgreSQL 연동
- Gemini LLM 통합
- 가드레일 시스템
- 최종 평가 시스템

---

**Made with 🤖 by AI Vibe Team**
