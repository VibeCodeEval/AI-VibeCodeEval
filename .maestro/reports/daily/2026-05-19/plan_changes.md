# plan_changes — 2026-05-19

## 가드레일 점수·맥락 정책 확정 (2026-05-05 메모 대체)

**이전** (`.maestro/reports/daily/2026-05-05/plan_changes.md`): `guardrail_flag_count` 누적, TURN_EVAL 계속 수행, N9 감점 TBD.

**현재** (본 PR):

| 항목 | 결정 |
|------|------|
| 턴 점수 | 가드레일 턴 **0점** (Redis·PG 저장) |
| LLM eval | eval_turn subgraph **스킵** |
| 맥락 | `previous_turns_summaries`, N8 debate 입력에서 **제외** |
| N9 | 가드레일 **추가 감점 없음** |
| prompt 평균 | 0점 턴 **포함** (`aggregate_turn_score`) |
| SoT | `guardrail_flag_turns` + `guardrail_turn_reasons` |
| N2 차단 | `OFF_TOPIC` / `INAPPROPRIATE` / `JAILBREAK` (YAML·N2 등록) |
| spec 붙여넣기 | `spec_paste_guard` **별도** (30점 트랙 유지) |

## DB·Redis 저장 계획

- 점검 문서: `.maestro/docs/DB_Save_Path_Audit.md`
- conversation turn vs storage turn 정규화 일원화
- meta 백필 패턴: 가드레일 우선 적용, `turn_analysis` 등은 후속 TODO

## 미결

- E2E V1–V3 (Worker 재시작 후)
- N4 PG `prompt_messages` fallback (Redis messages 불완전 시)
- 채팅 state에서 `solution_code` 제외 (보안, 별도 PR)
