import logging
from datetime import datetime
from typing import Any, Dict

from app.domain.langgraph.states import MainGraphState

logger = logging.getLogger(__name__)


async def aggregate_turn_scores(state: MainGraphState) -> Dict[str, Any]:
    """
    Node 7: 누적 실시간 점수 집계

    각 턴별 점수를 집계하여 평균 계산
    """
    session_id = state.get("session_id", "unknown")
    logger.info(f"[N7. Aggregate Turn Scores] 진입 - session_id: {session_id}")

    try:
        turn_scores = state.get("turn_scores", {})

        if not turn_scores:
            logger.warning(
                f"[N7. Aggregate Turn Scores] 턴 점수 없음 - session_id: {session_id}"
            )
            return {
                "aggregate_turn_score": None,
                "updated_at": datetime.utcnow().isoformat(),
            }

        all_scores = []
        for turn, scores in turn_scores.items():
            if isinstance(scores, dict) and "turn_score" in scores:
                all_scores.append(scores["turn_score"])

        if not all_scores:
            logger.warning(
                f"[N7. Aggregate Turn Scores] 유효한 점수 없음 - session_id: {session_id}"
            )
            return {
                "aggregate_turn_score": None,
                "updated_at": datetime.utcnow().isoformat(),
            }

        avg_score = sum(all_scores) / len(all_scores)

        logger.info(
            f"[N7. Aggregate Turn Scores] 완료 - session_id: {session_id}, 턴 개수: {len(all_scores)}, 평균: {avg_score:.2f}"
        )

        return {
            "aggregate_turn_score": round(avg_score, 2),
            "updated_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(
            f"[N7. Aggregate Turn Scores] 오류 - session_id: {session_id}, error: {str(e)}",
            exc_info=True,
        )
        return {
            "aggregate_turn_score": None,
            "error_message": f"턴 점수 집계 실패: {str(e)}",
            "updated_at": datetime.utcnow().isoformat(),
        }
