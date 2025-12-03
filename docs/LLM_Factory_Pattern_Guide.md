# LLM Factory Pattern 가이드

## 📋 개요

여러 LLM 타입을 지원하고, 노드별 설정을 관리하는 Factory Pattern 구현 가이드입니다.

**목적**:
- 여러 LLM 타입 지원 (Gemini, OpenAI, Anthropic 등)
- 노드별로 다른 LLM 설정 사용 가능
- 인스턴스 재사용 (싱글톤 패턴)
- 확장 가능한 구조

---

## 🏗️ 구조

### 파일 위치
- **구현**: `app/domain/langgraph/utils/llm_factory.py`
- **상태**: 구현 완료, 선택적 사용 가능

### 현재 상태
- ✅ Factory Pattern 구현 완료
- ⚠️ 아직 노드에 적용하지 않음 (선택적 사용)
- ✅ 각 노드는 독립적인 `get_llm()` 함수 사용 중

---

## 🔧 사용 방법

### 기본 사용 (노드 기본 설정)

```python
from app.domain.langgraph.utils.llm_factory import get_llm

# 노드 기본 설정 사용
llm = get_llm("intent_analyzer")
# → temperature=0.3, model=DEFAULT_LLM_MODEL

llm = get_llm("turn_evaluator")
# → temperature=0.1, model=DEFAULT_LLM_MODEL

llm = get_llm("writer")
# → temperature=settings.LLM_TEMPERATURE, model=DEFAULT_LLM_MODEL
```

### 커스텀 설정

```python
# 온도 변경
llm = get_llm("writer", temperature=0.9)

# 최대 토큰 수 설정
llm = get_llm("writer", max_tokens=2000)

# 모델 변경
llm = get_llm("writer", model="gemini-2.0-flash-exp")
```

### 다른 LLM 타입 사용

```python
# OpenAI 사용
llm = get_llm("writer", llm_type="openai", model="gpt-4")

# Anthropic 사용 (구현 필요)
# llm = get_llm("writer", llm_type="anthropic", model="claude-3-opus-20240229")
```

---

## 📊 노드별 기본 설정

### 설정 테이블

| 노드 이름 | LLM 타입 | Temperature | Model | Max Tokens |
|----------|---------|-------------|-------|------------|
| `intent_analyzer` | gemini | 0.3 | DEFAULT_LLM_MODEL | 기본값 |
| `writer` | gemini | settings.LLM_TEMPERATURE | DEFAULT_LLM_MODEL | settings.LLM_MAX_TOKENS |
| `turn_evaluator` | gemini | 0.1 | DEFAULT_LLM_MODEL | 기본값 |
| `holistic_evaluator` | gemini | 0.1 | DEFAULT_LLM_MODEL | 기본값 |
| `system_nodes` | gemini | 0.3 | DEFAULT_LLM_MODEL | 기본값 |

### 설정 정의 위치

```python
# app/domain/langgraph/utils/llm_factory.py
NODE_DEFAULT_CONFIGS: Dict[str, Dict[str, Any]] = {
    "intent_analyzer": {
        "llm_type": "gemini",
        "temperature": 0.3,
        "model": settings.DEFAULT_LLM_MODEL,
    },
    "writer": {
        "llm_type": "gemini",
        "temperature": getattr(settings, "LLM_TEMPERATURE", 0.7),
        "model": settings.DEFAULT_LLM_MODEL,
        "max_tokens": getattr(settings, "LLM_MAX_TOKENS", None),
    },
    # ... 기타 노드 설정
}
```

---

## 🔄 마이그레이션 가이드

### 현재 방식 (독립 함수)

```python
# turn_evaluator/utils.py
def get_llm():
    """LLM 인스턴스 생성"""
    return ChatGoogleGenerativeAI(
        model=settings.DEFAULT_LLM_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.1,
    )
```

### 새로운 방식 (Factory Pattern)

```python
# turn_evaluator/utils.py
from app.domain.langgraph.utils.llm_factory import get_llm as get_llm_factory

def get_llm():
    """LLM 인스턴스 생성 (Factory Pattern 사용)"""
    return get_llm_factory("turn_evaluator")
```

### 점진적 마이그레이션

1. **단계 1**: Factory Pattern 구현 (완료)
2. **단계 2**: 테스트 노드에 적용
3. **단계 3**: 모든 노드에 적용
4. **단계 4**: 기존 독립 함수 제거

---

## 🎯 장단점 비교

### 현재 방식 (독립 함수)

