# 토큰 사용량 조회 API 가이드

## 📋 개요

사용자 채팅 시 사용된 토큰 수와 평가에 사용된 토큰 수를 분리하여 조회하고, Core 백엔드로 전달할 수 있는 API를 제공합니다.

---

## 🎯 목적

1. **토큰 사용량 추적**: 채팅 검사(Intent Analyzer, Writer LLM)와 평가(Turn Evaluator, Holistic Evaluator) 토큰을 분리 추적
2. **Core 백엔드 전달**: 프롬프트/컴플리션/합계 사용량을 Core로 리턴
3. **비용 관리**: LLM 사용 비용을 정확히 추적하고 관리

---

## 📡 API 엔드포인트

### 1. 채팅 메시지 전송 (토큰 포함)

**엔드포인트**: `POST /api/chat/message`

**요청 예시**:
```json
{
  "session_id": "session-123",
  "exam_id": 1,
  "participant_id": 100,
  "spec_id": 1,
  "message": "DP에 대해 설명해줘"
}
```

**응답 예시**:
```json
{
  "session_id": "session-123",
  "turn": 1,
  "ai_message": "...",
  "is_submitted": false,
  "error": false,
  "error_message": null,
  "chat_tokens": {
    "prompt_tokens": 1262,
    "completion_tokens": 966,
    "total_tokens": 2228
  },
  "eval_tokens": null,
  "total_tokens": {
    "prompt_tokens": 1262,
    "completion_tokens": 966,
    "total_tokens": 2228
  }
}
```

**토큰 필드 설명**:
- `chat_tokens`: 채팅 검사 토큰 (Intent Analyzer + Writer LLM)
- `eval_tokens`: 평가 토큰 (Turn Evaluator + Holistic Evaluator) - 백그라운드 평가 완료 후 포함
- `total_tokens`: 전체 토큰 합계 (chat + eval) - **Core 백엔드 전달용**

---

### 2. 토큰 사용량 조회 API

**엔드포인트**: `GET /api/chat/tokens?session_id={session_id}`

**요청 예시**:
```bash
GET /api/chat/tokens?session_id=session-123
```

**응답 예시**:
```json
{
  "session_id": "session-123",
  "chat_tokens": {
    "prompt_tokens": 1262,
    "completion_tokens": 966,
    "total_tokens": 2228
  },
  "eval_tokens": {
    "prompt_tokens": 2000,
    "completion_tokens": 3000,
    "total_tokens": 5000
  },
  "total_tokens": {
    "prompt_tokens": 3262,
    "completion_tokens": 3966,
    "total_tokens": 7228
  },
  "error": false,
  "error_message": null
}
```

**응답 필드 설명**:
- `chat_tokens`: 채팅 검사 토큰 사용량
  - `prompt_tokens`: 프롬프트 토큰 수
  - `completion_tokens`: 컴플리션 토큰 수
  - `total_tokens`: 전체 토큰 수
- `eval_tokens`: 평가 토큰 사용량 (백그라운드 평가 완료 후 포함)
- `total_tokens`: 전체 토큰 합계 (chat + eval) - **Core 백엔드 전달용**
- `error`: 에러 발생 여부
- `error_message`: 에러 메시지 (에러 시)

---

## 🔄 Core 백엔드 전달 형식

### 전달 데이터 구조

```json
{
  "chat_tokens": {
    "prompt_tokens": 1262,
    "completion_tokens": 966,
    "total_tokens": 2228
  },
  "eval_tokens": {
    "prompt_tokens": 2000,
    "completion_tokens": 3000,
    "total_tokens": 5000
  },
  "total_tokens": {
    "prompt_tokens": 3262,      // chat.prompt_tokens + eval.prompt_tokens
    "completion_tokens": 3966,  // chat.completion_tokens + eval.completion_tokens
    "total_tokens": 7228        // chat.total_tokens + eval.total_tokens
  }
}
```

### Core 전달 시 주의사항

1. **백그라운드 평가**: `eval_tokens`는 백그라운드로 실행되므로 즉시 반영되지 않을 수 있습니다.
2. **합계 계산**: `total_tokens`는 `chat_tokens`와 `eval_tokens`의 합계입니다.
3. **null 처리**: `eval_tokens`가 `null`인 경우, `total_tokens`는 `chat_tokens`와 동일합니다.

