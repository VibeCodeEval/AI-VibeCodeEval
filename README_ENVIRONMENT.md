# 환경 설정 빠른 가이드

## 🚀 빠른 시작

### 로컬 개발 환경

```bash
# 1. .env 파일 생성
cp env.example .env

# 2. .env 파일 편집 (로컬 PostgreSQL 정보 입력)
# POSTGRES_HOST=localhost
# POSTGRES_PORT=5432
# POSTGRES_USER=postgres
# POSTGRES_PASSWORD=postgres

# 3. 로컬 DB 사용하여 실행
docker-compose -f docker-compose.dev.yml up -d
```

### 프로덕션 배포 환경

```bash
# 1. 환경 변수 설정 (또는 .env.prod 파일 사용)
export POSTGRES_HOST=your-production-db-host.com
export POSTGRES_USER=your_db_user
export POSTGRES_PASSWORD=your_db_password
export POSTGRES_DB=ai_vibe_coding_test

# 2. 배포 실행
docker-compose -f docker-compose.prod.yml up -d
```

## 📁 파일 구조

```
.env              # 로컬 개발 환경 (Git에 포함하지 않음)
.env.prod         # 프로덕션 환경 (Git에 포함하지 않음)
env.example       # 로컬 환경 예시 (Git에 포함)
env.prod.example  # 프로덕션 환경 예시 (Git에 포함)

docker-compose.yml      # 기본 (Docker PostgreSQL 포함)
docker-compose.dev.yml  # 로컬 DB 사용 (개발 환경)
docker-compose.prod.yml # 프로덕션 배포용
```

## 🔧 환경 변수 우선순위

1. **환경 변수** (최우선) - `export POSTGRES_HOST=...`
2. **.env 파일** - 프로젝트 루트의 `.env`
3. **기본값** - `app/core/config.py`의 기본값

## 📚 상세 가이드

자세한 내용은 [Environment_Separation_Guide.md](./docs/Environment_Separation_Guide.md)를 참조하세요.

