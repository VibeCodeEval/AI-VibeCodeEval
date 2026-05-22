# api_changes — 2026-05-19

## LangGraph `MainGraphState`

| 필드 | 변경 | 비고 |
|------|------|------|
| `guardrail_flag_turns` | **추가** | `list[int]` — conversation turn 번호. N2 BLOCKED 시 등록, N1에서 리셋 안 함 |
| `guardrail_turn_reasons` | **추가** | `dict[int, str]` — turn → `OFF_TOPIC` / `INAPPROPRIATE` / `JAILBREAK` 등 |
| `guardrail_flag_count` | **제거** | 2026-05-05 임시 카운터 폐기. N9 감점 미적용 정책 유지 |

## `prompt_messages.meta` (PG, Worker 병합)

| 키 | 타입 | 설명 |
|----|------|------|
| `is_guardrail_failed` | bool | 가드레일 턴 |
| `block_reason` | string | 차단 사유 코드 |
| `conversation_turn` | int | LangGraph conversation turn (storage turn과 구분) |

- Spring `save-message`가 그래프보다 먼저 오면 meta 비어 있을 수 있음 → `sync_guardrail_meta_to_db`로 백필.

## N2 intent (`eval_intent_analysis.yaml`)

- `INAPPROPRIATE`, `JAILBREAK` → `intent_status=BLOCKED` 시 `guardrail_flag_turns` 등록.

## N4 / N8 동작 (REST 스키마 변경 없음)

- `guardrail_flag_turns`에 포함된 turn: TURN_EVAL LLM 미호출, `turn_score=0`, `GUARDRAIL_BLOCKED`.
- N8: 해당 turn의 `turn_logs` 제외 (`filter_turn_logs_for_debate`).

## 호환성

- 기존 Redis state에 `guardrail_flag_count`만 있으면 무시됨 (필드 없음).
- 구간 export(`export_evaluation_json`)는 `block_reason` 필드 추가 반영.
