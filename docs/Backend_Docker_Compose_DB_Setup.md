# Backend Docker Compose DB 설정 가이드

## 📋 개요

Spring Boot Backend가 Docker Compose로 실행되며 JPA의 `ddl-auto: update`로 자동으로 DB 스키마를 생성하는 경우, Python/FastAPI도 같은 DB를 사용하도록 설정합니다.

## 🔍 Backend 설정 확인

사용자가 제공한 Backend 설정:

```yaml
spring:
  datasource:
    url: jdbc:postgresql://localhost:5432/ai_vibe_coding_test
    username: user
    password: user123
    driver-class-name: org.postgresql.Driver
  jpa:
    hibernate:
      ddl-auto: update  # 자동으로 테이블 생성
```

## ⚙️ Python/FastAPI 설정

### `.env` 파일 설정

Backend 설정에 맞춰 `.env` 파일을 수정합니다:

```env
# PostgreSQL 설정 (Backend와 동일)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=user
POSTGRES_PASSWORD=user123
POSTGRES_DB=ai_vibe_coding_test
```

### Backend Docker Compose 설정 확인

Backend의 Docker Compose 파일에서 PostgreSQL 설정을 확인합니다:

```yaml
# Backend docker-compose.yml
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: user          # Backend 설정과 동일
      POSTGRES_PASSWORD: user123   # Backend 설정과 동일
      POSTGRES_DB: ai_vibe_coding_test
    ports:
      - "5432:5432"  # 호스트 포트:컨테이너 포트
```

## 🚀 설정 단계

### 1. Backend Docker Compose 실행

```powershell
# Backend 프로젝트에서
docker-compose up -d postgres
# 또는
docker-compose up -d  # 전체 서비스 실행
```

### 2. Backend 실행 (자동 테이블 생성)

Backend를 실행하면 JPA가 자동으로 테이블을 생성합니다:

```powershell
# Backend 실행
# Spring Boot가 시작되면 자동으로 테이블 생성
```

### 3. Python/FastAPI 설정

`.env` 파일에 Backend와 동일한 설정 적용:

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=user
POSTGRES_PASSWORD=user123
POSTGRES_DB=ai_vibe_coding_test
```

### 4. Python/FastAPI 실행

```powershell
# Python/FastAPI 실행
uv run python -m app.main
# 또는
python -m app.main
```

## ✅ 확인 방법

### 1. Backend가 테이블을 생성했는지 확인

```powershell
# Docker PostgreSQL에 접속
docker exec -it <postgres_container_name> psql -U user -d ai_vibe_coding_test
# 비밀번호: user123

# 테이블 목록 확인
\dt

# 또는 특정 스키마의 테이블 확인
\dt public.*
\dt ai_vibe_coding_test.*
```

### 2. Python/FastAPI 연결 테스트

```python
# Python에서 연결 테스트
from app.core.config import settings
print(f"DB URL: {settings.POSTGRES_URL}")

# 연결 테스트
import asyncio
from app.infrastructure.persistence.session import init_db

async def test():
    try:
        await init_db()
        print("✅ DB 연결 성공")
    except Exception as e:
        print(f"❌ DB 연결 실패: {e}")

asyncio.run(test())
```

### 3. 같은 테이블에 접근 가능한지 확인

```sql
-- Backend에서 생성한 테이블 확인
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public'  -- 또는 Backend가 사용하는 스키마
ORDER BY table_name;

-- Python에서도 같은 테이블에 접근 가능한지 확인
SELECT COUNT(*) FROM prompt_sessions;  -- 예시
```

## 📝 주의사항

1. **스키마 이름**: Backend가 `public` 스키마를 사용하는지, `ai_vibe_coding_test` 스키마를 사용하는지 확인
   - `ddl-auto: update`는 기본적으로 `public` 스키마를 사용
   - `default_schema: ai_vibe_coding_test` 설정이 있으면 해당 스키마 사용

2. **포트 매핑**: Docker Compose의 포트 매핑 확인
   - `5432:5432` → 호스트의 5432 포트로 접속
   - 다른 포트 매핑이면 `.env`의 `POSTGRES_PORT` 수정

3. **사용자 권한**: Backend가 사용하는 사용자(`user`)가 충분한 권한을 가지고 있는지 확인

4. **테이블 생성 순서**: Backend를 먼저 실행하여 테이블을 생성한 후 Python/FastAPI 실행

## 🔄 통합 실행 시나리오

### 시나리오 1: Backend와 Python을 별도로 실행

```powershell
# 1. Backend Docker Compose 실행
cd backend-project
docker-compose up -d postgres
# Backend 실행 (테이블 자동 생성)

# 2. Python/FastAPI 실행 (같은 DB 사용)
cd python-project
# .env 파일에 Backend와 동일한 설정
uv run python -m app.main
```

### 시나리오 2: 같은 Docker Compose 네트워크 사용

```yaml
# 통합 docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: user123
      POSTGRES_DB: ai_vibe_coding_test
    ports:
      - "5432:5432"
    networks:
      - app_network

  spring_boot:
    # Backend 설정
    environment:
      - SPRING_DATASOURCE_URL=jdbc:postgresql://postgres:5432/ai_vibe_coding_test
      - SPRING_DATASOURCE_USERNAME=user
      - SPRING_DATASOURCE_PASSWORD=user123
    depends_on:
      - postgres
    networks:
      - app_network

  ai_worker:
    # Python/FastAPI 설정
    environment:
      - POSTGRES_HOST=postgres
      - POSTGRES_PORT=5432
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=user123
      - POSTGRES_DB=ai_vibe_coding_test
    depends_on:
      - postgres
    networks:
      - app_network

networks:
  app_network:
    driver: bridge
```

## 🚀 빠른 설정 체크리스트

- [ ] Backend Docker Compose의 PostgreSQL 설정 확인 (user/user123)
- [ ] Backend의 `application.yml` 확인 (ddl-auto: update)
- [ ] Python/FastAPI `.env` 파일에 동일한 설정 적용
- [ ] Backend 실행 후 테이블 생성 확인
- [ ] Python/FastAPI 연결 테스트
- [ ] 같은 테이블에 접근 가능한지 확인

## 💡 팁

- Backend가 자동으로 테이블을 생성하므로, Python 쪽에서는 테이블 생성 스크립트(`init-db.sql`)를 실행할 필요가 없습니다
- Backend의 `ddl-auto: update` 설정으로 인해 테이블 구조가 변경될 수 있으므로, Python 모델도 동기화 필요
- 개발 환경에서는 `ddl-auto: update`를 사용하고, 프로덕션에서는 `validate` 또는 `none` 사용 권장








