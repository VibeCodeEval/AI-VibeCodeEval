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

    turns = get_guardrail_flag_turns(state)
    if t not in turns:
        turns.append(t)
        turns.sort()

    reasons = get_guardrail_turn_reasons(state)
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


def filter_turn_logs_for_debate(
    turn_logs: Dict[str, Any],
    state: Dict[str, Any],
) -> Dict[str, Any]:
    """N8 토론: 가드레일 턴 로그 제외 (0점은 turn_scores 평균에만 반영)."""
    blocked = set(get_guardrail_flag_turns(state))
    filtered: Dict[str, Any] = {}
    for key, log in (turn_logs or {}).items():
        if not isinstance(log, dict):
            continue
        try:
            t = int(key)
        except (TypeError, ValueError):
            t = None
        if t is not None and t in blocked:
            continue
        ped = log.get("prompt_evaluation_details") or {}
        if log.get("is_guardrail_failed"):
            continue
        if ped.get("intent") == "GUARDRAIL_BLOCKED":
            continue
        filtered[key] = log
    return filtered


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
