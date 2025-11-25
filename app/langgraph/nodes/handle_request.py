"""
노드 1: Handle Request Load State
요청을 받아 상태를 로드하고 초기화
"""
from datetime import datetime
from typing import Dict, Any

from app.langgraph.states import MainGraphState


async def handle_request_load_state(state: MainGraphState) -> Dict[str, Any]:
    """
    요청 처리 및 상태 로드
    
    - 세션 정보 확인
    - 이전 상태 로드 (Redis에서)
    - 현재 턴 번호 증가
    - 초기 상태 설정
    """
    current_turn = state.get("current_turn", 0) + 1
    
    return {
        "current_turn": current_turn,
        "is_guardrail_failed": False,
        "guardrail_message": None,
        "writer_status": None,
        "writer_error": None,
        "error_message": None,
        "updated_at": datetime.utcnow().isoformat(),
    }



