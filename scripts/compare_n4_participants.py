#!/usr/bin/env python
"""exam 1 participant N4(TURN_EVAL) export 비교."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from app.domain.langgraph.nodes.eval_turn.grading import (  # noqa: E402
    compute_turn_score_v31,
    likert_to_final,
)
from app.domain.langgraph.prompts.eval_turn_compose import (  # noqa: E402
    eval_turn_compose_metadata,
    resolve_turn_archetype_gate,
)


def load_export(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def n4_rows(data: dict) -> list[dict]:
    rows = []
    for e in data.get("single_turn_evaluation", {}).get("evaluations") or []:
        d = e.get("details") or {}
        bd = d.get("rubric_breakdown") or {}
        ui = (d.get("unified_intent") or d.get("intent") or "").upper()
        gate = resolve_turn_archetype_gate(
            {
                "problem_in_turn": d.get("problem_in_turn"),
                "user_request_in_turn": d.get("user_request_in_turn"),
                "previous_turn_dialogue": "이전 턴 대화 없음",
            }
        )
        calc_l = compute_turn_score_v31(ui, bd) if bd else None
        calc_f = likert_to_final(calc_l) if calc_l else None
        rows.append(
            {
                "turn": e.get("turn"),
                "score_db": d.get("score") or d.get("turn_score"),
                "intent": ui,
                "problem_in_turn": d.get("problem_in_turn"),
                "user_request_in_turn": d.get("user_request_in_turn"),
                "breakdown": bd,
                "applied": d.get("applied_rubrics"),
                "one_liner": d.get("request_one_liner"),
                "gate_replay": gate,
                "calc_likert": calc_l,
                "calc_final": calc_f,
                "match": calc_f == d.get("score") if calc_f and d.get("score") else None,
            }
        )
    return sorted(rows, key=lambda x: x["turn"] or 0)


def main() -> None:
    paths = {
        4: project_root / "data" / "1_4_평가.json",
        5: project_root / "data" / "1_5_평가.json",
    }
    all_data = {}
    for pid, path in paths.items():
        data = load_export(path)
        meta = data["meta"]
        rows = n4_rows(data)
        code = (data.get("code_scores") or {}).get("score")
        all_data[pid] = {"meta": meta, "rows": rows, "code": code, "messages": len(
            data.get("single_turn_evaluation", {}).get("prompt_messages") or []
        )}

        print("=" * 72)
        print(f"participant {pid} | session_id={meta['session_id']} | messages={all_data[pid]['messages']}")
        print(f"  started={meta.get('started_at')} ended={meta.get('ended_at')}")
        if code:
            print(
                f"  BE: prompt={code.get('prompt_score')} perf={code.get('perf_score')} "
                f"correctness={code.get('correctness_score')} total={code.get('total_score')}"
            )
        for r in rows:
            print(
                f"  [N4 turn {r['turn']}] {r['intent']} | "
                f"problem={r['problem_in_turn']} request={r['user_request_in_turn']} | "
                f"gate~{r['gate_replay']}"
            )
            print(f"    breakdown={r['breakdown']} → DB={r['score_db']} calc={r['calc_final']} match={r['match']}")
            print(f"    one_liner: {(r['one_liner'] or '')[:90]}")
        if not rows:
            print("  (TURN_EVAL 없음)")
        print()

    # side-by-side by conversation turn (storage turn mapping differs)
    print("=" * 72)
    print("요약 비교 (N4 conversation turn 기준)")
    print("=" * 72)
    print(f"{'pid':>3} {'turn':>4} {'intent':>12} {'R1':>3} {'R2':>3} {'R3':>3} {'R4':>3} {'score':>6} {'gate':>16}")
    for pid in (4, 5):
        for r in all_data[pid]["rows"]:
            bd = r["breakdown"]
            print(
                f"{pid:3} {r['turn']:4} {r['intent']:12} "
                f"{bd.get('R1','-'):>3} {bd.get('R2','-'):>3} {bd.get('R3','-'):>3} {bd.get('R4','-'):>3} "
                f"{r['score_db'] or 0:6.0f} {r['gate_replay']:>16}"
            )

    # aggregate if multiple turns
    for pid in (4, 5):
        rows = all_data[pid]["rows"]
        if rows:
            avg = sum(r["score_db"] or 0 for r in rows) / len(rows)
            print(f"\nparticipant {pid}: N4 턴 수={len(rows)}, 턴 점수 평균(단순)={avg:.1f}")


if __name__ == "__main__":
    main()
