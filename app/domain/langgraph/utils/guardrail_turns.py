"""
가드레일 턴 등록·조회 (채팅 N2 → 제출 N4).

SoT: 대화 턴 번호 = MainGraphState.current_turn (N1 증가 후, N2 BLOCKED 시점).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# 거절 응답·N4 fallback 감지용 (handle_failure / writer_guardrail 통일)
GUARDRAIL_USER_MESSAGE_PREFIX = "해당 요청은 시험 규정상 답변할 수 없습니다"


def _normalize_turn_key(turn: Any) -> str:
    try:
        return str(int(turn))
    except (TypeError, ValueError):
        return str(turn)


def get_guardrail_flag_turns(state: Dict[str, Any]) -> List[int]:
    raw = state.get("guardrail_flag_turns") or []
    turns: List[int] = []
    for t in raw:
        try:
            turns.append(int(t))
        except (TypeError, ValueError):
            continue
    return sorted(set(turns))


def get_guardrail_turn_reasons(state: Dict[str, Any]) -> Dict[str, str]:
    return dict(state.get("guardrail_turn_reasons") or {})


def is_guardrail_turn(state: Dict[str, Any], turn: int) -> bool:
    return int(turn) in get_guardrail_flag_turns(state)


def api_turn_to_conversation_turn(turn: Any, role: Any) -> int:
    """
    Spring save-message / turnId: DB storage slot(USER=홀수, AI=짝수) 또는 conversation turn.
    session_repository.add_message는 conversation turn을 받는다.
    """
    try:
        t = int(turn)
    except (TypeError, ValueError):
        return 1
    role_s = str(role).upper() if role is not None else "USER"
    if "USER" in role_s and t % 2 == 1:
        return max(1, (t + 1) // 2)
    if ("AI" in role_s or "ASSISTANT" in role_s) and t % 2 == 0:
        return max(1, (t + 1) // 2)
    return max(1, t)


def build_guardrail_meta_patch(
    state: Dict[str, Any],
    message_turn: Any,
    role: Any,
    content: str = "",
) -> Optional[Dict[str, Any]]:
    """save-message·DB 백필용 meta 패치 (Redis 목록 우선, AI 문구 fallback)."""
    conv_turn = api_turn_to_conversation_turn(message_turn, role)
    blocked_conv = resolve_conversation_turn_for_guardrail(state, message_turn)
    if blocked_conv is None and is_guardrail_turn(state, conv_turn):
        blocked_conv = conv_turn
    if blocked_conv is not None:
        reasons = get_guardrail_turn_reasons(state)
        return {
            "is_guardrail_failed": True,
            "block_reason": reasons.get(str(blocked_conv)),
            "conversation_turn": blocked_conv,
        }
    role_s = str(role).upper() if role is not None else ""
    if ("AI" in role_s or "ASSISTANT" in role_s) and is_guardrail_blocked_response_text(
        content or ""
    ):
        reasons = get_guardrail_turn_reasons(state)
        return {
            "is_guardrail_failed": True,
            "block_reason": reasons.get(str(conv_turn)) or "OFF_TOPIC",
            "conversation_turn": conv_turn,
        }
    return None


def resolve_conversation_turn_for_guardrail(
    state: Dict[str, Any], message_turn: Any
) -> Optional[int]:
    """
    save-message turn(DB slot)과 graph conversation turn 정합.
    guardrail_flag_turns는 conversation turn 기준.
    """
    try:
        t = int(message_turn)
    except (TypeError, ValueError):
        return None
    candidates = {t}
    if t % 2 == 1:
        candidates.add((t + 1) // 2)
    else:
        candidates.add(t // 2)
    blocked = set(get_guardrail_flag_turns(state))
    for c in candidates:
        if c in blocked:
            return c
    return None


def register_guardrail_turn(
    state: Dict[str, Any],
    turn: Optional[int] = None,
    block_reason: Optional[str] = None,
) -> Dict[str, Any]:
    """
    가드레일 턴 등록. LangGraph 노드 반환 dict에 병합해 사용.

    Returns:
        guardrail_flag_turns, guardrail_turn_reasons 필드만 포함한 patch.
    """
    t = int(turn if turn is not None else state.get("current_turn") or 0)
    if t <= 0:
        return {}

    turns = list(get_guardrail_flag_turns(state))
    if t not in turns:
        turns.append(t)
        turns.sort()

    reasons = dict(get_guardrail_turn_reasons(state))
    key = _normalize_turn_key(t)
    if block_reason:
        reasons[key] = str(block_reason)

    return {
        "guardrail_flag_turns": turns,
        "guardrail_turn_reasons": reasons,
    }


def format_guardrail_user_message(violation_message: Optional[str] = None) -> str:
    """채팅 거절·assistant 응답용 통일 문구."""
    if violation_message and str(violation_message).strip():
        msg = str(violation_message).strip()
        if msg.startswith(GUARDRAIL_USER_MESSAGE_PREFIX):
            return msg
        return f"{GUARDRAIL_USER_MESSAGE_PREFIX} {msg}"
    return (
        f"{GUARDRAIL_USER_MESSAGE_PREFIX} "
        "다른 방식으로 질문해 주세요."
    )


def _turn_key_to_int(key: Any) -> Optional[int]:
    try:
        return int(key)
    except (TypeError, ValueError):
        return None


def debate_exclusion_reason_for_turn(
    turn: Optional[int],
    log: Optional[Dict[str, Any]],
    state: Dict[str, Any],
) -> Optional[str]:
    """
    N8 토론 컨텍스트에서 제외할 턴이면 사유 문자열, 포함이면 None.

    turn_logs 항목이 없어도 guardrail_flag_turns로 제외 가능.
    """
    if turn is None:
        return None
    blocked = set(get_guardrail_flag_turns(state))
    if turn in blocked:
        return "guardrail_flag_turns"
    if not isinstance(log, dict):
        return None
    if log.get("is_guardrail_failed"):
        return "is_guardrail_failed"
    ped = log.get("prompt_evaluation_details") or {}
    if ped.get("intent") == "GUARDRAIL_BLOCKED":
        return "GUARDRAIL_BLOCKED"
    return None


def filter_turn_material_for_debate(
    turn_logs: Dict[str, Any],
    turn_scores: Dict[str, Any],
    state: Dict[str, Any],
) -> tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
    """
    N8 토론: 가드레일 턴의 turn_logs·turn_scores 모두 제외.

    N9 aggregate_turn_score 등 MainGraph turn_scores는 변경하지 않음.
    Returns:
        (filtered_logs, filtered_scores, excluded) — excluded: {turn, reason}[]
    """
    logs_in = turn_logs if isinstance(turn_logs, dict) else {}
    scores_in = turn_scores if isinstance(turn_scores, dict) else {}
    all_keys = set(logs_in.keys()) | set(scores_in.keys())

    filtered_logs: Dict[str, Any] = {}
    filtered_scores: Dict[str, Any] = {}
    excluded: List[Dict[str, Any]] = []

    for key in all_keys:
        turn = _turn_key_to_int(key)
        log = logs_in.get(key) if isinstance(logs_in.get(key), dict) else {}
        reason = debate_exclusion_reason_for_turn(turn, log, state)
        if reason:
            excluded.append({"turn": key, "reason": reason})
            continue
        if key in logs_in and isinstance(logs_in[key], dict):
            filtered_logs[key] = logs_in[key]
        if key in scores_in:
            filtered_scores[key] = scores_in[key]

    return filtered_logs, filtered_scores, excluded


def filter_turn_logs_for_debate(
    turn_logs: Dict[str, Any],
    state: Dict[str, Any],
) -> Dict[str, Any]:
    """N8 토론: 가드레일 턴 turn_logs만 제외 (하위 호환). turn_scores는 filter_turn_material_for_debate 사용."""
    filtered, _, _ = filter_turn_material_for_debate(
        turn_logs, {}, state
    )
    return filtered


def storage_slot_to_conversation_turn(storage_turn: Any) -> int:
    """DB storage slot(USER=2N-1, AI=2N) → conversation turn N."""
    try:
        t = int(storage_turn)
    except (TypeError, ValueError):
        return 1
    return max(1, (t + 1) // 2)


def _message_role_str(msg: Any) -> str:
    if isinstance(msg, dict):
        return str(msg.get("role") or msg.get("type") or "user")
    role = getattr(msg, "role", None) or getattr(msg, "type", None)
    return str(role or "user")


def _raw_message_turn_int(msg: Any) -> Optional[int]:
    if isinstance(msg, dict):
        raw = msg.get("turn")
    else:
        raw = getattr(msg, "turn", None)
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _normalized_role(role: str) -> str:
    r = str(role or "").lower()
    if r in ("assistant", "ai"):
        return "assistant"
    if r in ("user", "human"):
        return "user"
    return "other"


def _detect_message_turn_style(messages: List[Any]) -> str:
    """
    message.turn 스타일 추정:
    - conversation: (user=1, assistant=1), (user=2, assistant=2) ...
    - storage:      (user=1, assistant=2), (user=3, assistant=4) ...

    모호하면 conversation(보수적)으로 간주해 오탐 변환을 막는다.
    """
    same_pairs = 0
    slot_pairs = 0
    prev_role = "other"
    prev_turn: Optional[int] = None

    for msg in messages or []:
        role = _normalized_role(_message_role_str(msg))
        turn = _raw_message_turn_int(msg)
        if turn is None:
            prev_role, prev_turn = role, turn
            continue

        if prev_role == "user" and role == "assistant" and prev_turn is not None:
            if turn == prev_turn:
                same_pairs += 1
            if turn == prev_turn + 1:
                slot_pairs += 1

        prev_role, prev_turn = role, turn

    if slot_pairs > same_pairs and slot_pairs > 0:
        return "storage"
    if same_pairs > 0:
        return "conversation"
    return "conversation"


def _normalize_scalar_to_conversation_turn(value: Any, conv_max_from_messages: int) -> int:
    """Redis legacy current_turn( storage slot ) → conversation turn."""
    try:
        v = int(value or 0)
    except (TypeError, ValueError):
        return max(0, conv_max_from_messages)
    if v <= 0:
        return max(0, conv_max_from_messages)
    as_conv = storage_slot_to_conversation_turn(v)
    # storage slot: 보통 conv_max보다 크고, 짝수 AI 슬롯(2N) 또는 홀수 USER(2N-1)
    if v > conv_max_from_messages + 1:
        return max(conv_max_from_messages, as_conv)
    return max(conv_max_from_messages, v)


def _normalize_guardrail_turn_entry(turn: int, conv_max: int) -> int:
    if turn <= conv_max + 1:
        return turn
    return storage_slot_to_conversation_turn(turn)


def _normalize_one_message_turn(msg: Any, style: str) -> int:
    """message.turn을 conversation turn으로 맞추고 conv 번호 반환."""
    role = _message_role_str(msg)
    if isinstance(msg, dict):
        raw = msg.get("turn")
        storage = msg.get("storage_turn")
        if storage is not None:
            try:
                conv = int(raw if raw is not None else storage_slot_to_conversation_turn(storage))
            except (TypeError, ValueError):
                conv = storage_slot_to_conversation_turn(storage)
            msg["turn"] = conv
            msg["storage_turn"] = int(storage)
            return conv
        if raw is None:
            return 0
        if style == "storage":
            conv = api_turn_to_conversation_turn(raw, role)
        else:
            try:
                conv = int(raw)
            except (TypeError, ValueError):
                conv = api_turn_to_conversation_turn(raw, role)
        try:
            raw_i = int(raw)
        except (TypeError, ValueError):
            raw_i = conv
        if style == "storage" and raw_i != conv:
            msg["storage_turn"] = raw_i
        msg["turn"] = conv
        return conv

    raw = getattr(msg, "turn", None)
    if raw is None:
        return 0
    if style == "storage":
        conv = api_turn_to_conversation_turn(raw, role)
    else:
        try:
            conv = int(raw)
        except (TypeError, ValueError):
            conv = api_turn_to_conversation_turn(raw, role)
    try:
        raw_i = int(raw)
    except (TypeError, ValueError):
        raw_i = conv
    if style == "storage" and raw_i != conv:
        setattr(msg, "storage_turn", raw_i)
    setattr(msg, "turn", conv)
    return conv


def normalize_state_turn_fields(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Redis/LangGraph state의 conversation vs storage turn 혼동을 보정.

    - messages[].turn → conversation turn, storage_turn 보존
    - current_turn / turn → messages 기준 및 legacy storage 값 정규화
    - guardrail_flag_turns → conversation turn 기준
    """
    if not state:
        return state

    messages = state.get("messages") or []
    style = _detect_message_turn_style(messages)

    conv_max = 0
    for msg in messages:
        c = _normalize_one_message_turn(msg, style)
        if c > conv_max:
            conv_max = c

    for field in ("current_turn", "turn"):
        if field in state and state[field] is not None:
            if style == "storage":
                state[field] = _normalize_scalar_to_conversation_turn(
                    state[field], conv_max
                )
            else:
                try:
                    state[field] = max(conv_max, int(state[field]))
                except (TypeError, ValueError):
                    state[field] = conv_max

    raw_gr = state.get("guardrail_flag_turns")
    if raw_gr is not None:
        normalized: List[int] = []
        for t in raw_gr:
            try:
                ti = int(t)
            except (TypeError, ValueError):
                continue
            nt = (
                _normalize_guardrail_turn_entry(ti, conv_max)
                if style == "storage"
                else ti
            )
            if nt not in normalized:
                normalized.append(nt)
        state["guardrail_flag_turns"] = sorted(normalized)

    raw_reasons = state.get("guardrail_turn_reasons")
    if isinstance(raw_reasons, dict) and raw_reasons:
        new_reasons: Dict[str, str] = {}
        for k, v in raw_reasons.items():
            try:
                nk = str(
                    _normalize_guardrail_turn_entry(int(k), conv_max)
                    if style == "storage"
                    else int(k)
                )
            except (TypeError, ValueError):
                nk = str(k)
            new_reasons[nk] = v
        state["guardrail_turn_reasons"] = new_reasons

    return state


def is_guardrail_blocked_response_text(ai_message: str) -> bool:
    """제출 시 fallback: 통일 prefix 또는 레거시 handle_failure 문구."""
    if not ai_message:
        return False
    text = ai_message.strip()
    if GUARDRAIL_USER_MESSAGE_PREFIX in text:
        return True
    if "시험 규정상 답변할 수 없습니다" in text:
        return True
    if "요청이 가이드라인을 위반" in text:
        return True
    return False
