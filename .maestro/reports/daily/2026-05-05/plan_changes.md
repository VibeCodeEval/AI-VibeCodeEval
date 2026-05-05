# 2026-05-05 계획 메모 (Guardrail 점수 정책)

## 결정 사항 (임시 확정)

- TURN_EVAL은 계속 수행/저장한다.
- 가드레일 플래그 감지 횟수는 `state.guardrail_flag_count`에 누적 저장한다.
- **최종 프롬프트 점수(prompt_score) 감점은 아직 적용하지 않는다.**

## 구현 반영 상태

- `n4_eval_turn_guard`에서 제출 턴 평가 루프 중 가드레일 플래그를 감지하고
  `guardrail_flag_count`를 state 반환값에 포함하도록 반영함.
- `MainGraphState`에 `guardrail_flag_count` 필드 추가.

## 추후 최종 결정 TODO

- 감점 정책 최종 확정 필요:
  - 감점 적용 여부(적용/미적용)
  - 적용 시점(N9 최종 점수 집계 단계 권장)
  - 감점식(고정값 vs 비율 vs 플래그 횟수 기반 누진)
  - 감점 상한/하한

