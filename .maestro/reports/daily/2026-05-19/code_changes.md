# code_changes — 2026-05-19

> **브랜치**: `35-fixn2-가드레일-증설-guardrail_flag_turn-추가-후-n4-평가에-반영`  
> **GitHub 푸시 전**: Worker 재시작 후 V1–V3 E2E 권장 (아래 수동 검증).

---

## 가드레일 턴 평가·맥락 제외 (`guardrail_flag_turns`)

### State / 그래프

| 파일 | 변경 |
|------|------|
| `app/domain/langgraph/states.py` | `guardrail_flag_turns`, `guardrail_turn_reasons` 추가; `guardrail_flag_count` **제거** |
| `app/domain/langgraph/graph.py` | state 필드 연동 |

### 유틸 (신규)

| 파일 | 변경 |
|------|------|
| `app/domain/langgraph/utils/guardrail_turns.py` | 등록·판별·거절 문구·N8 `filter_turn_logs_for_debate`·storage↔conversation turn·`build_guardrail_meta_patch` |
| `app/domain/langgraph/utils/turn_messages.py` | Redis `messages` Human+AI+`turn` 쌍 정규화 (`handle_failure` 경로) |

### 채팅 (N2 / Writer / system)

| 파일 | 변경 |
|------|------|
| `app/domain/langgraph/nodes/chat/n2_intent_analyzer.py` | `INAPPROPRIATE`·`JAILBREAK` BLOCKED 시 턴 등록 |
| `app/domain/langgraph/prompts/eval_intent_analysis.yaml` | 위 intent·BLOCKED 정의 |
| `app/domain/langgraph/nodes/system/system_nodes.py` | 가드레일 시 Writer와 동일 Human+AI append, 통일 거절 prefix |

### 평가 (N4 / N8 / export)

| 파일 | 변경 |
|------|------|
| `app/domain/langgraph/nodes/eval/n4_eval_turn_guard.py` | 목록 우선 0점·eval 스킵; `previous_turns_summaries`·`prev_user_content` 제외; assistant prefix fallback |
| `app/domain/langgraph/nodes/eval/n8_code_execution.py` | `filter_turn_logs_for_debate` |
| `app/domain/langgraph/nodes/eval/n8_holistic_debate.py` | 동일 |
| `app/domain/langgraph/nodes/eval/turn_evaluation_details.py` | export `block_reason` |

### 서비스 (DB·Redis·meta)

| 파일 | 변경 |
|------|------|
| `app/application/services/message_storage_service.py` | conv turn 정규화, meta 병합, Redis checkpoint `current_turn`, batch turn |
| `app/application/services/eval_service.py` | `sync_guardrail_meta_to_db` (그래프 직후 PG 백필) |
| `app/application/services/evaluation_storage_service.py` | storage turn 존재 체크 |

### 문서·테스트

| 파일 | 변경 |
|------|------|
| `docs/State_노드별_흐름.md` | N2/N4/N8 가드레일 정책 |
| `.maestro/docs/DB_Save_Path_Audit.md` | 저장 경로·turn 혼동 점검 (신규) |
| `tests/test_guardrail_turns.py` | U1–U8 등 (신규) |
| `tests/test_chains.py` | guardrail 메시지 assertion |

### 정책 요약

- 가드레일 턴: **0점**, eval_turn subgraph **미호출**, `previous_turns_summaries` / N8 토론 **제외**
- N9 **추가 감점 없음**; `aggregate_turn_score`에는 0점 **포함**
- `spec_paste_guard`는 **별도** (기존 30점 트랙, `guardrail_flag_turns`와 무관)
- SoT: `state.guardrail_flag_turns` (conversation turn); 레거시 `guardrail_flag_count` 폐기

---

## DB 저장 경로 후속 (동일 PR)

V3 `prompt_messages.meta` 미저장(저장 순서·turn 혼동) 조사 중 발견한 패턴 정리·보완.

- **문서**: [.maestro/docs/DB_Save_Path_Audit.md](../../docs/DB_Save_Path_Audit.md)
- **백필**: `EvalService.process_message` 종료 후 `sync_guardrail_meta_to_db`
- **meta 키**: `is_guardrail_failed`, `block_reason`, `conversation_turn`

---

## pytest

```text
tests/test_guardrail_turns.py     — U1–U8 + 필터 (13+ passed)
tests/test_chains.py            — guardrail 거절 문구
회귀: test_request_type_routing, test_holistic_debate_router, test_turn_content_decomposition
```

---

## 수동 검증 (V1–V3, 미실행)

| ID | 시나리오 |
|----|----------|
| V1 | 1턴 OFF_TOPIC → 2~3 정상 → 제출 |
| V2 | 1·5 GR, 2·3·4·6 정상 — 턴6 맥락에 1·5 없음 |
| V3 | Spring save-message 후 `prompt_messages.meta` 3키 |

---

## 미포함 (진단용, 커밋 선택)

- `scripts/_analyze_export_guardrail.py`
- `scripts/_check_pm_order.py`

---

## 보류 (별 PR 후보)

- `problem_context`에서 채팅 시 `solution_code` 제외, 제출(N4~) 시만 로드
