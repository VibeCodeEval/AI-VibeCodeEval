import asyncio
import json
from pathlib import Path

from sqlalchemy import text

from app.infrastructure.persistence.session import AsyncSessionLocal


async def main() -> None:
    out_path = Path("tmp/n5_judge0_inspect.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    async with AsyncSessionLocal() as db:
        await db.execute(text("SET search_path TO ai_vibe_coding_test"))

        recent_submissions = (
            await db.execute(
                text(
                    """
                    SELECT
                        s.id AS submission_id,
                        s.status::text AS status,
                        sc.created_at AS score_created_at,
                        sc.rubric_json->'performance_details'->>'execution_time' AS execution_time,
                        sc.rubric_json->'performance_details'->>'memory_used_mb' AS memory_used_mb,
                        sc.rubric_json->'correctness_details'->>'test_cases_passed' AS test_cases_passed,
                        sc.rubric_json->'correctness_details'->>'test_cases_total' AS test_cases_total
                    FROM submissions s
                    LEFT JOIN scores sc ON sc.submission_id = s.id
                    ORDER BY s.id DESC
                    LIMIT 5
                    """
                )
            )
        ).mappings().all()

        recent_runs = (
            await db.execute(
                text(
                    """
                    SELECT
                        submission_id,
                        case_index,
                        grp::text AS grp,
                        verdict::text AS verdict,
                        time_ms,
                        mem_kb,
                        stdout_bytes,
                        stderr_bytes,
                        created_at
                    FROM submission_runs
                    ORDER BY id DESC
                    LIMIT 20
                    """
                )
            )
        ).mappings().all()

    payload = {
        "recent_submissions": [dict(row) for row in recent_submissions],
        "recent_submission_runs": [dict(row) for row in recent_runs],
    }

    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(str(out_path))
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
