import json
from pathlib import Path


def build_timeline(entry: dict) -> dict:
    rubric = entry.get("rubric_json") or {}
    debate_log = rubric.get("debate_log") or []

    round1 = [x for x in debate_log if x.get("round") == 1]
    round2 = [x for x in debate_log if x.get("round") == 2]
    verdict = next((x for x in debate_log if x.get("agent") == "verdict"), None)

    return {
        "submission_id": entry.get("submission_id"),
        "scores": {
            "prompt_score": entry.get("prompt_score"),
            "perf_score": entry.get("perf_score"),
            "correctness_score": entry.get("correctness_score"),
            "total_score": entry.get("total_score"),
        },
        "debate_summary": {
            "round1_count": len(round1),
            "round2_count": len(round2),
            "has_verdict": verdict is not None,
            "holistic_flow_score": rubric.get("holistic_flow_score"),
            "r4_context_maintenance_score": rubric.get("r4_context_maintenance_score"),
            "holistic_flow_analysis": rubric.get("holistic_flow_analysis"),
        },
        "timeline": {
            "round1": [
                {
                    "agent": x.get("agent"),
                    "suggested_score": x.get("suggested_score"),
                    "stance": x.get("stance"),
                    "key_points_count": len(x.get("key_points") or []),
                }
                for x in round1
            ],
            "round2": [
                {
                    "agent": x.get("agent"),
                    "suggested_score": x.get("suggested_score"),
                    "stance": x.get("stance"),
                    "key_points_count": len(x.get("key_points") or []),
                }
                for x in round2
            ],
            "verdict": (
                {
                    "grade": verdict.get("grade"),
                    "holistic_flow_score": verdict.get("holistic_flow_score"),
                    "r4_context_maintenance_score": verdict.get(
                        "r4_context_maintenance_score"
                    ),
                    "consensus_summary": verdict.get("consensus_summary"),
                }
                if verdict
                else None
            ),
        },
    }


def main() -> None:
    src = Path("tmp/latest_scores.json")
    dst = Path("tmp/latest_scores_debate_timeline.json")
    data = json.loads(src.read_text(encoding="utf-8"))

    result = {
        "count": data.get("count", 0),
        "items": [build_timeline(item) for item in data.get("scores", [])],
    }
    dst.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(dst))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
