# Backend Docker 설정 가이드

## 📋 현재 상황

- **PostgreSQL**: 로컬 DB 사용 (`localhost:5432`, `user/user123`)
- **Redis**: Docker Compose로 실행 (`docker-compose.dev.yml`, `localhost:6379`)
- **Backend**: Docker로 실행 예정

## 🔧 Backend Docker 설정

### 방법 1: 같은 Docker Compose 네트워크 사용 (권장)

Backend를 `docker-compose.dev.yml`에 추가하거나, 같은 네트워크를 사용하는 별도 Docker Compose 파일 생성:

#### 옵션 A: docker-compose.dev.yml에 Backend 추가

```yaml
# docker-compose.dev.yml에 추가
services:
  # ... 기존 postgres, redis, adminer ...

  # Spring Boot Backend
  spring_boot:
    build:
      context: ../spring-backend  # Backend 프로젝트 경로
      dockerfile: Dockerfile
    container_name: ai_vibe_spring_dev
    environment:
      # PostgreSQL: 로컬 DB 접근 (host.docker.internal 사용)
      - SPRING_DATASOURCE_URL=jdbc:postgresql://host.docker.internal:5432/ai_vibe_coding_test
      - SPRING_DATASOURCE_USERNAME=user
      - SPRING_DATASOURCE_PASSWORD=user123
      # Redis: 같은 Docker 네트워크 내의 redis 서비스 사용
      - SPRING_REDIS_HOST=redis
      - SPRING_REDIS_PORT=6379
    ports:
      - "8080:8080"
    depends_on:
      - redis
    networks:
      - default  # docker-compose.dev.yml의 기본 네트워크
    restart: unless-stopped
```

#### 옵션 B: 별도 Docker Compose 파일 (외부 네트워크 사용)

```yaml
# backend-docker-compose.yml
version: '3.8'

services:
  spring_boot:
    build:
      context: .  # Backend 프로젝트 경로
      dockerfile: Dockerfile
    container_name: ai_vibe_spring
    environment:
      # PostgreSQL: 로컬 DB 접근
      - SPRING_DATASOURCE_URL=jdbc:postgresql://host.docker.internal:5432/ai_vibe_coding_test
      - SPRING_DATASOURCE_USERNAME=user
      - SPRING_DATASOURCE_PASSWORD=user123
      # Redis: 외부 네트워크의 redis 서비스 사용
      - SPRING_REDIS_HOST=ai_vibe_redis_dev  # docker-compose.dev.yml의 redis 컨테이너 이름
      - SPRING_REDIS_PORT=6379
    ports:
      - "8080:8080"
    networks:
      - ai_vibe_dev_network  # docker-compose.dev.yml과 같은 네트워크
    restart: unless-stopped

networks:
  ai_vibe_dev_network:
    external: true  # 외부 네트워크 사용
    name: langgraph_1_default  # docker-compose.dev.yml의 네트워크 이름 확인 필요
```

### 방법 2: 호스트 네트워크 모드 사용 (간단하지만 제한적)

```yaml
# backend-docker-compose.yml
version: '3.8'

services:
  spring_boot:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: ai_vibe_spring
    network_mode: "host"  # 호스트 네트워크 사용
    environment:
      # PostgreSQL: 로컬 DB (호스트 네트워크이므로 localhost 사용 가능)
      - SPRING_DATASOURCE_URL=jdbc:postgresql://localhost:5432/ai_vibe_coding_test
      - SPRING_DATASOURCE_USERNAME=user
      - SPRING_DATASOURCE_PASSWORD=user123
      # Redis: 로컬 Redis (호스트 네트워크이므로 localhost 사용 가능)
      - SPRING_REDIS_HOST=localhost
      - SPRING_REDIS_PORT=6379
    restart: unless-stopped
```

**주의**: `network_mode: "host"`는 Linux에서만 제대로 작동하며, Windows/Mac에서는 제한적입니다.

### 방법 3: 환경 변수로 설정 (application.yml 대신)

Backend의 `application.yml` 대신 Docker Compose의 환경 변수로 설정:

```yaml
# backend-docker-compose.yml
services:
  spring_boot:
    environment:
      # PostgreSQL 설정
      - SPRING_DATASOURCE_URL=jdbc:postgresql://host.docker.internal:5432/ai_vibe_coding_test
      - SPRING_DATASOURCE_USERNAME=user
      - SPRING_DATASOURCE_PASSWORD=user123
      - SPRING_DATASOURCE_DRIVER-CLASS-NAME=org.postgresql.Driver
      # JPA 설정
      - SPRING_JPA_HIBERNATE_DDL-AUTO=update
      - SPRING_JPA_SHOW-SQL=false
      - SPRING_JPA_PROPERTIES_HIBERNATE_DIALECT=org.hibernate.dialect.PostgreSQLDialect
      - SPRING_JPA_PROPERTIES_HIBERNATE_FORMAT_SQL=true
      # Redis 설정
      - SPRING_REDIS_HOST=redis  # 또는 localhost (호스트 네트워크 사용 시)
      - SPRING_REDIS_PORT=6379
```

