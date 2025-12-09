# Rubric 분리 및 리팩토링 제안

## 📋 현재 상황 분석

### 1. 4번 노드 (Turn Evaluator) - 하드코딩 현황

**위치**: `app/domain/langgraph/nodes/turn_evaluator/evaluators.py`

**현재 구조**:
- `prepare_evaluation_input_internal()` 함수 내부에 5개 루브릭이 **하드코딩**되어 있음 (68-110줄)
- 모든 평가 유형(`eval_type`)에 대해 동일한 루브릭 사용
- `criteria` 파라미터는 4번 루브릭(규칙)에만 동적으로 삽입됨

**하드코딩된 루브릭**:
1. **명확성 (Clarity)**: 점수 범위별 기준 포함
2. **문제 적절성 (Problem Relevance)**: 점수 범위별 기준 포함
3. **예시 (Examples)**: 점수 범위별 기준 포함
4. **규칙 (Rules)**: `{criteria}` 동적 삽입, 점수 범위별 기준 포함
5. **문맥 (Context)**: 점수 범위별 기준 포함

**문제점**:
- 루브릭 수정 시 코드 직접 수정 필요
- 평가 유형별 커스터마이징 어려움
- 테스트 및 버전 관리 어려움
- 재사용성 낮음

---

### 2. 6번 노드 (Holistic Evaluator) - 하드코딩 현황

**위치**: `app/domain/langgraph/nodes/holistic_evaluator/flow.py`

**현재 구조**:
- `create_holistic_system_prompt()` 함수 내부에 5개 평가 항목이 **하드코딩**되어 있음 (76-98줄)

**하드코딩된 평가 항목**:
1. **문제 분해 (Problem Decomposition)**
2. **피드백 수용성 (Feedback Integration)**
3. **주도성 및 오류 수정 (Proactiveness)**
4. **전략적 탐색 (Strategic Exploration)**
5. **고급 프롬프트 기법 활용 (Advanced Techniques Bonus)**

**문제점**:
- 평가 기준 수정 시 코드 직접 수정 필요
- 평가 항목 추가/삭제 시 유연성 부족

---

## 💡 분리 제안

### 장점 (Pros)

1. **유지보수성 향상**
   - 루브릭 변경 시 별도 파일만 수정
   - 코드와 프롬프트 분리로 가독성 향상

2. **재사용성**
   - 다른 노드나 평가 시스템에서 동일 루브릭 재사용 가능
   - 공통 루브릭 라이브러리 구축 가능

3. **테스트 용이성**
   - 루브릭 단위 테스트 작성 가능
   - 프롬프트 변경 영향 범위 명확화

4. **버전 관리**
   - 루브릭 버전별 관리 가능
   - A/B 테스트 용이

5. **커스터마이징**
   - 평가 유형별 다른 루브릭 적용 가능
   - 문제 유형별 특화 루브릭 구성 가능

6. **DB 저장 가능**
   - 루브릭을 DB에 저장하여 동적 관리 가능
   - 관리자 UI에서 루브릭 수정 가능

### 단점 (Cons)

1. **초기 구현 비용**
   - 파일 구조 설계 필요
   - 기존 코드 리팩토링 필요

2. **복잡도 증가**
   - 파일 수 증가
   - 루브릭 로딩 로직 추가 필요

3. **과도한 추상화 위험**
   - 현재는 단순한 구조로도 충분할 수 있음
   - 오버 엔지니어링 가능성

---

## 🎯 추천 방안

### 옵션 1: 파일 기반 분리 (권장)

**구조**:
```
app/domain/langgraph/nodes/turn_evaluator/
├── evaluators.py
├── rubrics/
│   ├── __init__.py
│   ├── base_rubrics.py          # 공통 루브릭 정의
│   ├── turn_evaluation_rubrics.py  # 4번 노드 전용
│   └── templates.py              # 프롬프트 템플릿
└── ...

app/domain/langgraph/nodes/holistic_evaluator/
├── flow.py
├── rubrics/
│   ├── __init__.py
│   ├── holistic_rubrics.py      # 6번 노드 전용
│   └── templates.py
└── ...
```

**장점**:
- 구현 간단
- 버전 관리 용이
- 테스트 작성 용이

**단점**:
- 코드 배포 시 루브릭 변경 필요

---

