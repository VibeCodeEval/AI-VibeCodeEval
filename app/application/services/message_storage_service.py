"""
메시지 저장 서비스
PostgreSQL 먼저 저장 → Redis 체크포인트 업데이트

[목적]
- Spring Boot에서 받은 메시지를 PostgreSQL과 Redis에 저장
- 저장 순서: PostgreSQL → Redis (데이터 무결성 보장)

[플로우]
1. exam_id, participant_id로 세션 조회/생성
2. PostgreSQL에 메시지 저장
3. Redis 체크포인트 업데이트
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.cache.redis_client import RedisClient
from app.infrastructure.persistence.models.enums import PromptRoleEnum
from app.infrastructure.persistence.models.sessions import (PromptMessage,
                                                            PromptSession)
from app.infrastructure.repositories.exam_repository import ExamRepository
from app.infrastructure.repositories.session_repository import \
    SessionRepository
from app.infrastructure.repositories.state_repository import StateRepository

logger = logging.getLogger(__name__)


class MessageStorageService:
    """메시지 저장 서비스"""

    def __init__(self, db: AsyncSession, redis: RedisClient):
        """
        Args:
            db: PostgreSQL 세션
            redis: Redis 클라이언트
        """
        self.db = db
        self.redis = redis
        self.session_repo = SessionRepository(db)
        self.state_repo = StateRepository(redis)

    async def save_message(
        self,
        exam_id: int,
        participant_id: int,
        turn: int,
        role: str,
        content: str,
        token_count: Optional[int] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        메시지 저장 (PostgreSQL 먼저 → Redis 업데이트)

        [저장 순서]
        1. PostgreSQL에 먼저 저장 (데이터 무결성)
        2. 성공하면 Redis 체크포인트 업데이트

        [호출 시점]
        - Spring Boot에서 SaveChatMessageRequest 받을 때
        - 매 메시지마다 호출 (USER, ASSISTANT 모두)

        Args:
            exam_id: 시험 ID
            participant_id: 참가자 ID
            turn: 턴 번호
            role: 역할 ('user' 또는 'assistant')
            content: 메시지 내용
            token_count: 토큰 사용량 (선택)
            meta: 메타데이터 (선택). SAVE(Phase 1 확정) 시 {"code_snapshot": "코드 전체", "is_v1_checkpoint": true} 포함 시
                prompt_messages.meta(JSONB)에 그대로 저장됨. Step 04에서 v1_code 복원에 사용.

        Returns:
            {
                "session_id": int,
                "message_id": int,
                "success": bool
            }

        Raises:
            ValueError: exam_participants가 없거나 spec_id가 없을 때
        """
        try:
            # 1. 세션 조회 또는 생성
            session = await self.session_repo.get_or_create_session(
                exam_id=exam_id, participant_id=participant_id
            )

            logger.info(
                f"[MessageStorage] 세션 확인/생성 완료 - "
                f"session_id: {session.id}, exam_id: {exam_id}, participant_id: {participant_id}"
            )

            # 2. Role 변환 ('user' → USER, 'assistant'/'ai' → AI — DB enum 값)
            role_enum = self._convert_role(role)
            conv_turn = self._api_turn_to_conversation_turn(turn, role_enum)

            # 3. PostgreSQL에 메시지 저장 (먼저)
            merged_meta = dict(meta) if meta else {}
            try:
                redis_state = await self.state_repo.get_state(
                    f"session_{session.id}"
                )
                if redis_state:
                    gr_patch = self._guardrail_meta_patch(
                        redis_state, turn, role_enum, content
                    )
                    if gr_patch:
                        merged_meta.update(gr_patch)
            except Exception as gr_err:
                logger.warning(
                    "[MessageStorage] 가드레일 meta 병합 실패 (저장은 계속) - %s",
                    gr_err,
                )

            message = await self.session_repo.add_message(
                session_id=session.id,
                turn=conv_turn,
                role=role_enum,
                content=content,
                token_count=token_count or 0,
                meta=merged_meta if merged_meta else None,
            )

            # 커밋 (PostgreSQL 저장 완료)
            await self.db.commit()

            logger.info(
                f"[MessageStorage] PostgreSQL 저장 완료 - "
                f"session_id: {session.id}, message_id: {message.id}, turn: {turn}, role: {role}"
            )

            # 4. Redis 체크포인트 업데이트 (PostgreSQL 성공 후)
            try:
                await self._update_redis_checkpoint(
                    session_id=session.id,
                    turn=turn,
                    role=role,
                    content=content,
                    token_count=token_count,
                )
                logger.info(
                    f"[MessageStorage] Redis 체크포인트 업데이트 완료 - "
                    f"session_id: {session.id}, turn: {turn}"
                )
            except Exception as redis_error:
                # Redis 실패해도 PostgreSQL은 저장되었으므로 경고만
                logger.warning(
                    f"[MessageStorage] Redis 업데이트 실패 (PostgreSQL은 저장됨) - "
                    f"session_id: {session.id}, error: {str(redis_error)}"
                )

            return {"session_id": session.id, "message_id": message.id, "success": True}

        except Exception as e:
            # PostgreSQL 실패 시 롤백
            await self.db.rollback()
            logger.error(
                f"[MessageStorage] 메시지 저장 실패 - "
                f"exam_id: {exam_id}, participant_id: {participant_id}, turn: {turn}, error: {str(e)}"
            )
            raise

    def _convert_role(self, role: str) -> PromptRoleEnum:
        """역할 문자열을 PromptRoleEnum으로 변환"""
        role_lower = role.lower()
        if role_lower == "user":
            return PromptRoleEnum.USER
        elif role_lower == "assistant" or role_lower == "ai":
            return PromptRoleEnum.AI
        else:
            # 기본값은 USER
            logger.warning(f"[MessageStorage] 알 수 없는 role: {role}, USER로 처리")
            return PromptRoleEnum.USER

    @staticmethod
    def _api_turn_to_conversation_turn(turn: int, role: PromptRoleEnum) -> int:
        from app.domain.langgraph.utils.guardrail_turns import api_turn_to_conversation_turn

        return api_turn_to_conversation_turn(turn, role)

    def _guardrail_meta_patch(
        self,
        state: Dict[str, Any],
        message_turn: int,
        role: PromptRoleEnum,
        content: str,
    ) -> Optional[Dict[str, Any]]:
        from app.domain.langgraph.utils.guardrail_turns import build_guardrail_meta_patch

        return build_guardrail_meta_patch(state, message_turn, role, content)

    async def sync_guardrail_meta_to_db(
        self, postgres_session_id: int, state: Dict[str, Any]
    ) -> int:
        """
        LangGraph 실행 후 guardrail_flag_turns를 prompt_messages.meta에 백필.
        save-message가 그래프보다 먼저 호출된 경우 V3 검증·export용.
        """
        from app.domain.langgraph.utils.guardrail_turns import (
            get_guardrail_flag_turns,
            get_guardrail_turn_reasons,
        )

        updated = 0
        reasons = get_guardrail_turn_reasons(state)
        for conv_turn in get_guardrail_flag_turns(state):
            patch = {
                "is_guardrail_failed": True,
                "block_reason": reasons.get(str(conv_turn)),
                "conversation_turn": conv_turn,
            }
            for role in (PromptRoleEnum.USER, PromptRoleEnum.AI):
                msg = await self.session_repo.update_message_meta(
                    session_id=postgres_session_id,
                    turn=conv_turn,
                    role=role,
                    meta_update=patch,
                    merge=True,
                )
                if msg:
                    updated += 1
        if updated:
            await self.db.commit()
            logger.info(
                "[MessageStorage] 가드레일 meta DB 백필 - session_id=%s, rows=%s",
                postgres_session_id,
                updated,
            )
        return updated

    async def _update_redis_checkpoint(
        self,
        session_id: int,
        turn: int,
        role: str,
        content: str,
        token_count: Optional[int] = None,
    ):
        """
        Redis 체크포인트 업데이트

        [업데이트 내용]
        - LangGraph State에 메시지 추가
        - turn_logs 업데이트 (선택적)
        """
        # Redis session_id는 문자열 형식 (예: "session_123")
        redis_session_id = f"session_{session_id}"

        # 기존 상태 로드
        state = await self.state_repo.get_state(redis_session_id)

        if not state:
            # 상태가 없으면 초기 상태 생성
            state = {
                "session_id": redis_session_id,
                "messages": [],
                "turn": 0,
            }

        # 메시지 추가 (LangChain 형식으로 변환 필요)
        # 현재는 간단히 메시지 리스트에 추가
        if "messages" not in state:
            state["messages"] = []

        role_enum = self._convert_role(role)
        conv_turn = self._api_turn_to_conversation_turn(turn, role_enum)
        storage_turn = turn  # Spring turnId(DB slot) 보존

        # LangGraph/N4는 conversation turn 기준
        message_data = {
            "role": role,
            "content": content,
            "turn": conv_turn,
            "storage_turn": storage_turn,
        }
        if token_count:
            message_data["token_count"] = token_count

        gr_meta = self._guardrail_meta_patch(state, turn, role_enum, content)
        if gr_meta:
            message_data["guardrail"] = gr_meta

        state["messages"].append(message_data)
        state["turn"] = max(state.get("turn", 0), conv_turn)
        state["current_turn"] = max(state.get("current_turn", 0), conv_turn)

        # 상태 저장
        await self.state_repo.save_state(redis_session_id, state)

    async def save_messages_batch(
        self, exam_id: int, participant_id: int, messages: list[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        여러 메시지 일괄 저장

        Args:
            exam_id: 시험 ID
            participant_id: 참가자 ID
            messages: 메시지 리스트 [{"turn": 1, "role": "user", "content": "...", ...}, ...]

        Returns:
            {
                "session_id": int,
                "saved_count": int,
                "success": bool
            }
        """
        try:
            # 세션 조회 또는 생성
            session = await self.session_repo.get_or_create_session(
                exam_id=exam_id, participant_id=participant_id
            )

            saved_count = 0

            redis_state = await self.state_repo.get_state(f"session_{session.id}")

            for msg in messages:
                role_enum = self._convert_role(msg.get("role", "user"))
                raw_turn = msg.get("turn", 1)
                conv_turn = self._api_turn_to_conversation_turn(raw_turn, role_enum)
                merged_meta = dict(msg.get("meta") or {})
                if redis_state:
                    gr_patch = self._guardrail_meta_patch(
                        redis_state,
                        raw_turn,
                        role_enum,
                        msg.get("content", ""),
                    )
                    if gr_patch:
                        merged_meta.update(gr_patch)

                message = await self.session_repo.add_message(
                    session_id=session.id,
                    turn=conv_turn,
                    role=role_enum,
                    content=msg.get("content", ""),
                    token_count=msg.get("token_count", 0),
                    meta=merged_meta if merged_meta else None,
                )
                saved_count += 1

            # 일괄 커밋
            await self.db.commit()

            logger.info(
                f"[MessageStorage] 일괄 저장 완료 - "
                f"session_id: {session.id}, saved_count: {saved_count}"
            )

            return {
                "session_id": session.id,
                "saved_count": saved_count,
                "success": True,
            }

        except Exception as e:
            await self.db.rollback()
            logger.error(f"[MessageStorage] 일괄 저장 실패: {str(e)}")
            raise
