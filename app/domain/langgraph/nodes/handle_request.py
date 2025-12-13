"""
노드 1: Handle Request Load State
요청을 받아 상태를 로드하고 초기화
"""
import logging
from datetime import datetime
from typing import Dict, Any

from app.domain.langgraph.states import MainGraphState
from app.domain.langgraph.utils.problem_info import get_problem_info, get_problem_info_sync
from app.infrastructure.persistence.session import get_db_context

logger = logging.getLogger(__name__)


async def handle_request_load_state(state: MainGraphState) -> Dict[str, Any]:
    """
    요청 처리 및 상태 로드
    
    - 세션 정보 확인
    - 이전 상태 로드 (Redis에서)
    - 현재 턴 번호 증가
    - 문제 정보 확인 및 추가 (없는 경우)
    - 초기 상태 설정
    """
    session_id = state.get("session_id", "unknown")
    current_turn = state.get("current_turn", 0)
    new_turn = current_turn + 1
    spec_id = state.get("spec_id")
    
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
        
        # 문제 정보가 없으면 추가 (기존 State 로드 시 문제 정보가 없을 수 있음)
        if not state.get("problem_context") and spec_id:
            # DB 조회 시도 (실패 시 하드코딩 딕셔너리로 Fallback)
            problem_context = None
            try:
                async with get_db_context() as db:
                    problem_context = await get_problem_info(spec_id, db)
                    logger.debug(f"[1. Handle Request] DB에서 문제 정보 조회 성공 - spec_id: {spec_id}")
            except Exception as e:
                logger.warning(f"[1. Handle Request] DB 조회 실패, 하드코딩 딕셔너리 사용 - spec_id: {spec_id}, error: {str(e)}")
                # Fallback: 하드코딩 딕셔너리 사용
            problem_context = get_problem_info_sync(spec_id)
            
            # 1. problem_context 저장 (새 구조)
            result["problem_context"] = problem_context
            
            # 2. 개별 필드도 저장 (하위 호환성 유지)
            basic_info = problem_context.get("basic_info", {})
            ai_guide = problem_context.get("ai_guide", {})
            
            result.update({
                "problem_id": basic_info.get("problem_id"),
                "problem_name": basic_info.get("title"),
                "problem_algorithm": ai_guide.get("key_algorithms", [None])[0] if ai_guide.get("key_algorithms") else None,
                "problem_keywords": problem_context.get("keywords", []),
            })
            
            problem_name = basic_info.get("title", "알 수 없음")
            source = "DB" if problem_context.get("content_md") else "하드코딩"
            logger.debug(f"[1. Handle Request] 문제 정보 추가 - spec_id: {spec_id}, problem_name: {problem_name}, source: {source}")
        
        logger.info(f"[1. Handle Request] 완료 - session_id: {session_id}, 턴: {new_turn}")
        return result
        
    except Exception as e:
        logger.error(f"[1. Handle Request] 오류 - session_id: {session_id}, error: {str(e)}", exc_info=True)
        raise



