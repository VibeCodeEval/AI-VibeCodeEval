# Backend Docker · DB 연동 가이드

> **최종 정리일**: 2026-03-27

Spring Boot 백엔드, Docker Compose(PostgreSQL·Redis), Python/FastAPI(AI Worker)가 **같은 DB·네트워크**를 쓰도록 맞추는 내용을 한 문서로 모았습니다.

---

## 문서 통합 이력 · Maestro 참조

### 통합 이력 (기존 `docs/` 파일 병합)

다음 다섯 문서를 이 파일로 합쳤습니다.

| 통합 전 파일 | 역할 |
|--------------|------|
| `Backend_Docker_Quick_Reference.md` | application.yml·환경 변수 빠른 참조 |
| `Backend_Docker_Setup_Guide.md` | Spring을 Docker에서 실행 (네트워크·Redis) |
| `Backend_Docker_Compose_DB_Setup.md` | Spring JPA + FastAPI 동일 DB (user/user123 시나리오) |
| `Backend_DB_Configuration_Guide.md` | 동일 주제(이 레포 `docker-compose`의 postgres 계정 등) |
| `Docker_PostgreSQL_Setup_Guide.md` | 이 레포에서 Compose로 PG/Redis 띄우기·접속·스키마 |

### Maestro 쪽에서 같이 보면 좋은 문서

Docker Compose **명령줄** 자체는 Maestro에 없고, **데이터가 Redis인지 PostgreSQL인지** 같은 맥락이 정리되어 있습니다.

| 경로 | 내용 |
|------|------|
| `.maestro/docs/current_eval_flow_db_to_llm.md` | 제출·평가 시 **Redis(graph state)** vs **PostgreSQL** 역할 구분 |
| `.maestro/docs/V2.1_Change_Log.md` | V2.1 평가·점수·`prompt_evaluations` 등 **스키마/필드** 변경 이력 (인프라 전용 장은 아님) |
| `.maestro/reports/test_failure_analysis.md` | DB/Redis 미기동 시 테스트 실패 사례 — **Compose로 기동 필요** 언급 |

---

## 1. Quick Reference

### 1.1 application.yml 패턴

**로컬에서 Spring만 실행할 때 (예시)**

```yaml
spring:
  datasource:
    url: jdbc:postgresql://localhost:5432/ai_vibe_coding_test
    username: user
    password: user123
    driver-class-name: org.postgresql.Driver
```

**Spring을 Docker에서 실행하고, PostgreSQL·Redis는 호스트 또는 다른 Compose에 둘 때**

- Windows/Mac: `localhost` → `host.docker.internal`
- Linux: `172.17.0.1` 등 Docker bridge IP

```yaml
spring:
  datasource:
    url: jdbc:postgresql://host.docker.internal:5432/ai_vibe_coding_test
  redis:
    host: host.docker.internal
    port: 6379
```

**환경 변수로 두기 (권장)**

```yaml
spring:
  datasource:
    url: ${SPRING_DATASOURCE_URL:jdbc:postgresql://localhost:5432/ai_vibe_coding_test}
    username: ${SPRING_DATASOURCE_USERNAME:user}
    password: ${SPRING_DATASOURCE_PASSWORD:user123}
  redis:
    host: ${SPRING_REDIS_HOST:localhost}
    port: ${SPRING_REDIS_PORT:6379}
```

```yaml
# docker-compose 예: Spring 서비스
environment:
  - SPRING_DATASOURCE_URL=jdbc:postgresql://host.docker.internal:5432/ai_vibe_coding_test
  - SPRING_REDIS_HOST=host.docker.internal
```

### 1.2 환경별 비교

| 환경 | PostgreSQL | Redis |
|------|------------|--------|
| Spring 로컬 | `localhost:5432` | `localhost:6379` |
| Spring Docker (Win/Mac) | `host.docker.internal:5432` | `host.docker.internal` 또는 Compose 서비스명 `redis` |
| Spring Docker (Linux) | `172.17.0.1:5432` 등 | 동일 |
| 같은 Compose 네트워크 | 서비스명 `postgres:5432` | 서비스명 `redis:6379` |

