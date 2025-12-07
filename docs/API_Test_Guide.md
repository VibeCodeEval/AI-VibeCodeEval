# API 테스트 가이드

## 📋 개요

현재 최신 API (`POST /api/chat/messages`, `POST /api/session/submit`)를 테스트하기 위한 가이드입니다.

---

## 🗂️ 테스트 파일 구조

### 1. 데이터 준비 스크립트 (`test_scripts/`)

#### `setup_web_test_data.py`
**용도**: Chat API 테스트를 위한 기본 데이터 생성

**생성 데이터**:
- Exam (ID: 1)
- Participant (ID: 1)
- Problem (ID: 1)
- ProblemSpec (spec_id: 10)
- ExamParticipant (ID: 2, exam_id=1, participant_id=1)
- PromptSession (ID: 1)

**사용법**:
```bash
uv run python test_scripts/setup_web_test_data.py
```

**사용 시점**: Chat API 테스트 전에 한 번 실행

---

#### `setup_submit_test_data.py`
**용도**: Submit API 테스트를 위한 데이터 생성 (동적 ID 자동 생성)

**생성 데이터**:
- Exam, Participant, ExamParticipant (자동 증가 ID)
- PromptSession (자동 증가 ID)
- Submission (자동 증가 ID)
- Problem (ID: 1 - 외판원 순회)
- ProblemSpec (spec_id: 10)

**특징**:
- 기존 최대 ID를 조회하여 자동으로 증가된 ID 생성
- 생성된 ID는 `test_ids.json`에 저장됨

**사용법**:
```bash
uv run python test_scripts/setup_submit_test_data.py
```

**사용 시점**: Submit API 테스트 전에 실행

---

### 2. API 테스트 스크립트 (루트 디렉토리)

#### `test_single_turn_submit.py`
**용도**: 단일 Turn 제출 테스트 (Chat 1턴 + Submit)

**테스트 흐름**:
1. Chat API로 1턴 대화 생성
2. Submit API로 코드 제출
3. 평가 결과 확인

**사용법**:
```bash
# 1. 테스트 데이터 준비
uv run python test_scripts/setup_submit_test_data.py

# 2. 서버 실행 (별도 터미널)
uv run scripts/run_dev.py

# 3. 테스트 실행
uv run python test_single_turn_submit.py
```

**필요 파일**: `test_ids.json` (자동 생성됨)

---

#### `test_submit_tsp.py`
**용도**: 외판원 문제(TSP) 제출 테스트

**사용법**:
```bash
# 1. 테스트 데이터 준비
uv run python test_scripts/setup_submit_test_data.py

# 2. 서버 실행 (별도 터미널)
uv run scripts/run_dev.py

# 3. 테스트 실행
uv run python test_submit_tsp.py
```

---

#### `test_full_flow_tsp.py`
**용도**: 외판원 문제 전체 Flow 테스트 (여러 턴 대화 + 제출)

**테스트 흐름**:
1. Chat API로 여러 턴 대화 생성
2. Submit API로 코드 제출
3. 평가 결과 확인

**사용법**:
```bash
# 1. 테스트 데이터 준비
uv run python test_scripts/setup_submit_test_data.py

# 2. 서버 실행 (별도 터미널)
uv run scripts/run_dev.py

# 3. 테스트 실행
uv run python test_full_flow_tsp.py
```

---

### 3. pytest 기반 테스트 (`tests/`)

#### `test_chat_api_new.py`
**용도**: 신규 Chat API (`POST /api/chat/messages`) 단위 테스트

**테스트 항목**:
- 단일 메시지 전송
- 여러 턴 대화
- 에러 처리 (404)

**사용법**:
```bash
# 1. 테스트 데이터 준비
uv run python test_scripts/setup_web_test_data.py

# 2. 서버 실행 (별도 터미널)
uv run scripts/run_dev.py

# 3. 테스트 실행
pytest tests/test_chat_api_new.py -v
```

---

#### `test_api.py`
**용도**: pytest 기반 API 통합 테스트

**테스트 항목**:
- Health Check API
- Chat API (신규)

**사용법**:
```bash
# 1. 테스트 데이터 준비
uv run python test_scripts/setup_web_test_data.py

# 2. 서버 실행 (별도 터미널)
uv run scripts/run_dev.py

# 3. 테스트 실행
pytest tests/test_api.py -v
```

---

### 4. 결과 확인 스크립트 (`test_scripts/`)

#### `check_submit_result.py`
**용도**: Submit API 테스트 결과 확인

**확인 항목**:
- Submission 상태
- Scores (최종 점수)
- Turn Evaluations (턴별 평가)
- Holistic Flow Evaluation (전체 평가)
- Session 상태

**사용법**:
```bash
# Submit 테스트 실행 후
uv run python test_scripts/check_submit_result.py
```

**필요 파일**: `test_ids.json` (자동 생성됨)

---

### 5. 유틸리티 스크립트 (`test_scripts/`)

#### `check_server.py`
**용도**: 서버 상태 빠른 확인

**사용법**:
```bash
uv run python test_scripts/check_server.py
```

---

#### `check_judge0_connection.py`
**용도**: Judge0 연결 확인

**사용법**:
```bash
uv run python test_scripts/check_judge0_connection.py
```

---

## 🐳 Docker 실행 방법

### 1. 개발 환경 (PostgreSQL + Redis만)

**파일**: `docker-compose.dev.yml`

**용도**: 로컬 개발 시 DB와 Redis만 실행 (서버는 로컬에서 실행)

