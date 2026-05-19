# DB 저장 경로 점검 — 가드레일 meta 유사 오류

> 작성: 2026-05-20  
> **작성**: 2026-05-19  
> 배경: V3(`prompt_messages.meta` 가드레일 필드) 미저장 이슈 조사 중, 동일 패턴이 다른 저장 경로에도 있는지 점검.

---

## 공통 원인 패턴 (3가지)

| 패턴 | 설명 | 대표 사례 |
|------|------|-----------|
| **① 저장 순서** | Spring `save-message` → Worker 그래프 순이면 Redis/그래프 결과가 DB보다 늦음 | 가드레일 `meta` → 그래프 후 백필로 보완 |
| **② turn 체계 혼동** | API는 DB **storage slot**(USER=홀수, AI=짝수), LangGraph는 **conversation turn** | `add_message`, `current_turn`, `update_message_meta` |
| **③ 조용한 실패** | `except: pass` / warning만 / “메시지 없음” 후 계속 | 예전 가드레일 meta 병합 |

### turn 체계 (SoT)

- **conversation turn**: LangGraph `current_turn`, N2 `guardrail_flag_turns`, N4 평가 루프 (1, 2, 3…)
- **storage slot**: `prompt_messages.turn` — USER `2N-1`, AI `2N` (`session_repository.conversation_turn_to_storage_slot`)
- **Spring `turnId` / save-message `turn`**: DB storage slot으로 전달되는 경우가 많음

---

## 경로별 점검

### 1. `MessageStorageService.save_message` — 가드레일 meta

| 항목 | 내용 |
|------|------|
| **상태** | 수정 완료 |
| **조치** | `api_turn_to_conversation_turn`, `build_guardrail_meta_patch`, AI 문구 fallback |
| **백필** | `EvalService.process_message` 후 `sync_guardrail_meta_to_db` |
| **남은 리스크** | 그래프 없이 `save-message`만 호출 시 백필 없음 → AI prefix fallback만 |

**V3 검증 (수동)** — `prompt_messages.meta` JSONB:

- `is_guardrail_failed`: `true`
- `block_reason`: `OFF_TOPIC` / `INAPPROPRIATE` / `JAILBREAK`
- `conversation_turn`: conversation turn 번호

```sql
SELECT turn, role, meta->>'is_guardrail_failed' AS gr,
       meta->>'block_reason' AS reason,
       meta->>'conversation_turn' AS conv
FROM prompt_messages
WHERE session_id = <세션_id>
ORDER BY turn;
```

---

### 2. `MessageStorageService._update_redis_checkpoint` — **높음 (수정함)**

| 항목 | 내용 |
|------|------|
| **문제** | Spring `turn`(storage 2,4,6…)을 그대로 `current_turn`에 반영 → LangGraph 턴 범위·N4 메시지 매칭 깨짐 |
| **증상** | `current_turn: 3`, `messages: 2`, `턴 1 - State에서 메시지 찾기 실패` |
| **조치** | Redis `messages[].turn`·`current_turn`은 **conversation turn**; `storage_turn` 필드로 API turn 보존 |

---

### 3. `MessageStorageService.save_messages_batch` — **중간 (수정함)**

| 항목 | 내용 |
|------|------|
| **문제** | raw `turn`으로 `add_message`, 가드레일 meta 미병합 |
| **조치** | `save_message`와 동일: conv turn 정규화 + Redis meta 병합 |

---

### 4. `EvalService._save_turn_analysis_to_db` — **중간 (보강함)**

| 항목 | 내용 |
|------|------|
| **패턴** | 그래프 **후** 실행 → ① 타이밍은 상대적으로 안전 |
| **리스크** | `turn`이 storage slot이면 USER 행 못 찾음 → `meta.turn_analysis` 누락 |
| **조치** | `api_turn_to_conversation_turn` 적용 |
| **미보완** | USER `save-message`가 아직 없으면 실패 (가드레일처럼 **백필 없음**) |

---

### 5. `EvalService` 백그라운드 → `prompt_evaluations` — **낮~중**

| 항목 | 내용 |
|------|------|
| **동작** | Redis `turn_log`는 conv turn; PG `save_turn_evaluation(turn=current_turn)` |
| **이슈** | `prompt_evaluations.turn`(conv) vs `prompt_messages.turn`(storage) — ORM FK·존재 체크 어긋남 (기존 설계) |
| **조치** | 존재 여부 조회만 USER storage turn으로 수정 (`evaluation_storage_service`) |
| **참고** | FK 없이 TURN_EVAL 저장 가능; export는 Redis/details 위주 |

---

### 6. `n4_eval_turn_guard` → `EvaluationStorageService` — **제출 시**

| 항목 | 내용 |
|------|------|
| **전제** | Redis `state.messages`에 턴 쌍(HUMAN+AI) 필요 |
| **리스크** | Spring만 `save-message`, LangGraph state 비어 있으면 N4 실패 |

---

### 7. Spring `meta` 직접 전달 (`code_snapshot`, `is_v1_checkpoint`)

| 항목 | 내용 |
|------|------|
| **상태** | 안전 (Worker Redis 불필요) |
| **리스크** | Spring이 키를 안 넣으면 Worker가 채우지 않음 |

---

### 8. `export_evaluation_json.py` / scripts

읽기 전용 — 저장 버그와 무관.

---

## 수정 파일 요약 (2026-05-20)

| 파일 | 변경 |
|------|------|
| `message_storage_service.py` | conv turn 정규화, 가드레일 백필, Redis `current_turn` 수정, batch 동일화 |
| `eval_service.py` | `sync_guardrail_meta_to_db` 호출, `turn_analysis` conv turn |
| `guardrail_turns.py` | `api_turn_to_conversation_turn`, `build_guardrail_meta_patch` |
| `evaluation_storage_service.py` | prompt_messages 존재 체크 시 storage turn |

---

## 권장 운영·검증

1. Worker 재시작 후 가드레일 1턴 → `prompt_messages.meta` 3키 확인 (V3).
2. 동일 세션 제출 → N4 로그: `messages` 개수·턴 쌍 추출 성공 여부.
3. Spec Extractor 사용 시 USER `meta.turn_analysis` 존재 여부.

---

## 추후 검토 (미구현)

- [ ] `turn_analysis` 그래프 후 DB 백필 (가드레일 `sync_*` 패턴)
- [ ] `prompt_evaluations.turn` ↔ storage slot 정합 문서/스키마 정리
- [ ] `send-messages`에서 Worker가 PG USER/AI 직접 저장 (Spring·Redis 이중화 축소)

---

## 관련 문서

- [State_노드별_흐름.md](../../docs/State_노드별_흐름.md) — N2/N4 가드레일 정책
- [current_eval_flow_db_to_llm.md](./current_eval_flow_db_to_llm.md) — turn_analysis 저장
- [../reports/daily/2026-05-19/code_changes.md](../reports/daily/2026-05-19/code_changes.md) — guardrail_flag_turns 구현
