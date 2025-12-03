# 토큰 추적 테스트 결과

## 📋 테스트 개요

**테스트 날짜**: 2025-12-02  
**테스트 스크립트**: `test_token_tracking_detailed.py`  
**서버 URL**: `http://localhost:8000`

---

## ✅ 완료된 수정사항

### 1. ChatResponse 스키마 수정
- **파일**: `app/presentation/schemas/chat.py`
- **추가 필드**:
  - `chat_tokens: Optional[Dict[str, int]]` - 채팅 검사 토큰 사용량
  - `eval_tokens: Optional[Dict[str, int]]` - 평가 토큰 사용량

### 2. 토큰 추적 구현 완료
- **모든 노드에서 토큰 추적 구현 완료**:
  - 2번 노드: Intent Analyzer ✅
  - 3번 노드: Writer LLM ✅
  - 4번 노드: Turn Evaluator ✅
  - 6번 노드: Holistic Evaluator ✅

---

## ⚠️ 현재 상태

### 테스트 결과
- **스키마 필드**: ✅ 추가 완료
- **API 응답**: ✅ 필드 포함됨
- **토큰 값**: ⚠️ 비어있음 (빈 dict)

### 가능한 원인

1. **토큰 추적이 실제로 작동하지 않음**
   - `extract_token_usage()` 함수가 원본 LLM 응답에서 토큰을 추출하지 못함
   - LLM 응답 형식이 예상과 다를 수 있음

2. **State에 토큰이 저장되지 않음**
   - `accumulate_tokens()` 함수가 State를 제대로 업데이트하지 않음
   - State 저장/로드 과정에서 토큰 정보 손실

3. **서버 로그 확인 필요**
   - EvalService에서 토큰 추적 로그 확인
   - 각 노드에서 토큰 추적 로그 확인

---

## 🔍 디버깅 방법

### 1. 서버 로그 확인

서버 실행 시 다음 로그를 확인:

```
[Intent Analyzer] 토큰 사용량 추출 성공 - prompt: X, completion: Y, total: Z
[Writer LLM] 토큰 사용량 - prompt: X, completion: Y, total: Z
[EvalService] ✅ chat_tokens 발견: {...}
```

### 2. State 직접 확인

Redis에서 State를 직접 확인:

```python
from app.infrastructure.cache.redis_client import redis_client
state = await redis_client.get(f"graph_state:{session_id}")
print(state.get("chat_tokens"))
print(state.get("eval_tokens"))
```

### 3. LLM 응답 구조 확인

원본 LLM 응답의 구조 확인:

```python
# intent_analyzer.py 또는 writer.py에서
raw_response = await llm.ainvoke(messages)
print(f"Response type: {type(raw_response)}")
print(f"Has usage_metadata: {hasattr(raw_response, 'usage_metadata')}")
if hasattr(raw_response, 'usage_metadata'):
    print(f"Usage metadata: {raw_response.usage_metadata}")
```

---

## 📝 다음 단계

1. **서버 로그 확인**
   - 실제로 토큰이 추출되고 있는지 확인
   - 각 노드의 토큰 추적 로그 확인

2. **LLM 응답 구조 확인**
   - Gemini API 응답 형식 확인
   - `usage_metadata` 위치 확인

3. **State 저장 확인**
   - Redis에 토큰 정보가 저장되는지 확인
   - State 로드 시 토큰 정보가 유지되는지 확인

---

## 🧪 테스트 스크립트

### 기본 테스트
```bash
uv run python test_token_tracking_detailed.py
```

### 상세 로그 확인
서버를 실행하고 다음 로그를 확인:
- `[Intent Analyzer] 토큰 사용량 추출 성공`
- `[Writer LLM] 토큰 사용량`
- `[EvalService] ✅ chat_tokens 발견`

---

## 📚 참고 자료

- [토큰 추적 구현 가이드](./Token_Tracking_Implementation_Guide.md)
- [토큰 추적 유틸리티](../app/domain/langgraph/utils/token_tracking.py)