## 🔍 Redis 접근 방법

### 시나리오 1: 같은 Docker Compose 네트워크

```yaml
# Backend Docker Compose
services:
  spring_boot:
    environment:
      - SPRING_REDIS_HOST=redis  # docker-compose.dev.yml의 redis 서비스 이름
      - SPRING_REDIS_PORT=6379
    networks:
      - default  # docker-compose.dev.yml과 같은 네트워크
```

### 시나리오 2: 외부 네트워크 (별도 Docker Compose)

```yaml
# docker-compose.dev.yml의 네트워크 확인
docker network ls
# 네트워크 이름 확인 (예: langgraph_1_default)

# backend-docker-compose.yml
services:
  spring_boot:
    environment:
      - SPRING_REDIS_HOST=ai_vibe_redis_dev  # 컨테이너 이름
      - SPRING_REDIS_PORT=6379
    networks:
      - ai_vibe_dev_network

networks:
  ai_vibe_dev_network:
    external: true
    name: langgraph_1_default  # 실제 네트워크 이름
```

### 시나리오 3: 호스트의 Redis 접근

```yaml
# Backend Docker Compose
services:
  spring_boot:
    environment:
      - SPRING_REDIS_HOST=host.docker.internal  # Windows/Mac
      # 또는
      - SPRING_REDIS_HOST=172.17.0.1  # Linux (Docker bridge IP)
      - SPRING_REDIS_PORT=6379
```

## 📝 Backend application.yml 수정 (환경 변수 사용)

Backend의 `application.yml`을 환경 변수를 사용하도록 수정:

```yaml
spring:
  datasource:
    url: ${SPRING_DATASOURCE_URL:jdbc:postgresql://localhost:5432/ai_vibe_coding_test}
    username: ${SPRING_DATASOURCE_USERNAME:user}
    password: ${SPRING_DATASOURCE_PASSWORD:user123}
    driver-class-name: ${SPRING_DATASOURCE_DRIVER-CLASS-NAME:org.postgresql.Driver}
  jpa:
    hibernate:
      ddl-auto: ${SPRING_JPA_HIBERNATE_DDL-AUTO:update}
    show-sql: ${SPRING_JPA_SHOW-SQL:false}
    properties:
      hibernate:
        dialect: ${SPRING_JPA_PROPERTIES_HIBERNATE_DIALECT:org.hibernate.dialect.PostgreSQLDialect}
        format_sql: ${SPRING_JPA_PROPERTIES_HIBERNATE_FORMAT_SQL:true}
  redis:
    host: ${SPRING_REDIS_HOST:localhost}
    port: ${SPRING_REDIS_PORT:6379}
```

## 🚀 실행 순서

### 1. Redis 실행 (docker-compose.dev.yml)

```powershell
# Redis만 실행
docker-compose -f docker-compose.dev.yml up -d redis
```

### 2. Backend Docker 실행

```powershell
# 방법 1: docker-compose.dev.yml에 추가한 경우
docker-compose -f docker-compose.dev.yml up -d spring_boot

# 방법 2: 별도 Docker Compose 파일 사용
docker-compose -f backend-docker-compose.yml up -d
```

### 3. 확인

```powershell
# 컨테이너 상태 확인
docker ps

# Backend 로그 확인
docker logs ai_vibe_spring

# Redis 연결 확인
docker exec -it ai_vibe_redis_dev redis-cli ping
```

## ✅ 권장 설정 (최종)

### docker-compose.dev.yml에 Backend 추가

```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  # Redis
  redis:
    image: redis:7-alpine
    container_name: ai_vibe_redis_dev
    ports:
      - "6379:6379"
    # ... 기존 설정 ...

  # Spring Boot Backend 추가
  spring_boot:
    build:
      context: ../spring-backend  # Backend 프로젝트 경로
      dockerfile: Dockerfile
    container_name: ai_vibe_spring_dev
    environment:
      # PostgreSQL: 로컬 DB
      - SPRING_DATASOURCE_URL=jdbc:postgresql://host.docker.internal:5432/ai_vibe_coding_test
      - SPRING_DATASOURCE_USERNAME=user
      - SPRING_DATASOURCE_PASSWORD=user123
      # Redis: 같은 네트워크의 redis
      - SPRING_REDIS_HOST=redis
      - SPRING_REDIS_PORT=6379
    ports:
      - "8080:8080"
    depends_on:
      - redis
    restart: unless-stopped
```

## 🔍 문제 해결

### PostgreSQL 연결 실패

- Windows/Mac: `host.docker.internal` 사용
- Linux: `172.17.0.1` (Docker bridge IP) 또는 `--network host` 사용

### Redis 연결 실패

- 같은 네트워크인지 확인: `docker network inspect <network_name>`
- Redis 컨테이너 이름 확인: `docker ps`
- 포트 매핑 확인: `docker-compose.dev.yml`의 `ports: "6379:6379"`

### 네트워크 확인

```powershell
# 네트워크 목록
docker network ls

# 특정 네트워크의 컨테이너 확인
docker network inspect <network_name>
```







