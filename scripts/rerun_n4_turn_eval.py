#!/usr/bin/env python
"""
N4 턴 프롬프트 평가(eval_turn subgraph)만 재실행 — 로그/콘솔 출력 전용.

DB·Redis 저장 없음. PG prompt_messages에서 USER/AI만 읽습니다.

사용 예:
  uv run python scripts/rerun_n4_turn_eval.py --session-id 5 --current-turn 3
  uv run python scripts/rerun_n4_turn_eval.py --session-id 5 --turn 1 --turn 2
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


def _primary_eval_block(turn_log: dict, unified_intent: str) -> dict | None:
    evaluations = turn_log.get("evaluations") or {}
    key_map = {
        "SETTING": "rule_setting_eval",
        "CREATION": "generation_eval",
        "REFINEMENT": "optimization_eval",
        "DEBUGGING": "debugging_eval",
        "EXPLORATION": "exploration_eval",
        "FOLLOW_UP": "follow_up_eval",
    }
    key = key_map.get((unified_intent or "").upper().replace("-", "_"))
    if key and key in evaluations and isinstance(evaluations[key], dict):
        return evaluations[key]
    for v in evaluations.values():
        if isinstance(v, dict):
            return v
    return None


def _make_turn_state(
    session_id: str,
    turn: int,
    human: str,
    ai: str,
    previous_turns_summary: str | None,
    previous_turn_dialogue: str | None,
) -> dict:
    return {
        "session_id": session_id,
        "turn": turn,
        "human_message": human,
        "ai_message": ai,
        "previous_turns_summary": previous_turns_summary,
        "previous_turn_dialogue": previous_turn_dialogue,
        "is_phase2_first_turn": False,
        "problem_context": None,
        "is_guardrail_failed": False,
        "guardrail_message": None,
        "intent_types": None,
        "intent_confidence": 0.0,
        "unified_intent": None,
        "system_prompt_eval": None,
        "rule_setting_eval": None,
        "generation_eval": None,
        "optimization_eval": None,
        "debugging_eval": None,
        "test_case_eval": None,
        "hint_query_eval": None,
        "follow_up_eval": None,
        "answer_summary": None,
        "turn_log": None,
        "turn_score": None,
        "eval_tokens": None,
    }


async def _run(args: argparse.Namespace) -> int:
    from app.domain.langgraph.nodes.eval.eval_turn_targets import (
        eval_target_turn_numbers,
    )
    from app.domain.langgraph.subgraph_eval_turn import create_eval_turn_subgraph
    from app.domain.langgraph.utils.turn_dialogue import format_previous_turn_dialogue
    from app.domain.langgraph.utils.turn_messages import (
        fetch_turn_pair_from_prompt_messages,
        resolve_turn_pair_for_eval,
    )
    from app.domain.langgraph.utils.guardrail_turns import (
        is_guardrail_blocked_response_text,
    )

    pg_id = args.session_id
    session_id = f"session_{pg_id}"
    messages: list = []
    subgraph = create_eval_turn_subgraph()

    if args.turn:
        turns = sorted(set(args.turn))
    else:
        ct = args.current_turn
        if ct is None:
            ct = 1
            while True:
                human, ai = await fetch_turn_pair_from_prompt_messages(
                    session_id, ct
                )
                if not (human and ai):
                    break
                ct += 1
            ct += 1
        turns = eval_target_turn_numbers(ct)

    if not turns:
        print("평가할 턴이 없습니다. --current-turn 또는 --turn 을 확인하세요.", file=sys.stderr)
        return 1

    logger.info("=== N4 턴 평가 (로그 전용, DB/Redis 미저장) ===")
    logger.info("session_id=%s PG id=%s turns=%s", session_id, pg_id, turns)

    previous_turns_summaries: list[str] = []
    previous_turn_pairs: list[tuple[int, str, str]] = []
    results: list[dict] = []

    for turn in turns:
        human_msg, ai_msg, msg_source = await resolve_turn_pair_for_eval(
            messages, session_id, turn
        )
        if not (human_msg and ai_msg):
            logger.warning("턴 %s: 메시지 쌍 없음 (source=%s) — 스킵", turn, msg_source)
            continue

        prev_summary = (
            "\n\n".join(previous_turns_summaries)
            if previous_turns_summaries
            else None
        )
        prev_dialogue = format_previous_turn_dialogue(previous_turn_pairs)

        logger.info("")
        logger.info("--- Turn %s (source=%s) ---", turn, msg_source)
        logger.info("USER: %s", human_msg[:200] + ("..." if len(human_msg) > 200 else ""))

        if is_guardrail_blocked_response_text(ai_msg or ""):
            logger.info(
                "턴 %s: 가드레일 AI 응답 감지 — 프로덕션 N4는 0점·eval 스킵 (rerun은 LLM 호출 유지)",
                turn,
            )

        state = _make_turn_state(
            session_id, turn, human_msg, ai_msg, prev_summary, prev_dialogue
        )
        result = await subgraph.ainvoke(state)

        turn_score = result.get("turn_score", 0)
        unified = result.get("unified_intent") or ""
        intent_types = result.get("intent_types") or []
        turn_log = result.get("turn_log") or {}
        primary = _primary_eval_block(turn_log, unified) or {}
        breakdown = primary.get("rubric_breakdown") or {}
        scoring_cot = primary.get("scoring_cot") or {}
        applied = primary.get("applied_rubrics") or []
        reasoning = (
            turn_log.get("comprehensive_reasoning")
            or primary.get("final_reasoning")
            or ""
        )

        logger.info("intent: %s (%s)", unified, intent_types)
        logger.info("turn_score: %s", turn_score)
        logger.info("applied_rubrics: %s", applied)
        logger.info("rubric_breakdown: %s", json.dumps(breakdown, ensure_ascii=False))
        if scoring_cot:
            for rk, rv in scoring_cot.items():
                logger.info("scoring_cot[%s]: %s", rk, rv)
        if reasoning:
            logger.info("reasoning: %s", reasoning[:800] + ("..." if len(reasoning) > 800 else ""))

        print(
            f"\n[Turn {turn}] score={turn_score} intent={unified} "
            f"rubrics={breakdown}"
        )

        results.append(
            {
                "turn": turn,
                "turn_score": turn_score,
                "intent": unified,
                "rubric_breakdown": breakdown,
            }
        )

        user_line = result.get("request_one_liner") or human_msg[:200]
        ai_line = result.get("answer_summary") or ""
        previous_turns_summaries.append(
            f"[Turn {turn}] 사용자: {user_line}\nAI 요약: {ai_line}"
        )
        previous_turn_pairs.append((int(turn), human_msg, ai_msg))

    print("\n=== 완료 (저장 없음, 로그만) ===")
    for r in results:
        print(
            f"  turn {r['turn']}: score={r['turn_score']} "
            f"intent={r['intent']} breakdown={r['rubric_breakdown']}"
        )
    return 0 if results else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="N4 턴 프롬프트 평가 재실행 (로그/콘솔만, DB·Redis 미저장)",
    )
    parser.add_argument("--session-id", type=int, required=True)
    parser.add_argument("--current-turn", type=int)
    parser.add_argument("--turn", type=int, action="append")
    args = parser.parse_args()

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
