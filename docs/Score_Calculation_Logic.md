# 스코어 총합 로직 정리

## 실제 Flow (scores.py)

### 1. Prompt Score 계산

```python
# holistic_flow_score: 60%, aggregate_turn_score: 40%
prompt_score = holistic_flow_score * 0.60 + aggregate_turn_score * 0.40
```

**가중치**:
- `holistic_flow_score`: 60% (체이닝 전략 평가)
- `aggregate_turn_score`: 40% (턴별 프롬프트 평가 평균)

### 2. 최종 Total Score 계산

```python
weights = {
    "prompt": 0.40,      # 프롬프트 활용 (턴 점수 + 플로우)
    "performance": 0.30,  # 성능
    "correctness": 0.30,  # 정확성
}

total_score = (
    prompt_score * 0.40 +
    perf_score * 0.30 +
    correctness_score * 0.30
)
```

**최종 가중치**:
- **Prompt Score**: 40% (holistic_flow 60% + turn_score 40%)
- **Performance Score**: 30%
- **Correctness Score**: 30%

## 테스트 스크립트 (test_judge0_submit.py)

### 현재 구현 (잘못됨)

```python
# 최종 점수 계산
final_score = (correctness_info['score'] * 0.5 + performance_info['score'] * 0.25)
```

**문제점**:
- 실제 Flow와 다름
- Prompt Score가 없음
- 가중치가 다름 (Correctness 50%, Performance 25%)

### 올바른 구현

테스트 스크립트는 Judge0만 테스트하므로:
- **Correctness Score**: 30% (실제 Flow와 동일)
- **Performance Score**: 30% (실제 Flow와 동일)
- **Prompt Score**: 40% (테스트 스크립트에서는 계산 불가, 0점 또는 제외)

## 점수 계산 예시

### 실제 Flow 예시

```
holistic_flow_score = 92.0
aggregate_turn_score = 88.0
code_performance_score = 100.0
code_correctness_score = 100.0

1. Prompt Score 계산:
   prompt_score = 92.0 * 0.60 + 88.0 * 0.40 = 55.2 + 35.2 = 90.4

2. Total Score 계산:
   total_score = 90.4 * 0.40 + 100.0 * 0.30 + 100.0 * 0.30
               = 36.16 + 30.0 + 30.0
               = 96.16점
```

### 테스트 스크립트 예시 (Judge0만)

```
code_correctness_score = 100.0
code_performance_score = 100.0

1. Prompt Score: 없음 (0점 또는 제외)
2. Total Score 계산:
   total_score = 0 * 0.40 + 100.0 * 0.30 + 100.0 * 0.30
               = 0 + 30.0 + 30.0
               = 60.0점
```

또는 Prompt Score를 제외하고:

```
total_score = 100.0 * 0.50 + 100.0 * 0.50
            = 50.0 + 50.0
            = 100.0점 (Judge0만 평가)
```

## 수정 필요 사항

테스트 스크립트의 최종 점수 계산을 실제 Flow와 일치시키거나, Judge0만 평가한다는 점을 명확히 해야 합니다.



