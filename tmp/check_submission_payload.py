import asyncio
import json

from sqlalchemy import text

from app.infrastructure.persistence.session import AsyncSessionLocal


async def main() -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET search_path TO ai_vibe_coding_test"))
        sub = (
            await db.execute(
                text(
                    """
                    SELECT id, status::text AS status, lang, code_inline, code_bytes, code_loc
                    FROM submissions
                    WHERE id = 6
                    """
                )
            )
        ).mappings().first()

    payload = {
        "submission_exists": sub is not None,
        "submission_id": sub["id"] if sub else None,
        "status": sub["status"] if sub else None,
        "lang": sub["lang"] if sub else None,
        "code_length": len(sub["code_inline"]) if sub and sub.get("code_inline") else 0,
        "code_bytes": sub["code_bytes"] if sub else None,
        "code_loc": sub["code_loc"] if sub else None,
        "code_preview": (sub["code_inline"][:180] if sub and sub.get("code_inline") else None),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
