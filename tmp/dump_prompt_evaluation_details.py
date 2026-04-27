import asyncio
import json
from pathlib import Path

from sqlalchemy import text

from app.infrastructure.persistence.session import AsyncSessionLocal


async def main() -> None:
    out = Path("tmp/latest_prompt_evaluation_details.json")
    out.parent.mkdir(parents=True, exist_ok=True)

    async with AsyncSessionLocal() as db:
        await db.execute(text("SET search_path TO ai_vibe_coding_test"))
        result = await db.execute(
            text(
                """
                SELECT
                    pe.id,
                    pe.session_id,
                    pe.turn,
                    pe.evaluation_type::text AS evaluation_type,
                    pe.details,
                    pe.created_at
                FROM prompt_evaluations pe
                WHERE pe.evaluation_type::text = 'TURN_EVAL'
                ORDER BY pe.created_at DESC, pe.id DESC
                LIMIT 20
                """
            )
        )

        rows = []
        for row in result.mappings().all():
            details = row.get("details") or {}
            item = {
                "id": row.get("id"),
                "session_id": row.get("session_id"),
                "turn": row.get("turn"),
                "evaluation_type": row.get("evaluation_type"),
                "created_at": (
                    row.get("created_at").isoformat() if row.get("created_at") else None
                ),
                # DB details를 prompt_evaluation_details 관점으로 재구성
                "prompt_evaluation_details": {
                    "score": details.get("score"),
                    "analysis": details.get("analysis"),
                    "intent": details.get("intent"),
                    "intent_types": details.get("intent_types"),
                    "unified_intent": details.get("unified_intent"),
                    "intent_confidence": details.get("intent_confidence"),
                    "turn_score": details.get("turn_score"),
                    "rubrics": details.get("rubrics"),
                    "rubric_breakdown": details.get("rubric_breakdown"),
                    "applied_rubrics": details.get("applied_rubrics"),
                    "scoring_cot": details.get("scoring_cot"),
                    "weights": details.get("weights"),
                    "is_guardrail_failed": details.get("is_guardrail_failed"),
                    "guardrail_message": details.get("guardrail_message"),
                    "user_prompt_summary": details.get("user_prompt_summary"),
                    "llm_answer_summary": details.get("llm_answer_summary"),
                    "llm_answer_reasoning": details.get("llm_answer_reasoning"),
                },
            }
            rows.append(item)

    payload = {"count": len(rows), "items": rows}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(out))
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
