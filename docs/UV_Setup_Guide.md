# 🚀 uv 환경 설정 가이드

> uv는 Rust로 작성된 빠른 Python 패키지 관리자입니다. pip보다 10-100배 빠르며, 의존성 해결도 더 정확합니다.

## 📋 목차

1. [uv 설치](#uv-설치)
2. [프로젝트 설정](#프로젝트-설정)
3. [주요 명령어](#주요-명령어)
4. [의존성 관리](#의존성-관리)
5. [문제 해결](#문제-해결)

---

## 🔧 uv 설치

### Windows

**PowerShell 사용 (권장)**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**수동 설치**
1. [uv 공식 사이트](https://github.com/astral-sh/uv)에서 최신 릴리스 다운로드
2. PATH에 추가

### Linux / macOS

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### pip로 설치 (모든 플랫폼)

```bash
pip install uv
```

### 설치 확인

```bash
uv --version
```

---

## 📦 프로젝트 설정

### 1. 저장소 클론

```bash
git clone <repository-url>
cd LangGraph_1
```

### 2. Python 버전 확인

프로젝트는 `.python-version` 파일에 Python 버전을 지정합니다:
```
3.10
```

### 3. 의존성 설치

```bash
# 한 번에: Python 설치 + 가상 환경 생성 + 의존성 설치
uv sync
```

이 명령어는 다음을 수행합니다:
- `.python-version` 파일을 읽어 Python 3.10 설치 (없는 경우)
- `.venv` 가상 환경 생성
- `pyproject.toml`과 `uv.lock` 기반으로 의존성 설치

### 4. 환경 변수 설정

```bash
# .env 파일 생성
cp env.example .env

# .env 파일 편집 (필수 항목)
# - GEMINI_API_KEY
# - POSTGRES_* (PostgreSQL 연결 정보)
# - REDIS_* (Redis 연결 정보)
# - JUDGE0_API_URL
# - SPRING_CALLBACK_URL
```

---

## 🎯 주요 명령어

### 의존성 관리

```bash
# 의존성 설치/업데이트
uv sync                    # pyproject.toml 기반 의존성 설치
uv sync --upgrade          # 모든 패키지를 최신 버전으로 업그레이드
uv sync --dev              # 개발 의존성 포함 설치

# 특정 패키지 추가
uv add <package>           # 패키지 추가 (pyproject.toml 자동 업데이트)
uv add <package>@<version>  # 특정 버전 추가
uv add --dev <package>     # 개발 의존성으로 추가

# 패키지 제거
uv remove <package>        # 패키지 제거 (pyproject.toml 자동 업데이트)
```

### Python 버전 관리

```bash
# Python 버전 설치
uv python install 3.10     # Python 3.10 설치
uv python install 3.12     # Python 3.12 설치

# 설치된 버전 목록
uv python list

# 프로젝트 Python 버전 고정
uv python pin 3.10         # .python-version 파일 업데이트
```

### 스크립트 실행

```bash
# 가상 환경에서 스크립트 실행 (권장)
uv run scripts/run_dev.py
uv run python test_scripts/test_chat_flow.py
uv run pytest tests/

# Python 파일 직접 실행
uv run python app/main.py
```

### 패키지 관리 (pip 호환)

```bash
# 패키지 설치
uv pip install <package>
uv pip install <package>==<version>

# 패키지 목록
uv pip list
uv pip show <package>

# requirements.txt 형식으로 출력
uv pip freeze > requirements.txt
```

### 가상 환경 관리

```bash
# 가상 환경 생성
uv venv                    # .venv 생성 (기본)
uv venv --python 3.10      # 특정 Python 버전으로 생성
uv venv venv-custom        # 커스텀 이름으로 생성

# 가상 환경 활성화 (수동)
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# Linux/Mac
source .venv/bin/activate
```

---

## 📚 의존성 관리

### 프로젝트 의존성 파일

프로젝트는 다음 파일로 의존성을 관리합니다:

1. **`pyproject.toml`**: 프로젝트 메타데이터 및 의존성 정의
   ```toml
   [project]
   requires-python = ">=3.10"
   dependencies = [
       "fastapi>=0.109.0",
       "langgraph>=0.6.11",
       # ...
   ]
   ```

2. **`uv.lock`**: 정확한 버전 고정 (자동 생성)
   - `uv sync` 실행 시 자동 생성/업데이트
   - Git에 포함하여 팀원 간 동일한 버전 보장

3. **`.python-version`**: Python 버전 지정
   ```
   3.10
   ```

### 의존성 추가/제거

```bash
# 패키지 추가 (pyproject.toml 자동 업데이트)
uv add fastapi
uv add "pydantic>=2.12.3"  # 버전 제약 조건 포함

# 개발 의존성 추가
uv add --dev pytest
uv add --dev black

# 패키지 제거
uv remove <package>

# uv.lock 업데이트
uv sync
```

### 의존성 업데이트

```bash
# 모든 패키지 최신 버전으로 업그레이드
uv sync --upgrade

# 특정 패키지만 업그레이드
uv add <package>@latest
uv sync
```

---

## 🔍 문제 해결

### uv가 인식되지 않는 경우

**Windows**
```powershell
# PATH에 추가 (PowerShell)
$env:PATH += ";$env:USERPROFILE\.cargo\bin"
# 또는 재시작
```

**Linux/Mac**
```bash
# PATH에 추가
export PATH="$HOME/.cargo/bin:$PATH"
# 또는 ~/.bashrc 또는 ~/.zshrc에 추가
echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Python 버전 문제

```bash
# Python 버전 재설치
uv python install 3.10

# 프로젝트 Python 버전 확인
cat .python-version

# Python 버전 고정
uv python pin 3.10
```

### 의존성 충돌

```bash
# 의존성 재설치
uv sync --reinstall

# uv.lock 재생성
rm uv.lock
uv sync
```

### 가상 환경 문제

```bash
# 가상 환경 재생성
rm -rf .venv
uv sync
```

### Windows PowerShell 실행 정책 오류

```powershell
# 실행 정책 변경 (관리자 권한)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 또는 uv 설치 스크립트 직접 실행
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

---

## 💡 uv vs pip 비교

| 기능 | uv | pip |
|------|----|----|
| **속도** | 10-100배 빠름 | 기준 |
| **의존성 해결** | 더 정확함 | 기본 |
| **Python 버전 관리** | 내장 | 별도 도구 필요 |
| **가상 환경** | 자동 생성 | 수동 생성 |
| **Lock 파일** | uv.lock (자동) | requirements.txt (수동) |

---

## 📖 추가 자료

- [uv 공식 문서](https://docs.astral.sh/uv/)
- [uv GitHub](https://github.com/astral-sh/uv)
- [pyproject.toml 가이드](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)

---

## ✅ 체크리스트

새 환경에서 프로젝트 설정 시:

- [ ] uv 설치 완료 (`uv --version`)
- [ ] 프로젝트 클론 완료
- [ ] `uv sync` 실행 완료
- [ ] `.env` 파일 생성 및 설정 완료
- [ ] Docker DB 실행 완료 (`docker-compose -f docker-compose.dev.yml up -d`)
- [ ] 서버 실행 확인 (`uv run scripts/run_dev.py`)

---

**Made with 🚀 by AI Vibe Team**