### 1.3 자주 쓰는 명령 (개발용 Compose 파일명은 프로젝트에 맞게)

```powershell
docker-compose -f docker-compose.dev.yml up -d redis
docker-compose up -d spring_boot
docker logs -f ai_vibe_spring
docker exec -it ai_vibe_redis_dev redis-cli ping
```

### 1.4 문제 해결 요약

| 증상 | 조치 |
|------|------|
| Connection refused (PG) | 컨테이너에서는 `host.docker.internal` 등으로 호스트 DB 주소 확인 |
| Redis 연결 실패 | `localhost` 대신 `host.docker.internal` 또는 같은 네트워크의 서비스명 |
| Linux에서 `host.docker.internal` 없음 | `172.17.0.1` 또는 `extra_hosts` / `--add-host` |

---

## 2. Spring Boot를 Docker에서 실행 (상세)

### 2.1 같은 Docker Compose 네트워크 (권장)

`docker-compose.dev.yml`에 Spring 서비스를 추가하거나, 기존 `redis`와 **같은 `networks`** 를 쓰는 별도 Compose를 둡니다.

- PostgreSQL이 **호스트**에만 있을 때: `SPRING_DATASOURCE_URL=jdbc:postgresql://host.docker.internal:5432/...`
- Redis가 **같은 Compose**에 있으면: `SPRING_REDIS_HOST=redis`, `SPRING_REDIS_PORT=6379`

### 2.2 외부 네트워크로 기존 Redis 컨테이너에 붙기

```powershell
docker network ls
docker network inspect <network_name>
```

`networks`에 `external: true`로 위 네트워크 이름을 지정하고, Redis는 컨테이너 이름 또는 서비스명으로 연결합니다.

### 2.3 `network_mode: "host"` (Linux 위주)

호스트 네트워크를 쓰면 Spring 쪽은 `localhost:5432`로 로컬 PG/Redis에 붙을 수 있으나, **Windows/Mac에서는 제한**이 있습니다.

### 2.4 실행 순서

1. Redis(또는 전체 인프라) 기동  
2. Spring 컨테이너 기동  
3. `docker ps`, `docker logs`로 확인  

---

## 3. Spring Boot와 Python(FastAPI) 동일 DB 사용

Spring이 `ddl-auto: update` 등으로 스키마를 잡고, AI Worker는 **같은 PostgreSQL**에 붙는 경우의 정리입니다.

### 3.1 이 레포 `app/core/config.py` 기본값과 맞추기

현재 코드 기본값은 대략 다음과 같습니다(`.env`로 덮어씀).

- `POSTGRES_USER` / `POSTGRES_PASSWORD`: `postgres` / `postgres`
- `POSTGRES_DB`: `ai_vibe_coding_test`
- `POSTGRES_PORT`: **기본 `5435`** — 루트 `docker-compose.yml`이 호스트에 **`5432:5432`** 로 올리는 경우, 로컬 Worker는 **`POSTGRES_PORT=5432`** 로 맞출 것.

즉, **Compose 포트 매핑과 `.env`의 `POSTGRES_PORT`는 반드시 일치**시켜야 합니다.

### 3.2 시나리오 A: Backend 문서의 `user` / `user123` + 로컬 PG

Backend가 아래처럼 맞춰져 있을 때:

```yaml
spring:
  datasource:
    url: jdbc:postgresql://localhost:5432/ai_vibe_coding_test
    username: user
    password: user123
```

AI Worker `.env` 예:

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=user
POSTGRES_PASSWORD=user123
POSTGRES_DB=ai_vibe_coding_test
```

Backend를 먼저 실행해 테이블을 만든 뒤 Worker를 띄우는 순서를 권장합니다.

### 3.3 시나리오 B: 이 레포 `docker-compose.yml`의 PostgreSQL

`postgres` 서비스가 `POSTGRES_USER: postgres`, `POSTGRES_PASSWORD: postgres` 인 구성과 맞춥니다.

**호스트에서 Worker만 실행할 때**

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=ai_vibe_coding_test
```

