# API 변경 사항 (2026-03-27)

> 1월 29일 이후 ~ 3월 27일까지의 API/스키마 변경을 정리합니다.

---

## 1. 내부 API (LangGraph State / 서비스 간 인터페이스)

### 1.1 MainGraphState 확장

| 필드 | 타입 | 상태 | 설명 |
|------|------|------|------|
| `v1_code` | `Optional[str]` | 신규 | Phase 1 SAVE 확정 Baseline 코드 |
| `v2_code` | `Optional[str]` | 신규 | 최종 제출 시점 Final 코드 |
| `v1_metrics` | `Optional[Dict[str, Any]]` | 신규 | v1 코드 분석 결과 (Radon CC 등) |
| `v2_metrics` | `Optional[Dict[str, Any]]` | 신규 | v2 코드 분석 결과 |

### 1.2 EvalTurnState 확장

| 필드 | 타입 | 상태 | 설명 |
|------|------|------|------|
| `previous_turns_summary` | `Optional[str]` | 신규 | 이전 턴 대화 요약 (V2.2) |

### 1.3 HolisticFlowEvaluation 변경

| 필드 | 변경 전 | 변경 후 | 사유 |
|------|---------|---------|------|
| `problem_decomposition` | float 0~100 | int 1~5 (ge=1, le=5) | V2.3 정수 출력 |
| `feedback_integration` | float 0~100 | int 1~5 | V2.3 |
| `strategic_exploration` | float 0~100 | int 1~5 | V2.3 |
| `overall_flow_score` | float 0~100 | int 1~5 | V2.3 |

### 1.4 IntentClassification 변경

| 필드 | 변경 전 | 변경 후 | 사유 |
|------|---------|---------|------|
| `intent_types` | `list[CodeIntentType]` (8가지) | `list[UnifiedIntentType]` (5가지) | V2.2 5-way |
| `reasoning` | `str` (필수) | `Optional[str]` | Optional로 완화 |

---

## 2. Enum 추가

| Enum | 위치 | 값 | 상태 |
|------|------|-----|------|
| `GradeType` | `enums.py` | A, B, C, D, F | 신규 |
| `UnifiedIntentType` | `enums.py` | SETTING, CREATION, REFINEMENT, VALIDATION, FOLLOW_UP | 신규 (기존 4대→5대로 확장) |
| `RubricType` | `enums.py` | SPECIFICITY, DESIGN_CONTROL, ROBUSTNESS, CONSISTENCY, EFFICIENCY | 신규 |

---

## 3. DB 저장 구조 변경 (스키마 변경 없음, JSONB 활용)

### 3.1 prompt_messages.meta (JSONB)

v1 스냅샷 저장 시:
```json
{
  "code_snapshot": "def check_passenger(...):\n    ...",
  "is_v1_checkpoint": true
}
```

### 3.2 scores.rubric_json (JSONB)

`final_scores`에 `v21_summary` 추가:
```json
{
  "v21_summary": {
    "rubric_breakdown": {
      "instruction_clarity": 85,
      "design_ownership": 70,
      "logical_gaps": 80,
      "consistency_maintained": 75,
      "code_improvement_contribution": 90
    },
    "code_quality_metrics": {
      "delta_cc_pct": 8.5,
      "ast_pattern_matched": true,
      "ast_applicable": true,
      "junior_grade": false,
      "has_v1": true
    }
  }
}
```

### 3.3 SessionRepository 추가 메서드

| 메서드 | 시그니처 | 설명 |
|--------|----------|------|
| `get_v1_checkpoint_code` | `(session_id: str) -> Optional[str]` | meta에서 `is_v1_checkpoint=true`인 `code_snapshot` 반환 |

---

## 4. 외부 API 변경

현재까지 **외부 REST API 엔드포인트의 변경은 없습니다.** 모든 변경은 내부 LangGraph State, 서비스 로직, JSONB 필드 활용에 한정됩니다.

> 향후 프론트엔드 연동 시 v21_summary를 응답에 포함하려면 `/api/chat/submit` 응답 스키마 확장이 필요할 수 있습니다.

---

## 5. 호환성 영향

- **하위 호환 유지**: 모든 신규 State 필드는 `Optional`/기본값으로 추가되어 기존 플로우에 영향 없음
- **Hybrid Likert**: Tier 1/2/3 우선순위 큐로 Legacy(0~100)와 New(1~5) 혼용 지원
- **5-way 의도**: DB JSONB에 저장되므로 스키마 변경 없음
- **v21_summary**: rubric_json JSONB 내부 필드이므로 기존 조회에 영향 없음
