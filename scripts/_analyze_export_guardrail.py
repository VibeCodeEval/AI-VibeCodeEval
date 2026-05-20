"""export JSON에서 가드레일 턴 제외 여부 요약."""
import json
import sys
from pathlib import Path

path = Path(sys.argv[1] if len(sys.argv) > 1 else "data/6_3_eval_check.json")
d = json.loads(path.read_text(encoding="utf-8"))
meta = d["meta"]
print("=== META ===")
print(
    f"session_id={meta['session_id']} exam={meta['exam_id']} "
    f"participant={meta['participant_id']} problem_id={meta.get('problem_id')} "
    f"spec_id={meta['spec_id']}"
)

msgs = d["single_turn_evaluation"]["prompt_messages"]
print("\n=== MESSAGES ===")
for m in msgs:
    mt = m.get("meta") or {}
    head = (m["content"] or "")[:55].replace("\n", " ")
    print(
        f"  turn={m['turn']} role={m['role']} "
        f"gr={mt.get('is_guardrail_failed')} reason={mt.get('block_reason')} | {head}"
    )

evals = d["single_turn_evaluation"]["evaluations"]
print("\n=== TURN_EVAL ===")
for e in evals:
    det = e.get("details") or {}
    ped = det.get("prompt_evaluation_details") or det
    if not isinstance(ped, dict):
        ped = {}
    print(
        f"  turn={e.get('turn')} score={ped.get('score')} intent={ped.get('intent')} "
        f"gr={det.get('is_guardrail_failed') or ped.get('is_guardrail_failed')} "
        f"block_reason={ped.get('block_reason')}"
    )

debate = d.get("debate_redis") or {}
for key in ("turn_logs", "turn_logs_for_debate", "filtered_turn_logs"):
    tl = debate.get(key)
    if isinstance(tl, dict):
        print(f"\n=== DEBATE {key} keys ===")
        print(" ", sorted(tl.keys(), key=lambda x: int(x) if str(x).isdigit() else 0))
        for k, v in sorted(tl.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0):
            if isinstance(v, dict):
                ped = v.get("prompt_evaluation_details") or {}
                print(
                    f"    {k}: intent={ped.get('intent')} score={ped.get('score')} "
                    f"gr={v.get('is_guardrail_failed')}"
                )

score = (d.get("code_scores") or {}).get("score") or {}
rj = score.get("rubric_json") or {}
print("\n=== prompt_score ===", score.get("prompt_score"))
te = rj.get("turn_evaluations")
if te:
    print("=== rubric_json.turn_evaluations ===")
    items = te.items() if isinstance(te, dict) else enumerate(te)
    for k, v in (items if isinstance(te, dict) else [(i, x) for i, x in enumerate(te)]):
        if isinstance(v, dict):
            print(f"  {k}: score={v.get('score')} intent={v.get('intent')}")
