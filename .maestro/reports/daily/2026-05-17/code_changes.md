# code_changes — 2026-05-17

## rubric_json: N5 TC 상세 + performance TC 스냅샷 (turn_logs 제외)

- `states.py`: `test_case_results` 필드 추가 (N5 → N9)
- `n5_integrated_evaluator.py`: Judge0 per-TC 결과를 State에 반환 (`test_case_results`, 실패 시 `[]`)
- `rubric_json_serializers.py`: `correctness_details.test_cases[]`, `performance_details.test_cases[]` 조립
- `n9_final_scores.py`: DB `scores.rubric_json` 저장 시 serializers 사용
- `graph.py`: 초기 State에 `test_case_results=None`
- `docs/프론트_평가결과_DTO_명세.md`, `docs/점수_계산_로직.md` 스키마 갱신
- `tests/test_rubric_json_serializers.py` 추가

**의도**: 제출 결과 단일 조회 시 Judge0 TC별 입출력·실패 사유 확인. 턴 평가 본문은 기존 `prompt_evaluations` 유지.

## intent_cot → prompt_evaluations 저장

- `intent_analysis`가 `intent_cot`을 State에 반환 (첫 턴 FOLLOW_UP 보정 시 CoT에 보정 문구 추가)
- Redis `prompt_evaluation_details.intent_cot`, PG `prompt_evaluations.details.intent_cot`
- `evaluation_storage_service`, `eval_service` 백그라운드, `n4_eval_turn_guard` 동기 경로 반영
- `tests/test_intent_cot_persistence.py`, `docs/프론트_평가결과_DTO_명세.md` (`intentCot`)