---

## 📊 토큰 분류

### 1. 채팅 검사 토큰 (chat_tokens)

**포함 노드**:
- **Intent Analyzer (2번 노드)**: 의도 분석 및 가드레일 체크
- **Writer LLM (3번 노드)**: AI 답변 생성

**특징**:
- 사용자 채팅 시 즉시 반환
- 실시간으로 추적 가능

### 2. 평가 토큰 (eval_tokens)

**포함 노드**:
- **Turn Evaluator (4번 노드)**: 턴별 평가
  - Intent Analysis
  - 의도별 평가 (Hint/Query, Debugging, Code Review 등)
  - Answer Summary
- **Holistic Evaluator (6번 노드)**: 전체 평가
  - Holistic Flow Evaluation
  - Code Correctness
  - Code Performance

**특징**:
- 백그라운드로 실행되므로 완료 후 조회 가능
- 일반 채팅 시 비동기 실행
- 코드 제출 시 동기 실행

---

## 🔧 구현 세부사항

### 토큰 추적 흐름

1. **노드 실행**: 각 노드에서 LLM 호출
2. **토큰 추출**: `extract_token_usage()` 함수로 토큰 사용량 추출
3. **State 누적**: `accumulate_tokens()` 함수로 State에 누적
4. **반환**: 노드 반환값에 토큰 정보 포함
5. **Core 변환**: `format_tokens_for_core()` 함수로 Core 전달 형식 변환

### 주요 함수

#### `extract_token_usage(response)`
- LLM 응답에서 토큰 사용량 추출
- Gemini API의 `usage_metadata` 지원

#### `accumulate_tokens(state, new_tokens, token_type)`
- State에 토큰 사용량 누적
- `token_type`: "chat" 또는 "eval"

#### `format_tokens_for_core(chat_tokens, eval_tokens)`
- Core 백엔드 전달 형식으로 변환
- `total_tokens` 자동 계산

---

## 📝 사용 예시

### Python 예시

```python
import requests

# 1. 채팅 메시지 전송
response = requests.post(
    "http://localhost:8000/api/chat/message",
    json={
        "session_id": "session-123",
        "exam_id": 1,
        "participant_id": 100,
        "spec_id": 1,
        "message": "DP에 대해 설명해줘"
    }
)

result = response.json()
print(f"Chat tokens: {result['chat_tokens']}")
print(f"Total tokens: {result['total_tokens']}")

# 2. 토큰 조회 (백그라운드 평가 완료 후)
import time
time.sleep(10)  # 백그라운드 평가 완료 대기

response = requests.get(
    "http://localhost:8000/api/chat/tokens",
    params={"session_id": "session-123"}
)

result = response.json()
print(f"Chat tokens: {result['chat_tokens']}")
print(f"Eval tokens: {result['eval_tokens']}")
print(f"Total tokens: {result['total_tokens']}")

# 3. Core 백엔드로 전달
core_data = {
    "chat_tokens": result["chat_tokens"],
    "eval_tokens": result["eval_tokens"],
    "total_tokens": result["total_tokens"]
}
# Core API로 전달
```

---

## ⚠️ 주의사항

1. **백그라운드 평가**: `eval_tokens`는 백그라운드로 실행되므로 완료까지 시간이 걸릴 수 있습니다.
2. **세션 유지**: 토큰 정보는 Redis에 저장되므로 세션이 유지되어야 합니다.
3. **null 처리**: `eval_tokens`가 `null`인 경우, `total_tokens`는 `chat_tokens`와 동일합니다.

---

## 🔗 관련 문서

- [토큰 추적 구현 가이드](./Token_Tracking_Implementation_Guide.md)
- [토큰 추적 테스트 결과](./Token_Tracking_Test_Results.md)
- [LLM Factory Pattern 가이드](./LLM_Factory_Pattern_Guide.md)

---

## 📚 참고 코드

- 토큰 추적 유틸리티: `app/domain/langgraph/utils/token_tracking.py`
- 토큰 조회 API: `app/presentation/api/routes/chat.py` (GET /api/chat/tokens)
- 토큰 스키마: `app/presentation/schemas/token.py`