**장점**:
- ✅ 코드가 명확하고 이해하기 쉬움
- ✅ 각 노드가 독립적으로 관리됨
- ✅ 노드별로 다른 설정 사용 가능
- ✅ 변경 영향 범위가 작음

**단점**:
- ⚠️ 여러 LLM 타입 전환 시 각 노드 수정 필요
- ⚠️ 중앙 집중식 설정 관리 어려움

### Factory Pattern

**장점**:
- ✅ 여러 LLM 타입을 쉽게 전환 가능
- ✅ 중앙 집중식 설정 관리
- ✅ 인스턴스 재사용 (싱글톤)
- ✅ 확장 가능한 구조

**단점**:
- ⚠️ 코드 변경 필요 (각 노드의 `get_llm()` 호출 수정)
- ⚠️ 설정이 중앙에 집중되어 노드별 독립성 감소

---

## 📝 권장 사항

### 옵션 1: 현재 구조 유지 (권장)

**이유**:
- 각 노드가 독립적으로 관리되어 유지보수가 쉬움
- 코드가 명확하고 이해하기 쉬움
- 노드별로 다른 설정 사용 가능
- Factory Pattern은 필요 시에만 도입

**적용 시점**:
- 여러 LLM 타입을 실제로 사용해야 할 때
- 중앙 집중식 설정 관리가 필요할 때

### 옵션 2: Factory Pattern으로 전환

**이유**:
- 여러 LLM 타입을 쉽게 전환하고 싶을 때
- 중앙 집중식 설정 관리가 필요할 때
- 인스턴스 재사용을 통한 최적화

**적용 시점**:
- 프로젝트 초기 단계
- 여러 LLM 타입을 실제로 사용하기 시작할 때

---

## 🔍 구현 세부사항

### 캐싱 메커니즘

```python
# LLM 인스턴스 캐시 (노드별 + 설정별)
_llm_cache: Dict[str, Any] = {}

def _create_cache_key(node_name: str, llm_type: str, **kwargs) -> str:
    """캐시 키 생성"""
    config_str = "_".join(f"{k}:{v}" for k, v in sorted(kwargs.items()) if v is not None)
    return f"{node_name}_{llm_type}_{config_str}"

def get_llm(node_name: str, **kwargs):
    """노드별 LLM 인스턴스 생성 (싱글톤 패턴)"""
    cache_key = _create_cache_key(node_name, **final_config)
    
    # 캐시에 있으면 재사용
    if cache_key in _llm_cache:
        return _llm_cache[cache_key]
    
    # 새 LLM 인스턴스 생성 및 캐싱
    llm = _create_llm(**final_config)
    _llm_cache[cache_key] = llm
    return llm
```

### LLM 타입별 생성 함수

```python
def _create_gemini_llm(**kwargs) -> ChatGoogleGenerativeAI:
    """Gemini LLM 생성"""
    return ChatGoogleGenerativeAI(
        model=kwargs.get("model", settings.DEFAULT_LLM_MODEL),
        google_api_key=kwargs.get("api_key", settings.GEMINI_API_KEY),
        temperature=kwargs.get("temperature", 0.3),
        max_output_tokens=kwargs.get("max_tokens"),
    )

def _create_openai_llm(**kwargs) -> ChatOpenAI:
    """OpenAI LLM 생성"""
    return ChatOpenAI(
        model=kwargs.get("model", "gpt-4"),
        api_key=kwargs.get("api_key", getattr(settings, "OPENAI_API_KEY", None)),
        temperature=kwargs.get("temperature", 0.3),
        max_tokens=kwargs.get("max_tokens"),
    )
```

---

## 🧪 테스트

### 캐시 확인

```python
from app.domain.langgraph.utils.llm_factory import get_llm, get_cache_info

# 첫 호출
llm1 = get_llm("intent_analyzer")

# 두 번째 호출 (캐시에서 재사용)
llm2 = get_llm("intent_analyzer")

# 같은 인스턴스인지 확인
assert llm1 is llm2  # True

# 캐시 정보 확인
cache_info = get_cache_info()
print(cache_info)  # {"cache_size": 1, "cached_keys": [...]}
```

### 캐시 초기화

```python
from app.domain.langgraph.utils.llm_factory import clear_llm_cache

# 캐시 초기화 (테스트용)
clear_llm_cache()
```

---

## 📚 참고 자료

- [LLM Factory 구현](../app/domain/langgraph/utils/llm_factory.py)
- [LLM 인스턴스 관리 가이드](./LLM_Instance_Management_Guide.md)


