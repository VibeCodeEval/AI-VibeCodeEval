import asyncio
import json
from pathlib import Path

from sqlalchemy import text

from app.infrastructure.persistence.session import AsyncSessionLocal


async def main() -> None:
    out = Path("tmp/latest_scores.json")
    out.parent.mkdir(parents=True, exist_ok=True)

    async with AsyncSessionLocal() as db:
        await db.execute(text("SET search_path TO ai_vibe_coding_test"))
        result = await db.execute(
            text(
                """
                SELECT
                    submission_id,
                    prompt_score,
                    perf_score,
                    correctness_score,
                    total_score,
                    rubric_json,
                    created_at
                FROM scores
                ORDER BY created_at DESC NULLS LAST, submission_id DESC
                LIMIT 5
                """
            )
        )

        rows = []
        for row in result.mappings().all():
            item = dict(row)
            for key in ("prompt_score", "perf_score", "correctness_score", "total_score"):
                if item.get(key) is not None:
                    item[key] = float(item[key])
            if item.get("created_at") is not None:
                item["created_at"] = item["created_at"].isoformat()
            rows.append(item)

    payload = {"count": len(rows), "scores": rows}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(out))
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