### 옵션 2: DB 기반 분리 (장기적)

**구조**:
- `evaluation_rubrics` 테이블 생성
- 관리자 UI에서 루브릭 관리
- 런타임에 DB에서 루브릭 로드

**장점**:
- 코드 배포 없이 루브릭 수정 가능
- 동적 루브릭 관리
- A/B 테스트 용이

**단점**:
- DB 스키마 설계 필요
- 관리자 UI 개발 필요
- 초기 구현 비용 높음

---

### 옵션 3: 하이브리드 (단계적 접근)

**1단계**: 파일 기반 분리 (옵션 1)
- 빠른 구현 및 테스트

**2단계**: DB 기반 전환 (옵션 2)
- 필요 시 점진적 전환

---

## 📝 구체적 구현 제안

### 4번 노드 루브릭 분리 예시

```python
# app/domain/langgraph/nodes/turn_evaluator/rubrics/base_rubrics.py

from typing import Dict, Any

TURN_EVALUATION_RUBRICS = {
    "clarity": {
        "name": "명확성 (Clarity)",
        "description": "요청이 모호하지 않고 구체적인가? (직접적이고 명확하게)",
        "score_ranges": {
            "90-100": "단어 수 20-200개, 문장 수 2-10개, 구체적 값 1개 이상 포함",
            "70-89": "단어 수 10-20개 또는 200-300개, 문장 수 1-2개 또는 10-15개, 구체적 값 포함 여부 불명확",
            "50-69": "단어 수 5-10개 또는 300개 이상, 문장 수 1개 또는 15개 이상",
            "0-49": "단어 수 5개 미만, 문장 수 1개 미만, 매우 모호한 표현"
        }
    },
    "problem_relevance": {
        "name": "문제 적절성 (Problem Relevance)",
        "description": "요청이 문제 특성에 적합한가? 필수 개념을 언급했는가?",
        "score_ranges": {
            "90-100": "기술 용어 3개 이상, 문제 특성에 맞는 알고리즘 명시",
            "70-89": "기술 용어 1-2개, 문제 관련 키워드 언급",
            "50-69": "기술 용어 0-1개, 문제와 관련 있지만 구체적 알고리즘 없음",
            "0-49": "기술 용어 0개, 문제와 무관한 요청"
        }
    },
    # ... 나머지 루브릭
}

def format_rubric_prompt(rubric_key: str, metrics: Dict[str, Any], algorithms_display: str = "알 수 없음") -> str:
    """루브릭을 프롬프트 형식으로 포맷팅"""
    rubric = TURN_EVALUATION_RUBRICS[rubric_key]
    # ... 포맷팅 로직
    return formatted_text
```

### 사용 예시

```python
# app/domain/langgraph/nodes/turn_evaluator/evaluators.py

from app.domain.langgraph.nodes.turn_evaluator.rubrics.base_rubrics import (
    TURN_EVALUATION_RUBRICS,
    format_rubric_prompt
)

def prepare_evaluation_input_internal(...):
    # ...
    rubrics_section = "\n".join([
        format_rubric_prompt(key, metrics, algorithms_display)
        for key in ["clarity", "problem_relevance", "examples", "rules", "context"]
    ])
    
    system_prompt = f"""...
평가 기준 (Claude Prompt Engineering):
{rubrics_section}
..."""
```

---

## ✅ 결론 및 권장사항

### 현재 상황
- **4번 노드**: 루브릭이 하드코딩되어 있음
- **6번 노드**: 평가 기준이 하드코딩되어 있음

### 효율성 판단
**분리하는 것이 효율적입니다** ✅

**이유**:
1. 루브릭은 자주 변경될 가능성이 높음 (프롬프트 튜닝)
2. 평가 유형별 커스터마이징 필요성 증가
3. 유지보수성과 테스트 용이성 향상
4. 초기 구현 비용 대비 장기적 이점 큼

### 추천 구현 순서
1. **1단계**: 4번 노드 루브릭 파일 분리 (옵션 1)
2. **2단계**: 6번 노드 평가 기준 파일 분리
3. **3단계**: (선택) DB 기반 전환 (필요 시)

### 주의사항
- 기존 프롬프트와의 호환성 유지
- 점진적 리팩토링 (한 번에 모두 변경하지 않기)
- 테스트 코드 작성 필수



