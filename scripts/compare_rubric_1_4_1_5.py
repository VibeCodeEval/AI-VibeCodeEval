#!/usr/bin/env python
"""R1~R5 Likert 조합별 turn_score 비교 (compute_turn_score_v31)."""

from __future__ import annotations

import os
import sys
from itertools import product

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from app.domain.langgraph.nodes.eval_turn.grading import (  # noqa: E402
    compute_turn_score_v31,
    likert_to_final,
)


def score(intent: str, r1: int, r2: int, r3: int, r4: int = 3) -> tuple[int, int]:
    bd = {"R1": r1, "R2": r2, "R3": r3, "R4": r4}
    likert = compute_turn_score_v31(intent, bd)
    return likert, likert_to_final(likert)


def normalize_intent(raw_intent: str) -> str:
    intent = (raw_intent or "").strip().upper()
    if intent == "VALIDATION":
        return "DEBUGGING"
    if intent in {
        "CREATION",
        "SETTING",
        "REFINEMENT",
        "DEBUGGING",
        "EXPLORATION",
        "FOLLOW_UP",
    }:
        return intent
    return "CREATION"


def main() -> None:
    print("=" * 72)
    print("CREATION — R1=5 고정, R2×R3 (1~5) → likert / final(×20)")
    print("=" * 72)
    print(f"{'R2':>3} {'R3':>3} | {'likert':>6} {'final':>6}")
    print("-" * 72)
    for r2, r3 in product(range(1, 6), repeat=2):
        likert, final = score("CREATION", 5, r2, r3)
        mark = ""
        if (r2, r3) in ((1, 4), (1, 5), (4, 4), (4, 5), (5, 4), (5, 5)):
            mark = "  ← 1-4/1-5 대표"
        if (r2, r3) == (4, 4):
            mark = "  ← participant3 실측"
        if (r2, r3) in ((2, 2), (2, 1), (1, 2), (1, 1)):
            mark = "  ← 혼합 규칙 목표대"
        print(f"{r2:3} {r3:3} | {likert:6} {final:6}{mark}")

    print()
    print("=" * 72)
    print("1-4 vs 1-5 짝 비교 (CREATION) — 한 축만 4→5")
    print("=" * 72)
    pairs = [
        ("R2: 1→유지, R3: 4 vs 5", (5, 1, 4), (5, 1, 5)),
        ("R2: 4 vs 5, R3: 1", (5, 4, 1), (5, 5, 1)),
        ("R2: 4 vs 5, R3: 3", (5, 4, 3), (5, 5, 3)),
        ("R2: 4 vs 5, R3: 4", (5, 4, 4), (5, 5, 4)),
        ("participant3: 4,4 vs 2,2", (5, 4, 4), (5, 2, 2)),
        ("혼합 목표: 4,4 vs 1,1", (5, 4, 4), (5, 1, 1)),
    ]
    for label, a, b in pairs:
        la, fa = score("CREATION", *a)
        lb, fb = score("CREATION", *b)
        print(
            f"{label:28} {a} → L={la} F={fa:3}  |  {b} → L={lb} F={fb:3}  |  Δfinal={fb - fa:+d}"
        )

    print()
    print("=" * 72)
    print("의도별 — (1,4) vs (1,5) 패턴")
    print("=" * 72)
    scenarios_3 = [
        ("CREATION", (5, 1, 4), (5, 1, 5)),
        ("CREATION", (5, 4, 4), (5, 5, 5)),
        ("SETTING", (3, 1, 4), (3, 1, 5)),
        ("EXPLORATION", (1, 4, 3), (1, 5, 3)),
    ]
    for intent, a, b in scenarios_3:
        _, fa = score(intent, *a)
        _, fb = score(intent, *b)
        print(f"{intent:12} {a} vs {b}  →  {fa} vs {fb}  (Δ{fb - fa:+d})")

    scenarios_4 = [
        ("REFINEMENT", (3, 3, 3, 4), (3, 3, 3, 5)),
        ("DEBUGGING", (3, 1, 3, 4), (3, 1, 3, 5)),
        ("FOLLOW_UP", (3, 3, 3, 4), (3, 3, 3, 5)),
    ]
    for intent, a, b in scenarios_4:
        _, fa = score(intent, *a)
        _, fb = score(intent, *b)
        print(f"{intent:12} R4={a[3]} vs R4={b[3]}  (rest {a[:3]})  →  {fa} vs {fb}  (Δ{fb - fa:+d})")

    # export JSON if present
    export_path = os.path.join(project_root, "data", "_tmp_1_3.json")
    if os.path.isfile(export_path):
        import json

        print()
        print("=" * 72)
        print(f"실측 export: {export_path}")
        print("=" * 72)
        with open(export_path, encoding="utf-8") as f:
            data = json.load(f)
        turns = data.get("prompt_evaluations") or data.get("turn_evaluations") or []
        if isinstance(turns, dict):
            turns = list(turns.values())
        for te in sorted(turns, key=lambda x: x.get("turn") or 0):
            if not isinstance(te, dict):
                continue
            turn = te.get("turn")
            det = te.get("details") or te
            bd = det.get("rubric_breakdown") or {}
            intent = det.get("unified_intent") or det.get("intent") or "?"
            intent_for_calc = normalize_intent(str(intent))
            sc = det.get("score")
            if sc is None:
                sc = det.get("turn_score")
            if bd:
                r1, r2, r3, r4 = (
                    bd.get("R1") or 3,
                    bd.get("R2") or 3,
                    bd.get("R3") or 3,
                    bd.get("R4") or 3,
                )
                calc_l, calc_f = score(intent_for_calc, r1, r2, r3, r4)
                print(
                    f"  turn {turn} intent={intent}({intent_for_calc}) breakdown={bd} "
                    f"DB={sc} calc_likert={calc_l} calc_final={calc_f}"
                )


if __name__ == "__main__":
    main()
