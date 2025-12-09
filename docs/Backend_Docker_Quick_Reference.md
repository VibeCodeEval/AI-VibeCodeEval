# Backend Docker 설정 Quick Reference

## 🔄 application.yml 변경 방법

### 현재 설정 (로컬 실행)

```yaml
spring:
  datasource:
    url: jdbc:postgresql://localhost:5432/ai_vibe_coding_test
    username: user
    password: user123
    driver-class-name: org.postgresql.Driver
  jpa:
    hibernate:
      ddl-auto: update
    show-sql: false
    properties:
      hibernate:
        dialect: org.hibernate.dialect.PostgreSQLDialect
        format_sql: true
```

### Docker 실행 시 변경 방법

#### 옵션 1: 직접 변경 (간단)

```yaml
spring:
  datasource:
    # localhost → host.docker.internal 변경
    url: jdbc:postgresql://host.docker.internal:5432/ai_vibe_coding_test
    username: user
    password: user123
    driver-class-name: org.postgresql.Driver
  jpa:
    hibernate:
      ddl-auto: update
    show-sql: false
    properties:
      hibernate:
        dialect: org.hibernate.dialect.PostgreSQLDialect
        format_sql: true
  redis:
    # Redis도 호스트 접근
    host: host.docker.internal
    port: 6379
```

**주의**: 
- Windows/Mac: `host.docker.internal` 사용
- Linux: `172.17.0.1` 사용

#### 옵션 2: 환경 변수 사용 (권장)

**application.yml:**
```yaml
spring:
  datasource:
    url: ${SPRING_DATASOURCE_URL:jdbc:postgresql://localhost:5432/ai_vibe_coding_test}
    username: ${SPRING_DATASOURCE_USERNAME:user}
    password: ${SPRING_DATASOURCE_PASSWORD:user123}
    driver-class-name: org.postgresql.Driver
  jpa:
    hibernate:
      ddl-auto: update
    show-sql: false
    properties:
      hibernate:
        dialect: org.hibernate.dialect.PostgreSQLDialect
        format_sql: true
  redis:
    host: ${SPRING_REDIS_HOST:localhost}
    port: ${SPRING_REDIS_PORT:6379}
```

**docker-compose.yml:**
```yaml
services:
  spring_boot:
    environment:
      - SPRING_DATASOURCE_URL=jdbc:postgresql://host.docker.internal:5432/ai_vibe_coding_test
      - SPRING_DATASOURCE_USERNAME=user
      - SPRING_DATASOURCE_PASSWORD=user123
      - SPRING_REDIS_HOST=host.docker.internal
      - SPRING_REDIS_PORT=6379
```

## 📋 설정 비교표

| 환경 | PostgreSQL URL | Redis Host | 설명 |
|------|---------------|------------|------|
| **로컬 실행** | `localhost:5432` | `localhost` | Backend를 로컬에서 직접 실행 |
| **Docker (Windows/Mac)** | `host.docker.internal:5432` | `host.docker.internal` | Docker 컨테이너에서 호스트 접근 |
| **Docker (Linux)** | `172.17.0.1:5432` | `172.17.0.1` | Docker bridge IP 사용 |
| **같은 네트워크** | `host.docker.internal:5432` | `redis` | Redis는 서비스 이름 사용 가능 |

## 🚀 실행 명령어

### 1. Redis 실행
```powershell
docker-compose -f docker-compose.dev.yml up -d redis
```

### 2. Backend 실행

#### 로컬 실행:
```powershell
./mvnw spring-boot:run
```

#### Docker 실행:
```powershell
# docker-compose.yml이 있는 경우
docker-compose up -d spring_boot

# 또는 docker-compose.dev.yml에 추가한 경우
docker-compose -f docker-compose.dev.yml up -d spring_boot
```

### 3. 확인
```powershell
# Backend 로그
docker logs -f ai_vibe_spring

# PostgreSQL 연결 확인
psql -h localhost -p 5432 -U user -d ai_vibe_coding_test

# Redis 연결 확인
docker exec -it ai_vibe_redis_dev redis-cli ping
```

## 🔍 문제 해결

### PostgreSQL 연결 실패
```
Error: Connection refused
```
**해결**: `localhost` → `host.docker.internal` 변경

### Redis 연결 실패
```
Error: Unable to connect to Redis
```
**해결**: 
- `localhost` → `host.docker.internal` 변경
- 또는 같은 네트워크 사용: `redis` (서비스 이름)

### Linux에서 host.docker.internal 작동 안 함
**해결**: `172.17.0.1` 사용 또는 `--network host` 사용







