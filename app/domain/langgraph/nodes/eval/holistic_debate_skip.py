"""N8 스킵 시 FE·rubric_json용 플레이스홀더 (LLM 토론 없음)."""

from __future__ import annotations

from typing import Any, Dict, List

HOLISTIC_DEBATE_SKIP_MESSAGE = "프롬프트 미제출로 평가 스킵"


def _skip_opinion(agent: str, round_num: int) -> Dict[str, Any]:
    msg = HOLISTIC_DEBATE_SKIP_MESSAGE
    return {
        "agent": agent,
        "round": round_num,
        "stance": msg,
        "key_points": [msg],
        "suggested_score": 0.0,
        "code_quality_assessment": msg,
        "prompt_quality_assessment": msg,
    }


def build_skipped_holistic_debate_result() -> Dict[str, Any]:
    """
    가드레일만 있거나 평가 가능한 프롬프트 턴이 없을 때 N8 대체 출력.

    holistic_flow_score·R4는 0, debate_log는 strict/advocate/neutral + verdict 형태.
    """
    initial: List[Dict[str, Any]] = [
        _skip_opinion("strict", 1),
        _skip_opinion("advocate", 1),
        _skip_opinion("neutral", 1),
    ]
    rebuttals: List[Dict[str, Any]] = [
        _skip_opinion("strict", 2),
        _skip_opinion("advocate", 2),
        _skip_opinion("neutral", 2),
    ]
    msg = HOLISTIC_DEBATE_SKIP_MESSAGE
    verdict = {
        "agent": "verdict",
        "round": 0,
        "holistic_flow_score": 0.0,
        "r4_context_maintenance_score": 0.0,
        "grade": "F",
        "consensus_summary": msg,
    }
    debate_log = initial + rebuttals + [verdict]
    holistic_flow_analysis = (
        f"[합의 요약] {msg}\n\n"
        f"[종합 분석] {msg}\n\n"
        f"[점수 근거] {msg}\n\n"
        f"[R4 맥락 유지] 0.0/100 (turn_scores 궤적 기반 수석 심사관 산정)"
    )
    return {
        "holistic_flow_score": 0.0,
        "r4_context_maintenance_score": 0.0,
        "holistic_flow_analysis": holistic_flow_analysis,
        "debate_log": debate_log,
        "debate_initial_opinions": initial,
        "debate_rebuttals": rebuttals,
    }
