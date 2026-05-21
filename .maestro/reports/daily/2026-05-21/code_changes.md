# code_changes — 2026-05-21

> **주제**: N9 최종 등급(`grade`)을 `total_score` 기준으로 통일  
> **증상**: `total_score` 82인데 `rubric_json.grade`가 D (또는 correctness&lt;100 시 F/D 고정) — 토론 verdict B와 불일치

---

## N9 — `grade` 산정 (`aggregate_final_scores`)

### 변경 파일

| 파일 | 변경 |
|------|------|
| `app/domain/langgraph/nodes/eval/n9_final_scores.py` | `_grade_from_total_score()` 추가; `total_score` 계산 직후 `grade = _grade_from_total_score(total_score)` |
| `tests/test_n9_perf_total_order.py` | P4 사례(82.38→B) 등 구간 테스트 추가 |

### 이전 로직 (제거)

```python
if correctness_normalized < 100:
    grade = "F" if correctness_normalized < 60 else "D"   # total_score 무시
else:
    # correctness==100 일 때만 ΔCC·AST 또는 total_score 구간 사용
```

- **문제**: Judge0 부분 통과(예: 90%)만으로도 등급이 **D 또는 F로 상한**됨.
- **P4 (`1_4_평가.json`)**: `total_score=82.38`, `correctness_normalized=90` → **grade D** (기대 B).

### 이후 로직 (SoT)

```python
grade = _grade_from_total_score(total_score)
```

| `total_score` (0~100) | `grade` |
|----------------------|---------|
| ≥ 90 | A |
| ≥ 80 | B |
| ≥ 70 | C |
| ≥ 60 | D |
| &lt; 60 | F |

- 구간은 `subgraph_debate._derive_grade(holistic_flow_score)`와 **동일 임계값**.
- `correctness_normalized`, `delta_cc_pct`, `ast_pattern_matched`는 **`total_score`·`v21_summary`에만 반영**, 등급 분기에는 미사용.

### `total_score` 공식 (변경 없음)

```text
prompt_score = holistic×0.6 + aggregate_turn×0.4  (+ R4 20% 반영, integrated_score 블렌딩 등)
total_score  = prompt×0.4 + correctness_normalized×0.4 + perf_score×0.2
```

### DB / export

- 이미 저장된 `scores.grade`·`rubric_json.grade`는 **자동 갱신되지 않음**.
- 신규 제출 N9 경로 또는 점수 재집계 후 반영.

### 검증

```bash
uv run pytest tests/test_n9_perf_total_order.py -q
```

---

## 참고 (동일 기간 코드, 본 항목과 별도)

- Intent v2.2 (`eval_intent_disambiguation.yaml`, `analysis.py` 정책 보정)
- Turn eval v3.4.6 (`eval_turn.yaml`, 이전 턴 대화, 혼합/후속 캘리브레이션)
- 상세는 별도 작업·rerun 로그 참고
