# API KEY 위치 가이드

## 📍 API KEY 정의 위치

### 1. 설정 파일 (정의)
**파일**: `app/core/config.py`

```python
class Settings(BaseSettings):
    # LLM API 설정
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    
    # Judge0 설정
    JUDGE0_API_KEY: Optional[str] = None
    
    # Spring Boot 콜백 설정
    SPRING_API_KEY: Optional[str] = None
    
    # LangSmith 설정
    LANGCHAIN_API_KEY: Optional[str] = None
```

**접근 방법**:
```python
from app.core.config import settings

api_key = settings.GEMINI_API_KEY
```

---

### 2. 환경 변수 파일 (실제 값)
**파일**: `.env` (또는 `env.example`)

```env
# LLM API 설정
GEMINI_API_KEY=your_gemini_api_key_here
# OPENAI_API_KEY=your_openai_api_key_here

# Judge0 설정
JUDGE0_API_URL=http://localhost:2358
# JUDGE0_API_KEY=

# Spring Boot 콜백 설정
SPRING_CALLBACK_URL=http://localhost:8080/api/ai/callback
# SPRING_API_KEY=

# LangSmith 설정
LANGCHAIN_TRACING_V2=false
# LANGCHAIN_API_KEY=your_langsmith_api_key_here
```

**주의**: `.env` 파일은 `.gitignore`에 포함되어 있어야 합니다.

---

## 🔑 각 API KEY 사용 위치

### 1. GEMINI_API_KEY
**사용 위치**:
- `app/domain/langgraph/nodes/intent_analyzer.py`
- `app/domain/langgraph/nodes/writer.py`
- `app/domain/langgraph/nodes/system_nodes.py`
- `app/domain/langgraph/nodes/holistic_evaluator/utils.py`
- `app/domain/langgraph/nodes/turn_evaluator/utils.py`
- `app/domain/langgraph/utils/llm_factory.py`

**사용 방법**:
```python
from app.core.config import settings

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=settings.GEMINI_API_KEY,
)
```

---

### 2. JUDGE0_API_KEY
**사용 위치**:
- `app/infrastructure/judge0/client.py`

**사용 방법**:
```python
from app.core.config import settings

client = Judge0Client(
    api_url=settings.JUDGE0_API_URL,
    api_key=settings.JUDGE0_API_KEY  # 선택사항
)
```

**헤더에 포함**:
```python
headers = {
    "Content-Type": "application/json",
}
if self.api_key:
    headers["X-Auth-Token"] = self.api_key
```

---

### 3. SPRING_API_KEY
**사용 위치**:
- `app/application/services/callback_service.py`
- `app/core/security.py` (API 인증)

**사용 방법**:
```python
from app.core.config import settings

# CallbackService에서
self.api_key = settings.SPRING_API_KEY

# 헤더에 포함
if self.api_key:
    headers["X-API-Key"] = self.api_key
```

**API 인증**:
```python
# app/core/security.py
async def verify_spring_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    if settings.SPRING_API_KEY is None:
        return True  # API Key 검증 비활성화
    
    if x_api_key is None or x_api_key != settings.SPRING_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
```

---

### 4. LANGCHAIN_API_KEY (LangSmith)
**사용 위치**:
- `app/domain/langgraph/nodes/holistic_evaluator/langsmith_utils.py`

**사용 방법**:
```python
from app.core.config import settings

# LangSmith 추적 활성화 확인
if settings.LANGCHAIN_TRACING_V2 and settings.LANGCHAIN_API_KEY:
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
```

---

### 5. OPENAI_API_KEY
**사용 위치**:
- `app/domain/langgraph/utils/llm_factory.py` (선택사항)

**사용 방법**:
```python
from app.core.config import settings

llm = ChatOpenAI(
    model="gpt-4",
    api_key=settings.OPENAI_API_KEY,
)
```

---

## 📝 요약

| API KEY | 설정 파일 | 환경 변수 파일 | 사용 위치 |
|---------|----------|--------------|----------|
| **GEMINI_API_KEY** | `app/core/config.py` | `.env` | LLM 노드들 |
| **JUDGE0_API_KEY** | `app/core/config.py` | `.env` | `app/infrastructure/judge0/client.py` |
| **SPRING_API_KEY** | `app/core/config.py` | `.env` | `app/application/services/callback_service.py` |
| **LANGCHAIN_API_KEY** | `app/core/config.py` | `.env` | `app/domain/langgraph/nodes/holistic_evaluator/langsmith_utils.py` |
| **OPENAI_API_KEY** | `app/core/config.py` | `.env` | `app/domain/langgraph/utils/llm_factory.py` |

---

## 🔧 설정 방법

### 1. `.env` 파일 생성
```bash
# env.example을 복사
cp env.example .env
```

### 2. API KEY 입력
```env
GEMINI_API_KEY=your_actual_api_key_here
JUDGE0_API_KEY=your_judge0_api_key_here
SPRING_API_KEY=your_spring_api_key_here
LANGCHAIN_API_KEY=your_langsmith_api_key_here
```

### 3. 환경 변수로도 설정 가능
```bash
export GEMINI_API_KEY=your_api_key_here
export JUDGE0_API_KEY=your_judge0_api_key_here
```

---

## ⚠️ 주의사항

1. **`.env` 파일은 `.gitignore`에 포함되어야 함**
2. **프로덕션 환경에서는 환경 변수로 설정 권장**
3. **API KEY는 절대 코드에 하드코딩하지 말 것**
4. **Judge0 API KEY는 선택사항** (로컬 Judge0 서버 사용 시 불필요)

---

## 🔍 현재 상태 확인

### 설정 파일 확인
```python
from app.core.config import settings

print(f"GEMINI_API_KEY: {'설정됨' if settings.GEMINI_API_KEY else '미설정'}")
print(f"JUDGE0_API_KEY: {'설정됨' if settings.JUDGE0_API_KEY else '미설정'}")
print(f"SPRING_API_KEY: {'설정됨' if settings.SPRING_API_KEY else '미설정'}")
print(f"LANGCHAIN_API_KEY: {'설정됨' if settings.LANGCHAIN_API_KEY else '미설정'}")
```

### 헬스 체크 API
```bash
curl http://localhost:8000/api/health
```

응답에서 `components.llm`이 `true`면 GEMINI_API_KEY가 설정된 것입니다.

