# Backend Docker Compose DB 설정 가이드

## 📋 개요

Spring Boot Backend가 Docker Compose로 실행되며 자동으로 DB 스키마를 생성하는 설정에 맞춰 Python/FastAPI도 같은 DB를 사용하도록 설정합니다.

## 🔍 Backend Docker Compose 설정 확인

Backend의 Docker Compose 파일에서 PostgreSQL 설정을 확인합니다:

```yaml
# Backend docker-compose.yml 예시
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: postgres        # 또는 user
      POSTGRES_PASSWORD: postgres    # 또는 user123
      POSTGRES_DB: ai_vibe_coding_test
    ports:
      - "5432:5432"  # 호스트 포트:컨테이너 포트
  
  spring_boot:
    environment:
      SPRING_DATASOURCE_URL: jdbc:postgresql://postgres:5432/ai_vibe_coding_test
      SPRING_DATASOURCE_USERNAME: postgres  # 또는 user
      SPRING_DATASOURCE_PASSWORD: postgres  # 또는 user123
```

## ⚙️ Python/FastAPI 설정

### 방법 1: Docker Compose 네트워크 내에서 실행 (권장)

Python/FastAPI도 같은 Docker Compose 네트워크에서 실행하는 경우:

**`.env` 파일:**
```env
# PostgreSQL 설정 (Docker Compose 네트워크 내)
POSTGRES_HOST=postgres  # Docker 서비스 이름
POSTGRES_PORT=5432      # 컨테이너 내부 포트
POSTGRES_USER=postgres  # Backend 설정과 동일
POSTGRES_PASSWORD=postgres  # Backend 설정과 동일
POSTGRES_DB=ai_vibe_coding_test
```

### 방법 2: 로컬에서 실행 (호스트에서 접속)

Python/FastAPI를 로컬에서 실행하고 Docker Compose의 PostgreSQL에 접속하는 경우:

**`.env` 파일:**
```env
# PostgreSQL 설정 (호스트에서 Docker 접속)
POSTGRES_HOST=localhost  # Docker 호스트
POSTGRES_PORT=5432       # Docker 포트 매핑 (호스트 포트)
POSTGRES_USER=postgres   # Backend 설정과 동일
POSTGRES_PASSWORD=postgres  # Backend 설정과 동일
POSTGRES_DB=ai_vibe_coding_test
```

## 🔧 Backend 설정 예시

### Spring Boot application.yml

```yaml
spring:
  datasource:
    url: jdbc:postgresql://postgres:5432/ai_vibe_coding_test
    username: postgres
    password: postgres
    driver-class-name: org.postgresql.Driver
  jpa:
    hibernate:
      ddl-auto: update  # 자동으로 테이블 생성
    show-sql: false
    properties:
      hibernate:
        dialect: org.hibernate.dialect.PostgreSQLDialect
        format_sql: true
        default_schema: ai_vibe_coding_test  # 스키마 지정 (선택)
```

### 또는 환경 변수로 설정

```yaml
# docker-compose.yml
services:
  spring_boot:
    environment:
      - SPRING_DATASOURCE_URL=jdbc:postgresql://postgres:5432/ai_vibe_coding_test
      - SPRING_DATASOURCE_USERNAME=postgres
      - SPRING_DATASOURCE_PASSWORD=postgres
```

## 📝 현재 프로젝트 설정

현재 `docker-compose.yml`의 PostgreSQL 설정:

```yaml
postgres:
  image: postgres:15-alpine
  container_name: ai_vibe_postgres
  environment:
    POSTGRES_USER: postgres
    POSTGRES_PASSWORD: postgres
    POSTGRES_DB: ai_vibe_coding_test
  ports:
    - "5432:5432"  # 호스트 5432 → 컨테이너 5432
```

**Python/FastAPI `.env` 설정:**
```env
# 로컬에서 실행하는 경우
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=ai_vibe_coding_test
```

## ✅ 확인 방법

### 1. Backend가 테이블을 생성했는지 확인

```powershell
# Docker PostgreSQL에 접속
docker exec -it ai_vibe_postgres psql -U postgres -d ai_vibe_coding_test

# 테이블 목록 확인
\dt

# 또는 특정 스키마의 테이블 확인
\dt ai_vibe_coding_test.*
```

### 2. Python/FastAPI 연결 테스트

```python
# Python에서 연결 테스트
from app.core.config import settings
print(settings.POSTGRES_URL)

# 또는 직접 테스트
import asyncio
from app.infrastructure.persistence.session import init_db

async def test():
    await init_db()
    print("✅ DB 연결 성공")

asyncio.run(test())
```

### 3. Spring Boot와 Python이 같은 DB를 사용하는지 확인

```sql
-- Spring Boot에서 생성한 테이블 확인
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public'  -- 또는 'ai_vibe_coding_test'
ORDER BY table_name;

-- Python에서도 같은 테이블에 접근 가능한지 확인
SELECT COUNT(*) FROM prompt_sessions;  -- 예시
```

## 🔄 통합 Docker Compose 설정

Backend와 Python/FastAPI를 함께 실행하는 경우:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: ai_vibe_postgres
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: ai_vibe_coding_test
    ports:
      - "5432:5432"
    networks:
      - ai_vibe_network

  spring_boot:
    # Backend 설정
    environment:
      - SPRING_DATASOURCE_URL=jdbc:postgresql://postgres:5432/ai_vibe_coding_test
      - SPRING_DATASOURCE_USERNAME=postgres
      - SPRING_DATASOURCE_PASSWORD=postgres
    depends_on:
      - postgres
    networks:
      - ai_vibe_network

  ai_worker:
    # Python/FastAPI 설정
    environment:
      - POSTGRES_HOST=postgres
      - POSTGRES_PORT=5432
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=ai_vibe_coding_test
    depends_on:
      - postgres
    networks:
      - ai_vibe_network

networks:
  ai_vibe_network:
    driver: bridge
```

## 📝 주의사항

1. **스키마 이름**: Backend가 `public` 스키마를 사용하는지, `ai_vibe_coding_test` 스키마를 사용하는지 확인
2. **ddl-auto 설정**: Backend의 `ddl-auto: update`로 자동 생성되는 테이블 구조 확인
3. **포트 매핑**: Docker Compose의 포트 매핑 확인 (호스트 포트:컨테이너 포트)
4. **네트워크**: 같은 Docker 네트워크를 사용하는지 확인
5. **사용자 권한**: Backend가 사용하는 사용자와 동일한 사용자 사용

## 🚀 빠른 설정 체크리스트

- [ ] Backend Docker Compose의 PostgreSQL 설정 확인
- [ ] Backend의 `application.yml` 또는 환경 변수 확인
- [ ] Python/FastAPI `.env` 파일에 동일한 설정 적용
- [ ] Backend 실행 후 테이블 생성 확인
- [ ] Python/FastAPI 연결 테스트
- [ ] 같은 테이블에 접근 가능한지 확인