**Worker도 Compose 네트워크 안에서 실행할 때**

```env
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=ai_vibe_coding_test
```

### 3.4 연결 확인 (Python)

```python
from app.core.config import settings
print(settings.POSTGRES_URL)

import asyncio
from app.infrastructure.persistence.session import init_db

async def test():
    await init_db()
    print("OK")

asyncio.run(test())
```

### 3.5 통합 `docker-compose` 예시 (개념)

`postgres` → `spring_boot` / `ai_worker` 가 같은 `networks`에 있고, Worker의 `POSTGRES_HOST=postgres` 형태로 연결합니다. (실제 서비스 이름·포트는 사용 중인 `docker-compose.yml`에 맞출 것.)

### 3.6 주의사항

- **스키마**: `public` vs `ai_vibe_coding_test` 등 — Spring·SQLAlchemy 모델·`init-db.sql`이 동일 스키마를 바라보는지 확인 (`docs/Schema_Reference_Index.md`, `docs/DB_Schema_Changes.md`).
- **테이블 소유**: 운영에서는 마이그레이션 전략을 팀 규칙에 맞출 것. 개발에서만 JPA `ddl-auto: update`에 의존하는 경우, Python 모델과 드리프트 주의.
- **Redis**: Worker 기본 포트는 `.env`의 `REDIS_PORT`와 Compose 매핑을 맞출 것 (`6378` vs `6379` 등).

### 3.7 체크리스트

- [ ] Spring·Worker가 동일 DB명·유저·호스트/포트를 사용하는가  
- [ ] Compose 호스트 포트와 `POSTGRES_PORT`가 일치하는가  
- [ ] 스키마·ENUM이 `init-db.sql` / ORM과 맞는가  
- [ ] Spring 기동 후 테이블 존재 여부 확인 (`\dt`, 메타 조회)  

---

## 4. 이 레포에서 Docker Compose로 PostgreSQL·Redis

### 4.1 실행

```bash
docker-compose up -d postgres redis
# 또는
docker-compose up -d
```

```bash
docker-compose ps
docker-compose logs postgres
docker-compose logs redis
```

### 4.2 접속

```bash
docker exec -it ai_vibe_postgres psql -U postgres -d ai_vibe_coding_test
```

호스트에서:

```bash
psql -h localhost -p 5432 -U postgres -d ai_vibe_coding_test
```

스키마·테이블:

```sql
\dn
\dt ai_vibe_coding_test.*
```

### 4.3 스키마·ENUM·ORM

- 전체 스키마·변경 이력: `docs/Schema_Reference_Index.md`, `docs/DB_Schema_Changes.md`, `scripts/init-db.sql`
- Enum·테이블 설계를 코드에 반영할 때는 `app/infrastructure/persistence/models/` 를 기준으로 합니다.

### 4.4 Spring과 테이블 공유 시

- Spring이 스키마를 생성·변경할 수 있음 — Worker는 팀 정책에 따라 읽기 위주 또는 제한된 쓰기.
- Python SQLAlchemy Enum은 DB ENUM과 이름·값이 맞아야 합니다.

### 4.5 저장·통합 테스트

`test_scripts/` 등에서 Docker PG가 떠 있는지 확인한 뒤 스크립트를 실행합니다. 자세한 절차는 기존 테스트 가이드를 따릅니다.

---

## 5. 관련 문서

| 문서 | 설명 |
|------|------|
| `docs/Complete_DB_Setup_Guide.md` | DB 전체 기동 흐름 |
| `docs/Local_DB_Setup_Guide.md` | 로컬 PostgreSQL 초기 설정 |
| `docs/Local_DB_Migration_Guide.md` | Docker ↔ 로컬 덤프/복원 |
| `docs/Quick_DB_Guide.md` | 짧은 DB 작업 메모 |
| `docs/Test_Execution_Guide.md` | 통합 테스트 실행 순서 |
