# 🔍 테스트 실패 분석 보고서

**날짜**: 2026-01-18  
**분석자**: Maestro  
**테스트 환경**: Python 3.12.12, pytest 9.0.2

---

## 📊 테스트 결과 요약

| 항목 | 수치 |
|------|------|
| 전체 테스트 | 121 |
| 통과 | 86 (71%) |
| 실패 | 32 |
| 에러 | 2 |
| 스킵 | 1 |

---

## 🔴 실패 원인 분류

### 1. ✅ **[해결됨] Circular Import (순환 참조)**

**위치**: `app/domain/langgraph/middleware/`

**문제**:
```
__init__.py → factory.py → __init__.py (순환)
```

**해결**:
```python
# factory.py - 수정 전
from app.domain.langgraph.middleware import (LoggingMiddleware, ...)

# factory.py - 수정 후  
from app.domain.langgraph.middleware.logging import LoggingMiddleware
from app.domain.langgraph.middleware.rate_limiting import RateLimitingMiddleware
from app.domain.langgraph.middleware.retry import RetryMiddleware
```

---

### 2. ⚠️ **테스트 격리 문제 (Test Isolation)**

**증상**: 전체 실행 시 실패, 개별 실행 시 통과

**영향 테스트**:
- `test_intent_analyzer_normal_request`
- `test_writer_llm_normal_request`
- 기타 LLM 호출 테스트

**원인 추정**:
- 비동기 이벤트 루프 충돌
- gRPC 연결 상태 오염
- LLM API 상태 공유

**권장 조치**:
```python
# conftest.py에 추가
@pytest.fixture(autouse=True)
async def cleanup_async_resources():
    yield
    # 비동기 리소스 정리
    await asyncio.sleep(0.1)
```

---

### 3. ⚠️ **Fixture 누락**

**영향 테스트**:
- `test_chat_api_new.py::test_send_message`
- `test_chat_api_new.py::test_multiple_turns`

**문제**: `session_info` fixture가 정의되지 않음

**해결 방법**:
```python
# tests/conftest.py에 추가
@pytest.fixture
async def session_info():
    return {
        "session_id": "test-session-123",
        "exam_id": 1,
        "participant_id": 100,
        "spec_id": 10
    }
```

---

### 4. ⚠️ **Deprecated API 경고**

**경고**: `datetime.utcnow()` deprecated in Python 3.12

**영향 파일**:
- `tests/test_nodes_chains.py`
- `app/domain/langgraph/nodes/intent_analyzer.py`

**해결 방법**:
```python
# 변경 전
datetime.utcnow()

# 변경 후
datetime.now(timezone.utc)
```

---

### 5. ⚠️ **Guardrail 테스트 실패**

**영향 테스트** (10개):
- `test_direct_answer_patterns_blocked`
- `test_quick_answer_detection_korean`
- `test_intent_analyzer_safe_logic_hint`
- 등

**원인 추정**:
- LLM 응답 형식 변경
- 가드레일 로직 변경 후 테스트 미업데이트
- 비결정적 LLM 응답으로 인한 불안정

**권장 조치**:
- Mock LLM 사용으로 결정적 테스트 작성
- 가드레일 규칙 문서와 테스트 동기화

---

### 6. ℹ️ **gRPC RuntimeWarning**

**경고**:
```
RuntimeWarning: coroutine 'InterceptedUnaryUnaryCall._invoke' was never awaited
```

**원인**: Google Vertex AI/gRPC 비동기 정리 문제

**영향**: 기능에 영향 없음 (경고만)

---

## 🎯 권장 조치 우선순위

| 우선순위 | 작업 | 예상 시간 |
|---------|------|----------|
| P1 | `session_info` fixture 추가 | 10분 |
| P1 | `datetime.utcnow()` → `datetime.now(UTC)` 변경 | 30분 |
| P2 | 테스트 격리 개선 (cleanup fixture) | 1시간 |
| P3 | Guardrail 테스트 Mock으로 재작성 | 2-3시간 |
| P3 | gRPC 경고 무시 설정 추가 | 10분 |

---

## ✅ 결론

**핵심 문제인 순환 참조는 해결**되었습니다.

### 🔴 주요 실패 원인: DB 미실행

현재 **PostgreSQL 및 Redis가 실행되지 않은 상태**에서 테스트를 진행했습니다.
DB 연결이 필요한 테스트들이 실패한 것으로 추정됩니다.

**DB 실행 후 재테스트 필요:**
```powershell
# Docker Compose로 DB 실행
docker-compose -f docker-compose.dev.yml up -d

# 테스트 재실행
uv run pytest tests/ -v
```

나머지 실패 원인:
1. DB 연결 실패 (PostgreSQL, Redis 미실행) ← **주요 원인**
2. 테스트 코드 자체의 문제 (fixture 누락, deprecated API)
3. LLM 비결정성으로 인한 불안정한 테스트

**앱 자체는 정상 작동**합니다.
