"""
콜백 서비스
Spring Boot로 결과 전송
"""
from typing import Dict, Any, Optional
import logging

import httpx

from app.core.config import settings


logger = logging.getLogger(__name__)


class CallbackService:
    """Spring Boot 콜백 서비스"""
    
    def __init__(self):
        self.callback_url = settings.SPRING_CALLBACK_URL
        self.api_key = settings.SPRING_API_KEY
        self.timeout = 30.0
    
    def _get_headers(self) -> Dict[str, str]:
        """요청 헤더 생성"""
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers
    
    async def send_message_response(
        self,
        session_id: str,
        turn: int,
        ai_message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        메시지 응답 전송
        
        Args:
            session_id: 세션 ID
            turn: 턴 번호
            ai_message: AI 응답 메시지
            metadata: 추가 메타데이터
        
        Returns:
            성공 여부
        """
        payload = {
            "type": "message_response",
            "session_id": session_id,
            "turn": turn,
            "ai_message": ai_message,
            "metadata": metadata or {},
        }
        
        return await self._send_callback(payload)
    
    async def send_turn_evaluation(
        self,
        session_id: str,
        turn: int,
        turn_log: Dict[str, Any],
        turn_score: float,
    ) -> bool:
        """
        턴 평가 결과 전송
        
        Args:
            session_id: 세션 ID
            turn: 턴 번호
            turn_log: 턴 로그
            turn_score: 턴 점수
        
        Returns:
            성공 여부
        """
        payload = {
            "type": "turn_evaluation",
            "session_id": session_id,
            "turn": turn,
            "turn_log": turn_log,
            "turn_score": turn_score,
        }
        
        return await self._send_callback(payload)
    
    async def send_final_scores(
        self,
        session_id: str,
        exam_id: int,
        participant_id: int,
        submission_id: Optional[int],
        final_scores: Dict[str, Any],
        turn_scores: Dict[str, Any],
    ) -> bool:
        """
        최종 점수 전송
        
        Args:
            session_id: 세션 ID
            exam_id: 시험 ID
            participant_id: 참가자 ID
            submission_id: 제출 ID
            final_scores: 최종 점수
            turn_scores: 턴별 점수
        
        Returns:
            성공 여부
        """
        payload = {
            "type": "final_scores",
            "session_id": session_id,
            "exam_id": exam_id,
            "participant_id": participant_id,
            "submission_id": submission_id,
            "final_scores": final_scores,
            "turn_scores": turn_scores,
        }
        
        return await self._send_callback(payload)
    
    async def send_error(
        self,
        session_id: str,
        error_type: str,
        error_message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        에러 전송
        
        Args:
            session_id: 세션 ID
            error_type: 에러 유형
            error_message: 에러 메시지
            metadata: 추가 메타데이터
        
        Returns:
            성공 여부
        """
        payload = {
            "type": "error",
            "session_id": session_id,
            "error_type": error_type,
            "error_message": error_message,
            "metadata": metadata or {},
        }
        
        return await self._send_callback(payload)
    
    async def _send_callback(self, payload: Dict[str, Any]) -> bool:
        """
        콜백 전송 (내부)
        
        Args:
            payload: 전송할 데이터
        
        Returns:
            성공 여부
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.callback_url,
                    json=payload,
                    headers=self._get_headers(),
                )
                
                if response.status_code == 200:
                    logger.info(f"콜백 전송 성공: {payload.get('type')}")
                    return True
                else:
                    logger.warning(
                        f"콜백 전송 실패: status={response.status_code}, "
                        f"body={response.text}"
                    )
                    return False
                    
        except httpx.TimeoutException:
            logger.error(f"콜백 전송 타임아웃: {self.callback_url}")
            return False
        except Exception as e:
            logger.error(f"콜백 전송 오류: {str(e)}", exc_info=True)
            return False
    
    async def health_check(self) -> bool:
        """Spring Boot 서버 헬스체크"""
        try:
            health_url = self.callback_url.replace("/ai/callback", "/health")
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(health_url)
                return response.status_code == 200
        except Exception:
            return False



