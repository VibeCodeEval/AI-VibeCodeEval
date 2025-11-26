"""
노드 1: Handle Request Load State
요청을 받아 상태를 로드하고 초기화
"""
import logging
from datetime import datetime
from typing import Dict, Any

from app.langgraph.states import MainGraphState

logger = logging.getLogger(__name__)


async def handle_request_load_state(state: MainGraphState) -> Dict[str, Any]:
    """
    요청 처리 및 상태 로드
    
    - 세션 정보 확인
    - 이전 상태 로드 (Redis에서)
    - 현재 턴 번호 증가
    - 초기 상태 설정
    """
    session_id = state.get("session_id", "unknown")
    current_turn = state.get("current_turn", 0)
    new_turn = current_turn + 1
    
    logger.info(f"[1. Handle Request] 진입 - session_id: {session_id}, 이전 턴: {current_turn}, 새 턴: {new_turn}")
    
    try:
        result = {
            "current_turn": new_turn,
            "is_guardrail_failed": False,
            "guardrail_message": None,
            "writer_status": None,
            "writer_error": None,
            "error_message": None,
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        logger.info(f"[1. Handle Request] 완료 - session_id: {session_id}, 턴: {new_turn}")
        return result
        
    except Exception as e:
        logger.error(f"[1. Handle Request] 오류 - session_id: {session_id}, error: {str(e)}", exc_info=True)
        raise