**실행 방법**:
```bash
# Docker Compose로 실행
docker-compose -f docker-compose.dev.yml up -d

# 로그 확인
docker-compose -f docker-compose.dev.yml logs -f

# 중지
docker-compose -f docker-compose.dev.yml down

# 데이터까지 삭제 (주의!)
docker-compose -f docker-compose.dev.yml down -v
```

**서비스**:
- PostgreSQL: `localhost:5435`
- Redis: `localhost:6379`
- Adminer: `http://localhost:8080`

**Adminer 접속 정보**:
- 시스템: PostgreSQL
- 서버: `postgres`
- 사용자명: `postgres`
- 비밀번호: `postgres`
- 데이터베이스: `ai_vibe_coding_test`

---

### 2. 전체 환경 (PostgreSQL + Redis + AI Worker + Judge Worker)

**파일**: `docker-compose.yml`

**용도**: 전체 시스템을 Docker로 실행

**실행 방법**:
```bash
# 1. 환경 변수 설정 (.env 파일 확인)
# 필수 환경 변수:
# - GEMINI_API_KEY
# - JUDGE0_API_URL
# - JUDGE0_API_KEY
# - JUDGE0_USE_RAPIDAPI
# - JUDGE0_RAPIDAPI_HOST

# 2. Docker Compose로 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 특정 서비스 로그만 확인
docker-compose logs -f ai_worker
docker-compose logs -f judge_worker

# 중지
docker-compose down

# 데이터까지 삭제 (주의!)
docker-compose down -v
```

**서비스**:
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
- AI Worker (FastAPI): `http://localhost:8001`
- Judge Worker: 백그라운드 실행

**헬스 체크**:
```bash
# AI Worker 헬스 체크
curl http://localhost:8001/health

# API 문서 확인
open http://localhost:8001/docs
```

---

### 3. 프로덕션 환경

**파일**: `docker-compose.prod.yml`

**용도**: 프로덕션 배포용 (별도 설정 필요)

---

## 📝 전체 테스트 시나리오

### 시나리오 1: Chat API 테스트

```bash
# 1. Docker 실행 (개발 환경)
docker-compose -f docker-compose.dev.yml up -d

# 2. 테스트 데이터 준비
uv run python test_scripts/setup_web_test_data.py

# 3. 서버 실행 (별도 터미널)
uv run scripts/run_dev.py

# 4. 테스트 실행
# 옵션 1: requests 기반 테스트
uv run python tests/test_chat_api_new.py

# 옵션 2: pytest 기반 테스트
pytest tests/test_chat_api_new.py -v
pytest tests/test_api.py -v
```

---

### 시나리오 2: Submit API 테스트 (단일 턴)

```bash
# 1. Docker 실행 (개발 환경)
docker-compose -f docker-compose.dev.yml up -d

# 2. 테스트 데이터 준비
uv run python test_scripts/setup_submit_test_data.py

# 3. 서버 실행 (별도 터미널)
uv run scripts/run_dev.py

# 4. 테스트 실행
uv run python test_single_turn_submit.py

# 5. 결과 확인
uv run python test_scripts/check_submit_result.py
```

---

### 시나리오 3: 전체 Flow 테스트 (여러 턴)

```bash
# 1. Docker 실행 (개발 환경)
docker-compose -f docker-compose.dev.yml up -d

# 2. 테스트 데이터 준비
uv run python test_scripts/setup_submit_test_data.py

# 3. 서버 실행 (별도 터미널)
uv run scripts/run_dev.py

# 4. 테스트 실행
uv run python test_full_flow_tsp.py

# 5. 결과 확인
uv run python test_scripts/check_submit_result.py
```

---

## 🔧 문제 해결

### 서버가 실행되지 않을 때

```bash
# 서버 상태 확인
uv run python test_scripts/check_server.py

# 서버 재시작
# Ctrl+C로 중지 후
uv run scripts/run_dev.py
```

### DB 연결 오류

```bash
# Docker 컨테이너 상태 확인
docker-compose -f docker-compose.dev.yml ps

# PostgreSQL 로그 확인
docker-compose -f docker-compose.dev.yml logs postgres

# PostgreSQL 재시작
docker-compose -f docker-compose.dev.yml restart postgres
```

### Redis 연결 오류

```bash
# Redis 로그 확인
docker-compose -f docker-compose.dev.yml logs redis

# Redis 재시작
docker-compose -f docker-compose.dev.yml restart redis
```

### Judge0 연결 오류

```bash
# Judge0 연결 확인
uv run python test_scripts/check_judge0_connection.py

# .env 파일 확인
# JUDGE0_API_URL, JUDGE0_API_KEY 등 설정 확인
```

---

## 📌 참고사항

1. **test_ids.json**: `setup_submit_test_data.py` 실행 시 자동 생성됨
2. **세션 ID**: Chat API 테스트는 고정 ID (1) 사용, Submit API 테스트는 동적 ID 사용
3. **토큰 계산**: Chat API는 `tokenCount` (현재 턴), `totalToken` (누적) 반환
4. **평가 결과**: Submit API 실행 후 `check_submit_result.py`로 확인 가능

---

## 📚 관련 문서

- `docs/API_Current_Implementation.md`: 현재 구현된 API 상세
- `docs/API_Specification.md`: API 명세서
- `docs/Quick_DB_Guide.md`: DB 가이드
- `docs/Judge0_Complete_Guide.md`: Judge0 가이드

