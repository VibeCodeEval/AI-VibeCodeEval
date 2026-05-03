# Code Changes Log

> **추적 날짜**: 2026-04-27  
> **작성자**: Cursor AI Agent  
> **작업 주제**: API 우선 분기 전환 (`request_type` 기반), CHAT 가드레일 전용화, 문서/테스트 동기화

---

## 1. 개요

이번 작업에서는 제출/채팅 분기를 LLM 해석에 의존하던 구조를 정리하고,
**API 입력(`request_type`)을 단일 분기 소스**로 우선 적용하도록 리팩터링했습니다.

핵심 목표:
- 제출 요청은 LLM 오판과 무관하게 평가 파이프라인으로 진입
- `n2_intent_analyzer`는 경로 결정자가 아니라 CHAT 가드레일/전략 판단 노드로 축소
- 라우팅 소스 불일치(`request_type` vs `is_submitted` vs LLM 출력) 최소화

---

## 2. 상세 변경 내역

### [MODIFY] `app/domain/langgraph/states.py`

- `MainGraphState`에 아래 필드를 추가:
  - `request_type: Optional[str]` (`CHAT` / `SUBMISSION`)
- 목적: API 입력 기반 분기 신호를 상태 모델에서 명시적으로 관리

---

### [MODIFY] `app/domain/langgraph/graph.py`

- `get_initial_state()` 시그니처 확장:
  - `request_type: str = "CHAT"`
- 초기 상태에 `request_type`를 포함해 생성

---

### [MODIFY] `app/application/services/eval_service.py`

- `process_message` / 스트리밍 경로 / `submit_code` 경로에서
  state에 `request_type`를 명시 주입하도록 변경
  - 일반 채팅: `CHAT`
  - 제출: `SUBMISSION`

- 제출 경로(`submit_code`)의 기존 `is_submitted=True` 동작 유지 + `request_type="SUBMISSION"` 동기화

---

### [MODIFY] `app/domain/langgraph/nodes/chat/routers.py`

- `intent_router` 우선순위 변경:
  1. `request_type == "SUBMISSION"` → 즉시 `eval_turn_guard`
  2. 하위 호환: 기존 `is_submitted` 또는 `PASSED_SUBMIT`도 제출 분기 허용

- `main_router`도 `request_type == "SUBMISSION"`를 우선 고려하도록 보강

---

### [MODIFY] `app/domain/langgraph/nodes/chat/n2_intent_analyzer.py`

- `request_type == "SUBMISSION"`(또는 기존 `is_submitted=True`)이면:
  - LLM 분기 판정을 생략하고 즉시 `PASSED_SUBMIT` 반환

- `request_type == "CHAT"`에서는 기존 LLM 가드레일/전략 판정 유지

- CHAT 경로에서 LLM이 `PASSED_SUBMIT`을 반환해도 라우팅 오염이 발생하지 않도록 보정:
  - `is_submitted=False` 강제
  - 필요 시 `intent_status`를 `PASSED_HINT`로 정규화

---

### [MODIFY] `app/domain/langgraph/prompts/eval_intent_analysis.yaml`

- 프롬프트 책임 범위를 명확화:
  - 제출/채팅 분기(`request_type`)는 API 입력 우선
  - 본 프롬프트는 가드레일/가이드 전략 판단 중심

---

### [MODIFY] 문서 동기화

- `docs/평가_파이프라인_플로우.md`
- `.maestro/docs/평가_파이프라인_플로우.md`

갱신 내용:
- 제출 평가 진입 조건을 `PASSED_SUBMIT` 중심에서
  **`request_type=SUBMISSION` 중심**으로 정리
- N2 역할 설명을 “의도·제출 분기”에서
  **“CHAT 가드레일·전략 판정”**으로 현실 동작에 맞게 수정

---

### [ADD] `tests/test_request_type_routing.py`

신규 테스트 3건 추가:
1. `request_type=SUBMISSION`이면 `intent_router`가 즉시 `eval_turn_guard`로 분기
2. `request_type=CHAT`이면 기존 `intent_status` 기반으로 writer 경로 유지
3. `main_router`가 `request_type=SUBMISSION`을 평가 경로로 인식

---

## 3. 테스트 결과

실행 명령 및 결과:

- `uv run pytest tests/test_request_type_routing.py -q`
  - **3 passed**

- `uv run pytest tests/test_node4_unit.py -q`
  - **13 passed**

린트 확인:
- 변경 파일 대상 진단 결과 **No linter errors found**

---

## 4. 영향 및 안정성 메모

- 제출 경로 결정론 강화:
  - API에서 `SUBMISSION`이면 LLM 오판과 무관하게 평가 진입

- 운영 안정성 개선:
  - 분기 기준이 단일화되어 원인 추적 용이
  - `is_submitted`/LLM 출력 불일치로 인한 오분기 위험 감소

- 하위 호환 유지:
  - 기존 `is_submitted`/`PASSED_SUBMIT` 기반 분기는 보조적으로 유지해 점진 전환 가능

---

## 5. 후속 권장 작업

1. API 스키마 문서에 `request_type` 우선 규칙을 명시
2. `session`/`chat` 경로에서 누락 없는 `request_type` 전달을 E2E로 재검증
3. 라우팅 로그에 `routing_source`(api/legacy) 라벨을 추가해 운영 관측성 강화
