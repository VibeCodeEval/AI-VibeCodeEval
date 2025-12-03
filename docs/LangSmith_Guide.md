# LangSmith 통합 가이드

## 📋 목차

1. [개요](#개요)
2. [설정](#설정)
3. [사용 방법](#사용-방법)
4. [구현 구조](#구현-구조)
5. [추적 확인](#추적-확인)
6. [무료 티어 정보](#무료-티어-정보)

---

## 개요

LangSmith는 LangChain/LangGraph 애플리케이션의 추적 및 디버깅을 위한 플랫폼입니다. 이 프로젝트에서는 **6.X 평가 노드**에서 사용자 대화 내역과 평가 결과를 추적합니다.

### 추적 대상
- **6a. Holistic Flow**: Chaining 전략 평가
- **6c. Code Performance**: 코드 성능 평가
- **6d. Code Correctness**: 코드 정확성 평가

### 추적 목적
- 사용자 대화 흐름 분석
- 평가 프로세스 추적
- LLM 응답 품질 모니터링

---

## 설정

### 1. API Key 발급

1. [LangSmith 웹사이트](https://smith.langchain.com/) 접속
2. 계정 생성 및 로그인
3. Settings → API Keys → Create API Key
4. 키 이름과 만료 기간 설정 후 생성
5. **⚠️ 중요**: 생성된 API Key는 한 번만 표시되므로 반드시 복사하여 보관

**공식 문서**: https://docs.langchain.com/langsmith/create-account-api-key

### 2. 환경 변수 설정

**위치**: 프로젝트 루트의 `.env` 파일

```bash
# LangSmith 설정 (개발 환경에서 사용)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key_here
LANGCHAIN_PROJECT=langgraph-eval-dev
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

### 3. 설정 파일

**위치**: `app/core/config.py`

```python
# LangSmith 설정 (개발 환경에서 사용)
LANGCHAIN_TRACING_V2: bool = False  # 개발 환경에서만 True로 설정
LANGCHAIN_API_KEY: Optional[str] = None  # LangSmith API Key
LANGCHAIN_PROJECT: str = "langgraph-eval-dev"  # LangSmith 프로젝트 이름
LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"  # LangSmith API 엔드포인트
```

---

## 사용 방법

### 1. 환경 변수 기반 (기본)

환경 변수 `LANGCHAIN_TRACING_V2=true`로 설정하면 자동으로 추적됩니다.

```bash
# .env 파일
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_api_key
```

### 2. State 기반 제어 (코드에서 제어)

State의 `enable_langsmith_tracing` 값으로 추적을 제어할 수 있습니다.

#### 우선순위
1. **State의 `enable_langsmith_tracing`** (명시적 설정)
2. **환경 변수 `LANGCHAIN_TRACING_V2`** (기본값)

#### 활성화
```python
from app.domain.langgraph.graph import get_initial_state

state = get_initial_state(
    session_id="test-session",
    exam_id=1,
    participant_id=1,
    spec_id=1,
    human_message="테스트 메시지"
)
state["enable_langsmith_tracing"] = True  # 추적 활성화
```

#### 비활성화
```python
state["enable_langsmith_tracing"] = False  # 추적 비활성화
```

#### 환경 변수 사용
```python
state["enable_langsmith_tracing"] = None  # 환경 변수 사용
```

### 3. 테스트에서 사용

테스트에서는 기본적으로 LangSmith 추적이 **비활성화**됩니다 (토큰 절약).

```python
from tests.test_langsmith_tracing import create_test_state

# 기본적으로 비활성화
state = create_test_state()

# 필요시 활성화
state = create_test_state(enable_langsmith_tracing=True)
```

---

## 구현 구조

### 파일 구조

```
app/domain/langgraph/nodes/holistic_evaluator/
├── __init__.py              # Export 관리
├── langsmith_utils.py       # LangSmith 유틸리티 (상수, 헬퍼 함수)
├── utils.py                 # LLM 유틸리티
├── flow.py                  # 6a: Holistic Flow 평가
├── performance.py           # 6c: Code Performance 평가
├── correctness.py            # 6d: Code Correctness 평가
└── scores.py                # 6b, 7: 점수 집계
```

### 상수 정의

**`langsmith_utils.py`**:
```python
# 추적 태그
TAG_EVALUATION = "evaluation"
TAG_NODE_6A = "node_6a"
TAG_NODE_6C = "node_6c"
TAG_NODE_6D = "node_6d"
TAG_HOLISTIC = "holistic"
TAG_CHAINING = "chaining"
TAG_PERFORMANCE = "performance"
TAG_CORRECTNESS = "correctness"
TAG_CODE = "code"

# 노드별 추적 이름
TRACE_NAME_HOLISTIC_FLOW = "eval_holistic_flow"
TRACE_NAME_CODE_PERFORMANCE = "eval_code_performance"
TRACE_NAME_CODE_CORRECTNESS = "eval_code_correctness"

# 노드별 태그 설정
NODE_TAGS = {
    TRACE_NAME_HOLISTIC_FLOW: [TAG_EVALUATION, TAG_NODE_6A, TAG_HOLISTIC, TAG_CHAINING],
    TRACE_NAME_CODE_PERFORMANCE: [TAG_EVALUATION, TAG_NODE_6C, TAG_PERFORMANCE, TAG_CODE],
    TRACE_NAME_CODE_CORRECTNESS: [TAG_EVALUATION, TAG_NODE_6D, TAG_CORRECTNESS, TAG_CODE],
}
```

### 노드 구조

각 노드 파일의 구조:
```python
"""
[구조]
- 상수: 프롬프트 템플릿
- Chain 구성 함수: 평가 Chain 생성
- 내부 구현: 실제 평가 로직
- 외부 래퍼: LangSmith 추적 제어
"""
# ===== 상수 =====
SYSTEM_PROMPT = "..."
WEIGHTS = {...}

# ===== Chain 구성 함수 =====
def prepare_input(...): ...
def format_messages(...): ...
def process_output(...): ...

# ===== 내부 구현 =====
async def _eval_*_impl(...): ...

# ===== 외부 래퍼 =====
async def eval_*(...): ...
```

### 공통 패턴

**`wrap_node_with_tracing()`** 함수로 노드 래핑:
```python
async def eval_holistic_flow(state: MainGraphState) -> Dict[str, Any]:
    wrapped_func = wrap_node_with_tracing(
        node_name=TRACE_NAME_HOLISTIC_FLOW,
        impl_func=_eval_holistic_flow_impl,
        state=state
    )
    return await wrapped_func(state)
```

---

## 추적 확인

### 1. 웹사이트에서 확인

- **URL**: https://smith.langchain.com/
- **프로젝트**: `langgraph-eval-dev`
- **Traces 탭**: 시각적으로 추적 내역 확인

### 2. 터미널에서 확인

```bash
uv run python test_scripts/check_langsmith_traces.py
```

**기능**:
- 최근 추적 내역 조회
- 노드별 추적 조회 (6.X 노드)
- 세션별 추적 조회
- 추적 상세 정보 조회

### 3. 로그 확인

LangSmith 추적 활성화 시:
```python
logger.debug(f"[LangSmith] 6a 노드 추적 활성화 - session_id: {session_id}, 턴 개수: {len(structured_logs)}")
```

---

## 무료 티어 정보

### 기본 제한

LangSmith는 일반적으로 다음과 같은 무료 티어를 제공합니다:

- **Traces**: 월 10,000개 (또는 그 이상)
- **Projects**: 무제한
- **API Calls**: 월 10,000개
- **Data Retention**: 7일 (무료 티어)

### 정확한 제한 사항

정확한 제한 사항은 LangSmith 공식 문서를 확인하세요:
- **LangSmith 웹사이트**: https://smith.langchain.com/
- **가격 정보**: https://docs.langchain.com/langsmith/pricing

### 권장 사항

1. **개발 환경에서만 활성화**: 프로덕션에서는 필요시에만 사용
2. **State 기반 제어**: 테스트 시 추적 비활성화로 토큰 절약
3. **주기적 확인**: 무료 티어 한도 모니터링

---

## 주요 기능

### 1. State 기반 제어
- 환경 변수 변경 없이 코드에서 제어
- 세션별로 다른 추적 설정 가능
- 테스트에서 기본적으로 비활성화

### 2. 상수 중앙화
- LangSmith 관련 상수 통합 관리
- 노드별 태그 자동 관리
- 프롬프트 템플릿 상수화

### 3. 공통 패턴 추출
- `wrap_node_with_tracing()` 함수로 중복 코드 제거
- 일관된 추적 제어

### 4. 유지보수성
- 상수 중앙화로 변경 시 한 곳만 수정
- 명확한 파일 구조
- 확장성 있는 구조

---

## 주의 사항

### 1. 환경 변수 우선순위
- State에 명시적으로 설정하지 않으면 환경 변수 사용
- `None`으로 설정해도 환경 변수 사용

### 2. 테스트 기본값
- 테스트에서는 기본적으로 `False`
- LangSmith 테스트를 위해서는 명시적으로 `True` 설정 필요

### 3. 프로덕션 사용
- 프로덕션에서는 환경 변수로 제어하는 것을 권장
- State 기반 제어는 특수한 경우에만 사용

### 4. 토큰 사용량
- LangSmith 추적은 추가 API 호출을 발생시킬 수 있음
- 테스트 시 불필요한 추적 비활성화로 토큰 절약

---

## 관련 파일

### 설정
- `app/core/config.py`: LangSmith 환경 변수 설정
- `.env`: 환경 변수 파일

### 구현
- `app/domain/langgraph/nodes/holistic_evaluator/langsmith_utils.py`: 유틸리티 함수
- `app/domain/langgraph/nodes/holistic_evaluator/flow.py`: 6a 노드
- `app/domain/langgraph/nodes/holistic_evaluator/performance.py`: 6c 노드
- `app/domain/langgraph/nodes/holistic_evaluator/correctness.py`: 6d 노드
- `app/domain/langgraph/states.py`: State 정의

### 테스트
- `tests/test_langsmith_tracing.py`: LangSmith 추적 테스트
- `test_scripts/check_langsmith_traces.py`: 추적 확인 스크립트

---

## 참고 자료

- **LangSmith 공식 문서**: https://docs.smith.langchain.com/
- **API Key 발급**: https://docs.langchain.com/langsmith/create-account-api-key
- **가격 정보**: https://docs.langchain.com/langsmith/pricing
- **LangSmith 웹사이트**: https://smith.langchain.com/

