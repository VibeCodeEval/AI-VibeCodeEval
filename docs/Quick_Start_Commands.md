# 🚀 빠른 시작 명령어

## 📦 DB 실행

```bash
# PostgreSQL & Redis 실행
docker-compose -f docker-compose.dev.yml up -d

# 실행 확인
docker ps

# 로그 확인
docker-compose -f docker-compose.dev.yml logs -f

# 중지
docker-compose -f docker-compose.dev.yml down
```

## 🔴 Redis 확인

### Redis CLI 접속 방법

**방법 1: 컨테이너 내부에서 redis-cli 실행 (권장)**
```bash
# 실행 중인 Redis 컨테이너 확인
docker ps | findstr redis

# 컨테이너 내부에서 redis-cli 실행
docker exec -it ai_vibe_redis_dev redis-cli
# 또는 다른 컨테이너 이름 사용
docker exec -it vibecode-redis redis-cli
```

**방법 2: 호스트에서 redis-cli로 접속**
```bash
# 호스트에 redis-cli가 설치되어 있어야 함
# Windows: choco install redis 또는 직접 다운로드
# Mac: brew install redis
# Linux: apt-get install redis-tools

redis-cli -h localhost -p 6378
```

**방법 3: 컨테이너가 중지된 경우**
```bash
# docker-compose로 시작
docker-compose -f docker-compose.dev.yml up -d redis

# 또는 개별 컨테이너 시작
docker start ai_vibe_redis_dev
```

### 유용한 Redis 명령어

redis-cli 접속 후 사용 가능한 명령어:
```bash
PING              # 연결 확인 (PONG 응답)
KEYS *            # 모든 키 조회
KEYS pattern      # 패턴으로 키 검색 (예: KEYS langgraph:*)
GET <key>         # 키 값 조회
SET <key> <value> # 키 값 설정
DEL <key>         # 키 삭제
DBSIZE            # 현재 DB의 키 개수
INFO              # 서버 정보
INFO memory       # 메모리 사용량
INFO keyspace     # 데이터베이스별 키 통계
SELECT 0          # DB 선택 (0-15)
FLUSHDB           # 현재 DB 전체 삭제 (주의!)
FLUSHALL          # 모든 DB 삭제 (주의!)
TTL <key>         # 키의 남은 TTL 확인
EXPIRE <key> <sec> # 키에 TTL 설정
```

### Redis 상태 확인 (컨테이너 외부에서)
```bash
# 컨테이너 로그 확인
docker logs ai_vibe_redis_dev

# 컨테이너 상태 확인
docker ps | findstr redis

# Redis 연결 테스트
docker exec ai_vibe_redis_dev redis-cli ping
```

### ⚠️ 맥에서 로컬 Redis 충돌 문제

맥에 로컬 Redis가 설치되어 있으면 포트 6379 충돌이 발생할 수 있습니다.

**해결 방법 1: 로컬 Redis 중지 (권장)**
```bash
# 로컬 Redis 실행 중인지 확인
brew services list | grep redis
# 또는
ps aux | grep redis

# 로컬 Redis 중지
brew services stop redis
# 또는
redis-cli shutdown
```

**해결 방법 2: Docker Redis 포트 변경**
`docker-compose.dev.yml`에서 Redis 포트를 변경:
```yaml
redis:
  ports:
    - "6380:6379"  # 호스트 포트를 6380으로 변경
```

그리고 `.env` 파일도 수정:
```env
REDIS_PORT=6380
```

**해결 방법 3: 로컬 Redis 사용**
Docker Redis를 실행하지 않고 로컬 Redis를 사용:
```env
REDIS_HOST=localhost
REDIS_PORT=6379
```

## 🐍 Python 환경 설정 (uv 사용)

### uv 설치

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Linux/Mac
curl -LsSf https://astral.sh/uv/install.sh | sh

# 또는 pip로 설치
pip install uv
```

### 의존성 설치

```bash
# 프로젝트 루트에서 실행
cd LangGraph_1

# Python 3.10 설치 + 가상 환경 생성 + 의존성 설치 (한 번에)
uv sync

# 의존성만 업데이트
uv sync --upgrade
```

### uv 주요 명령어

```bash
# 스크립트 실행 (가상 환경 자동 사용)
uv run scripts/run_dev.py
uv run python test_scripts/test_chat_flow.py
uv run pytest tests/

# Python 버전 관리
uv python install 3.10      # Python 3.10 설치
uv python list               # 설치된 버전 목록

# 패키지 관리
uv pip install <package>     # 패키지 설치
uv pip list                   # 설치된 패키지 목록
```

## 🐍 서버 실행

```bash
# 방법 1: uv run 사용 (권장)
uv run scripts/run_dev.py

# 방법 2: uvicorn 직접 실행
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 방법 3: 가상 환경 활성화 후 실행
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# Linux/Mac
source .venv/bin/activate

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## ⚙️ Judge0 Worker 실행

```bash
# Judge0 Worker 실행 (코드 실행 처리)
uv run python -m app.application.workers.judge_worker

# 또는
python -m app.application.workers.judge_worker
```

**참고**: 코드 제출 기능을 사용하려면 Judge0 Worker가 실행 중이어야 합니다.

## ✅ 확인

- 서버: http://localhost:8000
- API 문서: http://localhost:8000/docs
- Adminer (DB 관리): http://localhost:8081
  - 시스템: PostgreSQL
  - 서버: postgres
  - 사용자: postgres
  - 비밀번호: postgres
  - 데이터베이스: ai_vibe_coding_test

## 🔧 환경 변수

`.env` 파일 생성 필요:
```env
GEMINI_API_KEY=your_key_here
POSTGRES_HOST=localhost
POSTGRES_PORT=5435
POSTGRES_DB=ai_vibe_coding_test
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
REDIS_HOST=localhost
REDIS_PORT=6379

# Judge0 설정 (코드 제출 기능 사용 시)
JUDGE0_API_URL=https://judge0-ce.p.rapidapi.com
JUDGE0_API_KEY=your_rapidapi_key_here
JUDGE0_USE_RAPIDAPI=true
JUDGE0_RAPIDAPI_HOST=judge0-ce.p.rapidapi.com
USE_REDIS_QUEUE=true
```

