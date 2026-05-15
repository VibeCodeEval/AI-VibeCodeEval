# Code Changes Log

> **추적 날짜**: 2026-04-13  
> **작성자**: Cursor AI Agent  
> **관련 Branch**: `develop`  
> **관련 Phase**: 노드 파일명 ↔ 역할 불일치 수정 (리팩토링)

---

## 1. 개요

평가 파이프라인 N5~N8 노드 파일명이 실제 구현 역할과 불일치한 문제를 수정.  
리팩토링 과정에서 기능은 재배치됐지만 파일명이 갱신되지 않아 코드 가독성 및 유지보수성이 저하된 상태였음.

- **CMD_006 (`phase6b_integrated_evaluator`) 폐기** 결정에 따라 관련 테스트 파일도 삭제.
- export 함수명(노드 ID)은 변경 없이 **파일명만** 변경하여 graph.py 노드 연결에 영향 없음.

---

## 2. 상세 변경 내역

---

### [RENAME] `app/domain/langgraph/nodes/eval/` — 파일명 4건

| 변경 전 | 변경 후 | export 함수 | 실제 역할 |
|---------|---------|-------------|-----------|
| `n5_integrated_evaluator.py` | `n5_code_execution.py` | `eval_code_execution` | Judge0 코드 실행 평가 |
| `n6_holistic_flow.py` | `n6_static_analysis.py` | `eval_static_analysis` | Radon CC + AST 정적 분석 |
| `n7_aggregate_turn_scores.py` | `n7_code_agent.py` | `eval_code_agent` | 단일 LLM 코드 리뷰 |
| `n8_code_execution.py` | `n8_holistic_debate.py` | `holistic_debate_flow` | 다중 에이전트 토론 (검사/변호인/중재자 × 2라운드) |

---

### [MODIFY] `app/domain/langgraph/graph.py`

**수정 내용:** N5~N8 import 경로를 변경된 파일명으로 갱신.

```python
# 변경 전
from app.domain.langgraph.nodes.eval.n5_integrated_evaluator import eval_code_execution
from app.domain.langgraph.nodes.eval.n6_holistic_flow import eval_static_analysis
from app.domain.langgraph.nodes.eval.n7_aggregate_turn_scores import eval_code_agent
from app.domain.langgraph.nodes.eval.n8_code_execution import holistic_debate_flow

# 변경 후
from app.domain.langgraph.nodes.eval.n5_code_execution import eval_code_execution
from app.domain.langgraph.nodes.eval.n6_static_analysis import eval_static_analysis
from app.domain.langgraph.nodes.eval.n7_code_agent import eval_code_agent
from app.domain.langgraph.nodes.eval.n8_holistic_debate import holistic_debate_flow
```

---

### [MODIFY] `app/domain/langgraph/nodes/eval/__init__.py`

**수정 내용:** `graph.py`와 동일하게 N5~N8 import 경로 4줄 갱신.

---

### [MODIFY] `app/domain/langgraph/nodes/__init__.py`

**수정 내용:** `graph.py`와 동일하게 N5~N8 import 경로 4줄 갱신.

---

### [MODIFY] `tests/test_langsmith_tracing.py`

**문제:** `n8_code_execution`에서 `eval_code_execution`을 import하는 잘못된 경로가 있었음.  
(`eval_code_execution`은 N5 파일에 있으며, N8 파일은 `holistic_debate_flow`를 export함.)

**수정:**
```python
# 변경 전 (잘못된 import)
from app.domain.langgraph.nodes.eval.n8_code_execution import eval_code_execution

# 변경 후 (올바른 경로)
from app.domain.langgraph.nodes.eval.n5_code_execution import eval_code_execution
```

---

### [DELETE] `tests/test_phase6b_integrated_evaluator.py`

**사유:** CMD_006 (`phase6b_integrated_evaluator`) 폐기 결정에 따라 삭제.  
해당 테스트는 존재하지 않는 함수(`calculate_expression_score`, `calculate_first_prompt_score` 등)와 미구현 Pydantic 모델(`TurnAnalysis`, `SessionAnalysis`, `IntegratedEvaluationResult`)을 import하고 있어 실행 시 ImportError가 발생하는 상태였음.

---

### [MODIFY] `docs/평가_파이프라인_플로우.md` / `.maestro/docs/평가_파이프라인_플로우.md`

**수정 내용:** "5. 관련 코드 경로" 섹션의 N5~N9 경로를 변경된 파일명으로 갱신.

```
# 변경 전
N5~N9 | app/domain/langgraph/nodes/eval/n5_integrated_evaluator.py ~ n9_final_scores.py

# 변경 후
N5~N9 | app/domain/langgraph/nodes/eval/n5_code_execution.py ~ n9_final_scores.py
```

두 파일은 동일 내용으로 동시 수정.

---

## 3. 검증

`uv run python`으로 변경된 4개 경로 import 정상 동작 확인:

```
N5: eval_code_execution    ✓
N6: eval_static_analysis   ✓
N7: eval_code_agent        ✓
N8: holistic_debate_flow   ✓
모든 import 성공
```

---

## 4. 영향 범위

- **그래프 노드 연결**: 변경 없음 (노드 ID 및 export 함수명 동일)
- **State 필드**: 변경 없음
- **DB 스키마**: 변경 없음
- **API**: 변경 없음
