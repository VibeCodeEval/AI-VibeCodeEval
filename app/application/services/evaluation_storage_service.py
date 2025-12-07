"""
평가 결과 저장 서비스
4번 노드 (eval_turn) 및 6.a 노드 (eval_holistic_flow) 평가 결과를 PostgreSQL에 저장

[목적]
- 턴별 평가 결과를 prompt_evaluations 테이블에 저장
- 전체 평가 결과를 prompt_evaluations 테이블에 저장

[저장 시점]
1. 백그라운드 평가 완료 시 (Eval Turn SubGraph 완료 후)
2. 제출 시 동기 평가 완료 시 (eval_turn_guard에서 _evaluate_turn_sync 호출 후)
3. 6.a 노드 평가 완료 시 (eval_holistic_flow 완료 후)
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.repositories.session_repository import SessionRepository
from app.infrastructure.persistence.models.sessions import PromptEvaluation, PromptMessage
from app.infrastructure.persistence.models.enums import EvaluationTypeEnum
from sqlalchemy import select

logger = logging.getLogger(__name__)


class EvaluationStorageService:
    """평가 결과 저장 서비스"""
    
    def __init__(self, db: AsyncSession):
        """
        Args:
            db: PostgreSQL 세션
        """
        self.db = db
        self.session_repo = SessionRepository(db)
    
    async def save_turn_evaluation(
        self,
        session_id: int,
        turn: int,
        turn_log: Dict[str, Any]
    ) -> Optional[PromptEvaluation]:
        """
        4번 노드 (eval_turn) 평가 결과 저장
        
        [저장 데이터]
        - evaluation_type: 'TURN_EVAL'
        - turn: 턴 번호 (NOT NULL)
        - details: 모든 평가 데이터 (score, analysis, rubrics, intent, evaluations 등)
        
        Args:
            session_id: 세션 ID (PostgreSQL id)
            turn: 턴 번호
            turn_log: Redis에서 가져온 turn_log (aggregate_turn_log 결과)
        
        Returns:
            생성된 PromptEvaluation 또는 None (실패 시)
        """
        try:
            # turn_log에서 평가 정보 추출
            prompt_eval_details = turn_log.get("prompt_evaluation_details", {})
            score = prompt_eval_details.get("score")
            analysis = turn_log.get("comprehensive_reasoning") or prompt_eval_details.get("final_reasoning")
            
            # details에 모든 평가 데이터 포함
            details = {
                "score": score,  # 점수
                "analysis": analysis,  # 분석 내용
                "intent": prompt_eval_details.get("intent"),
                "intent_types": turn_log.get("intent_types", []),
                "rubrics": prompt_eval_details.get("rubrics", []),
                "evaluations": turn_log.get("evaluations", {}),
                "detailed_feedback": turn_log.get("detailed_feedback", []),
                "turn_score": turn_log.get("turn_score"),
                "is_guardrail_failed": turn_log.get("is_guardrail_failed", False),
                "guardrail_message": turn_log.get("guardrail_message"),
            }
            
            # 기존 평가 결과 확인 (중복 방지)
            existing = await self._get_existing_evaluation(
                session_id=session_id,
                turn=turn,
                evaluation_type=EvaluationTypeEnum.TURN_EVAL
            )
            
            if existing:
                # 기존 평가 결과 업데이트
                existing.details = details
                existing.created_at = datetime.utcnow()
                
                await self.db.flush()
                logger.info(
                    f"[EvaluationStorage] 턴 평가 업데이트 - "
                    f"session_id: {session_id}, turn: {turn}, score: {score}"
                )
                return existing
            else:
                # 제약 조건 검증: TURN_EVAL이면 turn은 NOT NULL이어야 함
                if turn is None:
                    logger.error(
                        f"[EvaluationStorage] 제약 조건 위반 - "
                        f"TURN_EVAL은 turn이 NOT NULL이어야 합니다. session_id: {session_id}"
                    )
                    return None
                
                # Foreign Key 제약 조건을 위해 메시지가 존재하는지 확인
                # (백엔드에서 메시지를 생성하므로, 평가 저장 시점에는 메시지가 이미 존재해야 함)
                message_query = select(PromptMessage).where(
                    PromptMessage.session_id == session_id,
                    PromptMessage.turn == turn
                )
                existing_message = await self.db.execute(message_query)
                message = existing_message.scalar_one_or_none()
                
                if not message:
                    logger.error(
                        f"[EvaluationStorage] Foreign Key 제약 조건 위반 - "
                        f"메시지가 존재하지 않습니다. session_id: {session_id}, turn: {turn}. "
                        f"백엔드에서 먼저 메시지를 생성해야 합니다."
                    )
                    return None
                
                # 새 평가 결과 생성
                evaluation = PromptEvaluation(
                    session_id=session_id,
                    turn=turn,
                    evaluation_type=EvaluationTypeEnum.TURN_EVAL,
                    details=details,
                    created_at=datetime.utcnow()
                )
                
                self.db.add(evaluation)
                await self.db.flush()
                
                logger.info(
                    f"[EvaluationStorage] 턴 평가 저장 완료 - "
                    f"session_id: {session_id}, turn: {turn}, score: {score}"
                )
                return evaluation
                
        except Exception as e:
            logger.error(
                f"[EvaluationStorage] 턴 평가 저장 실패 - "
                f"session_id: {session_id}, turn: {turn}, error: {str(e)}",
                exc_info=True
            )
            return None
    
    async def save_holistic_flow_evaluation(
        self,
        session_id: int,
        holistic_flow_score: float,
        holistic_flow_analysis: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Optional[PromptEvaluation]:
        """
        6.a 노드 (eval_holistic_flow) 평가 결과 저장
        
        [저장 데이터]
        - evaluation_type: 'HOLISTIC_FLOW'
        - turn: NULL (세션 전체 평가)
        - details: 모든 평가 데이터 (score, analysis, 추가 상세 정보 등)
        
        Args:
            session_id: 세션 ID (PostgreSQL id)
            holistic_flow_score: 전체 플로우 점수
            holistic_flow_analysis: 전체 플로우 분석 내용
            details: 추가 상세 정보 (선택)
        
        Returns:
            생성된 PromptEvaluation 또는 None (실패 시)
        """
        try:
            # details에 모든 평가 데이터 포함
            evaluation_details = details.copy() if details else {}
            evaluation_details.update({
                "score": holistic_flow_score,  # 점수
                "analysis": holistic_flow_analysis,  # 분석 내용
            })
            
            # 기존 평가 결과 확인 (중복 방지)
            existing = await self._get_existing_evaluation(
                session_id=session_id,
                turn=None,  # holistic 평가는 turn이 NULL
                evaluation_type=EvaluationTypeEnum.HOLISTIC_FLOW
            )
            
            if existing:
                # 기존 평가 결과 업데이트
                existing.details = evaluation_details
                existing.created_at = datetime.utcnow()
                
                await self.db.flush()
                logger.info(
                    f"[EvaluationStorage] 전체 플로우 평가 업데이트 - "
                    f"session_id: {session_id}, score: {holistic_flow_score}"
                )
                return existing
            else:
                # 새 평가 결과 생성 (HOLISTIC_FLOW는 항상 turn=None)
                evaluation = PromptEvaluation(
                    session_id=session_id,
                    turn=None,  # holistic 평가는 turn이 NULL
                    evaluation_type=EvaluationTypeEnum.HOLISTIC_FLOW,
                    details=evaluation_details,
                    created_at=datetime.utcnow()
                )
                
                self.db.add(evaluation)
                await self.db.flush()
                
                logger.info(
                    f"[EvaluationStorage] 전체 플로우 평가 저장 완료 - "
                    f"session_id: {session_id}, score: {holistic_flow_score}"
                )
                return evaluation
                
        except Exception as e:
            logger.error(
                f"[EvaluationStorage] 전체 플로우 평가 저장 실패 - "
                f"session_id: {session_id}, error: {str(e)}",
                exc_info=True
            )
            return None
    
    async def _get_existing_evaluation(
        self,
        session_id: int,
        turn: Optional[int],
        evaluation_type: EvaluationTypeEnum
    ) -> Optional[PromptEvaluation]:
        """
        기존 평가 결과 조회
        
        Args:
            session_id: 세션 ID
            turn: 턴 번호 (None이면 holistic 평가)
            evaluation_type: 평가 유형
        
        Returns:
            기존 PromptEvaluation 또는 None
        """
        from sqlalchemy import select, and_, text
        
        # PostgreSQL ENUM 타입과 비교하기 위해 text()를 사용하여 원시 SQL 작성
        # evaluation_type.value를 사용하여 문자열 값으로 비교
        query = select(PromptEvaluation).where(
            and_(
                PromptEvaluation.session_id == session_id,
                # ENUM 값을 문자열로 변환하여 비교 (PostgreSQL의 ::text 캐스팅 사용)
                text("prompt_evaluations.evaluation_type::text = :eval_type")
            )
        )
        
        # turn이 None이면 holistic 평가 (turn IS NULL)
        if turn is None:
            query = query.where(PromptEvaluation.turn.is_(None))
        else:
            query = query.where(PromptEvaluation.turn == turn)
        
        # 파라미터 바인딩
        result = await self.db.execute(
            query.params(eval_type=evaluation_type.value)
        )
        return result.scalar_one_or_none()
    
    async def save_turn_evaluations_batch(
        self,
        session_id: int,
        turn_logs: Dict[str, Dict[str, Any]]
    ) -> int:
        """
        여러 턴 평가 결과 일괄 저장
        
        Args:
            session_id: 세션 ID
            turn_logs: Redis에서 가져온 모든 turn_logs {turn: turn_log, ...}
        
        Returns:
            저장된 평가 결과 개수
        """
        saved_count = 0
        
        for turn_str, turn_log in turn_logs.items():
            try:
                turn = int(turn_str)
                evaluation = await self.save_turn_evaluation(
                    session_id=session_id,
                    turn=turn,
                    turn_log=turn_log
                )
                if evaluation:
                    saved_count += 1
            except (ValueError, KeyError) as e:
                logger.warning(
                    f"[EvaluationStorage] 턴 평가 저장 건너뜀 - "
                    f"session_id: {session_id}, turn: {turn_str}, error: {str(e)}"
                )
        
        # 일괄 커밋
        try:
            await self.db.commit()
            logger.info(
                f"[EvaluationStorage] 일괄 저장 완료 - "
                f"session_id: {session_id}, saved_count: {saved_count}/{len(turn_logs)}"
            )
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"[EvaluationStorage] 일괄 저장 실패 - "
                f"session_id: {session_id}, error: {str(e)}"
            )
            raise
        
        return saved_count


