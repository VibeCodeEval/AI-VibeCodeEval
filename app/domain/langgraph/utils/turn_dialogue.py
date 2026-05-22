"""N4 eval_turn — 이전 conversation turn USER/AI 본문 블록."""

from __future__ import annotations

from typing import List, Sequence, Tuple

# (conversation_turn, human_content, ai_content)
TurnPair = Tuple[int, str, str]

DEFAULT_USER_TRUNC = 6_000
DEFAULT_AI_TRUNC = 8_000
DEFAULT_MAX_PRIOR_TURNS = 3


def _truncate(text: str, max_chars: int, label: str) -> str:
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 24] + f"\n…({label} 발췌 생략)"


def format_previous_turn_dialogue(
    prior_pairs: Sequence[TurnPair],
    *,
    max_turns: int = DEFAULT_MAX_PRIOR_TURNS,
    user_max_chars: int = DEFAULT_USER_TRUNC,
    ai_max_chars: int = DEFAULT_AI_TRUNC,
) -> str:
    """
    턴 N 평가 시 1..N-1 대화를 프롬프트에 넣기 위한 블록.
    평가 대상은 항상 *이번* 턴 human/ai; 이 블록은 해석 맥락만 제공.
    """
    if not prior_pairs:
        return "(이전 턴 대화 없음 — 첫 번째 턴입니다.)"

    pairs: List[TurnPair] = list(prior_pairs)
    if len(pairs) > max_turns:
        pairs = pairs[-max_turns:]

    lines: List[str] = [
        "아래는 **이번 턴 이전** 사용자·AI 교환입니다 (평가 대상 본문이 아님).",
        "",
    ]
    for turn_no, human, ai in pairs:
        lines.append(f"#### [이전 턴 {turn_no}] USER")
        lines.append(_truncate(human, user_max_chars, "USER"))
        lines.append(f"#### [이전 턴 {turn_no}] AI")
        lines.append(_truncate(ai, ai_max_chars, "AI"))
        lines.append("")

    lines.append(
        "**포함 범위:** 각 이전 턴은 **USER와 AI 응답 모두** 표시됩니다 (요약만이 아님). "
        "후속·참조 턴 채점 시 **[이전 턴 N] AI** 로드맵·분해·코드를 반드시 확인하십시오."
    )
    lines.append(
        "**해석 규칙:** 이번 턴 `text`·`ai_message`만 Rn 채점 대상. "
        "위 대화는 R2·R3·R4 및 REFINEMENT의 R1(범위·연결) **해석**에만 사용. "
        "이전 턴 USER에 붙은 스펙 **완전성**으로 이번 턴 R1(스펙)·R3를 올리지 마십시오."
    )
    return "\n".join(lines)
