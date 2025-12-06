"""
프롬프트 세션 Repository
PostgreSQL에서 세션 정보를 조회하고 관리

[목적]
- 사용자의 코딩 테스트 세션 정보를 PostgreSQL에 영구 저장
- 대화 메시지 기록을 턴별로 관리
- Redis의 임시 상태와 달리, 세션 기록을 장기 보관
- 향후 분석 및 감사를 위한 데이터 제공

[Redis와의 관계]
- Redis: 실시간 세션 상태 (`graph_state:{session_id}`, `turn_logs:{session_id}:{turn}`)
  * 임시 저장, TTL 24시간
  * LangGraph 실행 중 사용
  * 평가 결과 포함 (intent, rubrics, reasoning)
  
- PostgreSQL: 영구 세션 기록 (`prompt_sessions`, `prompt_messages`)
  * 장기 보관, 영구 저장
  * 순수 메시지 내용 + 메타데이터
  * 분석 및 감사 목적

[데이터 흐름]
1. 세션 시작: create_session() → PostgreSQL 레코드 생성
2. 대화 진행: Redis에서 실시간 처리
3. 각 턴 완료: add_message() → PostgreSQL 저장 (선택)
4. 제출 완료: end_session() → PostgreSQL 업데이트

[주요 기능]
- 세션 생성/조회/종료
- 메시지 추가/조회
- 토큰 사용량 추적
- 대화 히스토리 조회
"""
from typing import Optional, List
from datetime import datetime

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infrastructure.persistence.models.sessions import PromptSession, PromptMessage
from app.infrastructure.persistence.models.enums import PromptRoleEnum
from app.infrastructure.repositories.exam_repository import ExamRepository


class SessionRepository:
    """
    프롬프트 세션 데이터 접근 계층
    
    [역할]
    - PromptSession 테이블 CRUD
    - PromptMessage 테이블 CRUD
    - 세션과 메시지의 관계 관리
    
    [사용처]
    - API 라우터 (chat.py, session.py)
    - 향후 분석 도구 및 대시보드
    """
    
    def __init__(self, db: AsyncSession):
        """
        Args:
            db: SQLAlchemy 비동기 세션 (FastAPI Depends에서 주입)
        """
        self.db = db
    
    async def create_session(
        self,
        exam_id: int,
        participant_id: int,
        spec_id: Optional[int] = None
    ) -> PromptSession:
        """
        새 프롬프트 세션 생성
        
        [호출 시점]
        - 사용자가 채팅을 최초 시작할 때
        - API: POST /api/chat/start 또는 첫 send_message 호출 시
        
        [생성 후 처리]
        1. PostgreSQL에 세션 레코드 저장
        2. Redis에 초기 graph_state 생성 (별도 처리)
        3. session_id를 클라이언트에 반환
        
        [참고]
        - started_at: 현재 시각 (UTC)
        - ended_at: NULL (진행 중)
        - total_tokens: 0 (초기값)
        
        Args:
            exam_id: 시험 ID
            participant_id: 참가자 ID
            spec_id: 문제 스펙 ID (선택)
        
        Returns:
            생성된 PromptSession (id 포함)
        """
        session = PromptSession(
            exam_id=exam_id,
            participant_id=participant_id,
            spec_id=spec_id,
            started_at=datetime.utcnow(),
            total_tokens=0
        )
        self.db.add(session)
        await self.db.flush()  # ID 생성을 위해 flush
        return session
    
    async def get_session_by_id(
        self, 
        session_id: int,
        include_messages: bool = False
    ) -> Optional[PromptSession]:
        """
        세션 ID로 조회
        
        [사용처]
        - API에서 세션 정보 조회
        - 세션 존재 여부 확인
        - 세션 업데이트 전 조회
        
        Args:
            session_id: 세션 ID (BigInteger)
            include_messages: 메시지 목록 포함 여부 (True면 JOIN 실행)
        
        Returns:
            PromptSession 또는 None
        """
        query = select(PromptSession).where(PromptSession.id == session_id)
        
        if include_messages:
            query = query.options(selectinload(PromptSession.messages))
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_or_create_session(
        self,
        exam_id: int,
        participant_id: int
    ) -> PromptSession:
        """
        세션 조회 또는 생성 (exam_id, participant_id 기반)
        
        [플로우]
        1. exam_participants 조회 → spec_id 확인
        2. 진행 중인 세션 조회 (ended_at IS NULL)
        3. 없으면 새 세션 생성
        
        [호출 시점]
        - Spring Boot에서 메시지 요청 시 (exam_id, participant_id 전달)
        - 첫 메시지: 세션 생성
        - 이후 메시지: 기존 세션 사용
        
        Args:
            exam_id: 시험 ID
            participant_id: 참가자 ID
        
        Returns:
            PromptSession (기존 또는 새로 생성된 세션)
        
        Raises:
            ValueError: exam_participants가 존재하지 않거나 spec_id가 없을 때
        """
        # 1. exam_participants 조회 (spec_id 확인)
        exam_repo = ExamRepository(self.db)
        exam_participant = await exam_repo.get_exam_participant(exam_id, participant_id)
        
        if not exam_participant:
            raise ValueError(
                f"시험 참가자 정보 없음: exam_id={exam_id}, participant_id={participant_id}"
            )
        
        if not exam_participant.spec_id:
            raise ValueError(
                f"시험 참가자의 spec_id가 없음: exam_id={exam_id}, participant_id={participant_id}"
            )
        
        spec_id = exam_participant.spec_id
        
        # 2. 진행 중인 세션 조회 (ended_at이 NULL인 세션)
        query = select(PromptSession).where(
            and_(
                PromptSession.exam_id == exam_id,
                PromptSession.participant_id == participant_id,
                PromptSession.ended_at.is_(None)  # 종료되지 않은 세션
            )
        )
        result = await self.db.execute(query)
        existing_session = result.scalar_one_or_none()
        
        if existing_session:
            return existing_session  # 기존 세션 반환
        
        # 3. 세션 없으면 새로 생성
        new_session = PromptSession(
            exam_id=exam_id,
            participant_id=participant_id,
            spec_id=spec_id,
            started_at=datetime.utcnow(),
            total_tokens=0
        )
        self.db.add(new_session)
        await self.db.flush()  # ID 생성을 위해 flush
        await self.db.refresh(new_session)  # 생성된 객체 새로고침
        
        return new_session
    
    async def get_active_session(
        self,
        exam_id: int,
        participant_id: int
    ) -> Optional[PromptSession]:
        """
        활성 세션 조회 (ended_at이 None인 세션)
        
        [정의]
        - ended_at이 NULL인 세션 = 아직 종료되지 않은 세션
        - 한 참가자가 동시에 여러 세션을 가질 수 없다고 가정
        
        [사용처]
        - 참가자가 재접속 시 이전 세션 확인
        - 세션 중복 생성 방지
        - 세션 복구 (브라우저 새로고침 등)
        
        [반환값]
        - 진행 중인 세션이 있으면 해당 세션 (메시지 포함)
        - 없으면 None (새 세션 생성 필요)
        
        Args:
            exam_id: 시험 ID
            participant_id: 참가자 ID
        
        Returns:
            활성 PromptSession 또는 None
        """
        query = select(PromptSession).where(
            and_(
                PromptSession.exam_id == exam_id,
                PromptSession.participant_id == participant_id,
                PromptSession.ended_at.is_(None)
            )
        ).options(selectinload(PromptSession.messages))
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_session_messages(
        self,
        session_id: int,
        limit: Optional[int] = None
    ) -> List[PromptMessage]:
        """
        세션의 메시지 목록 조회
        
        [정렬]
        - turn 오름차순 (1 → 2 → 3...)
        - 동일 turn 내에서는 id 오름차순 (USER → ASSISTANT)
        
        [사용처]
        - 세션 기록 조회 API
        - 대화 히스토리 표시
        - 분석 및 감사
        
        Args:
            session_id: 세션 ID
            limit: 최대 조회 개수 (선택, None이면 전체)
        
        Returns:
            PromptMessage 리스트 (턴 순서대로)
        """
        query = select(PromptMessage).where(
            PromptMessage.session_id == session_id
        ).order_by(PromptMessage.turn.asc())
        
        if limit:
            query = query.limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_sessions_by_exam_participant(
        self,
        exam_id: int,
        participant_id: int
    ) -> List[PromptSession]:
        """
        참가자의 모든 세션 조회 (exam_id, participant_id 기반)
        
        [사용처]
        - 백엔드에서 참가자의 모든 세션 조회
        - 세션 히스토리 확인
        
        Args:
            exam_id: 시험 ID
            participant_id: 참가자 ID
        
        Returns:
            PromptSession 리스트 (시간순 정렬)
        """
        query = select(PromptSession).where(
            and_(
                PromptSession.exam_id == exam_id,
                PromptSession.participant_id == participant_id
            )
        ).order_by(PromptSession.started_at.desc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_last_n_messages(
        self,
        session_id: int,
        n: int = 10
    ) -> List[PromptMessage]:
        """
        세션의 마지막 N개 메시지 조회
        
        [동작]
        1. turn 내림차순으로 N개 조회 (최근 턴부터)
        2. 결과를 reverse하여 시간순으로 정렬
        
        [사용처]
        - LangChain context window 관리
        - 최근 대화만 LLM에 전달 (토큰 절약)
        - 실시간 채팅 UI (최근 메시지만 표시)
        
        [예시]
        - n=10: 최근 10개 메시지 (약 5턴)
        - 반환: [Turn 1 USER, Turn 1 AI, Turn 2 USER, ...]
        
        Args:
            session_id: 세션 ID
            n: 조회할 메시지 개수 (기본 10개)
        
        Returns:
            최근 N개 메시지 리스트 (시간순)
        """
        query = select(PromptMessage).where(
            PromptMessage.session_id == session_id
        ).order_by(PromptMessage.turn.desc()).limit(n)
        
        result = await self.db.execute(query)
        messages = list(result.scalars().all())
        return list(reversed(messages))  # 시간순으로 다시 정렬
    
    async def add_message(
        self,
        session_id: int,
        turn: Optional[int],
        role: PromptRoleEnum,
        content: str,
        token_count: int = 0,
        meta: Optional[dict] = None
    ) -> PromptMessage:
        """
        메시지 추가 (단일)
        
        [Atomic Increment 방식]
        - turn=None일 경우: DB에서 자동으로 MAX(turn) + 1 계산하여 저장
        - turn이 지정된 경우: 지정된 turn 번호로 저장
        
        ⚠️ **중요**: turn=None은 파라미터 의미일 뿐, DB에는 항상 정수값이 저장됩니다.
        - DB 스키마: `turn INTEGER NOT NULL` (NULL 불가능)
        - SQL 서브쿼리: `COALESCE(MAX(turn), 0) + 1` → 항상 정수 반환 (최소 1)
        - 따라서 실제 저장되는 turn 값은 절대 NULL이 아닙니다.
        
        [동시성 안전]
        - DB 레벨에서 원자적(Atomic) 처리로 동시성 문제 방지
        - 서브쿼리를 사용하여 MAX(turn) + 1을 계산
        - UNIQUE 제약조건과 함께 사용하여 중복 방지
        
        [호출 시점]
        1. Handle Request에서 사용자 메시지 처리 후: role=USER, turn=None
        2. Writer LLM 응답 생성 후: role=AI, turn=None
        3. SYSTEM 프롬프트 기록 시: role=SYSTEM, turn=None (선택)
        
        [turn과 role 관계]
        - Turn 1: USER (사용자 질문)
        - Turn 2: AI (AI 답변)
        - Turn 3: USER
        - Turn 4: AI
        - 순차적으로 저장 (같은 turn에 USER/AI 페어 저장 불가)
        
        [meta 필드 활용]
        meta 필드(JSONB)에 추가 정보 저장 가능:
        - meta.intent_type: 의도 분류 결과 (CodeIntentType)
        - meta.is_guardrail_failed: 가드레일 위반 여부
        - meta.llm_model: 사용한 LLM 모델명
        - meta.timestamp: 생성 시각 (ISO 8601)
        
        Args:
            session_id: 세션 ID
            turn: 턴 번호 
                - None: DB에서 자동 계산 (MAX(turn) + 1, 최소 1)
                - int: 지정된 번호로 저장
                - ⚠️ 실제 DB 저장값은 항상 정수 (NULL 불가능)
            role: 메시지 역할 (USER/AI)
            content: 메시지 내용
            token_count: 토큰 수 (LLM 응답 시 필수)
            meta: 메타데이터 (JSON, 선택)
        
        Returns:
            생성된 PromptMessage (id, turn 포함, turn은 항상 정수)
        """
        from sqlalchemy import text, func
        
        if turn is None:
            # Atomic Increment: DB에서 자동으로 다음 turn 번호 계산
            # 서브쿼리를 사용하여 동시성 안전 보장
            # meta를 JSON 문자열로 변환
            import json
            meta_json = json.dumps(meta) if meta else None
            
            # SQLAlchemy의 text()는 named parameter를 지원하며,
            # asyncpg 드라이버가 이를 자동으로 positional parameter로 변환합니다.
            insert_query = text("""
                INSERT INTO ai_vibe_coding_test.prompt_messages 
                (session_id, turn, role, content, token_count, meta, created_at)
                VALUES (
                    :session_id,
                    (SELECT COALESCE(MAX(turn), 0) + 1 
                     FROM ai_vibe_coding_test.prompt_messages 
                     WHERE session_id = :session_id),
                    CAST(:role AS ai_vibe_coding_test.prompt_role_enum),
                    :content,
                    :token_count,
                    CAST(:meta AS jsonb),
                    NOW()
                )
                RETURNING id, turn, session_id, role, content, token_count, meta, created_at
            """)
            
            result = await self.db.execute(
                insert_query,
                {
                    "session_id": session_id,
                    "role": role.value,  # Enum 값을 문자열로 변환
                    "content": content,
                    "token_count": token_count,
                    "meta": meta_json
                }
            )
            row = result.fetchone()
            
            # 반환된 행을 PromptMessage 객체로 변환
            message = PromptMessage(
                id=row.id,
                session_id=row.session_id,
                turn=row.turn,
                role=role,
                content=row.content,
                token_count=row.token_count,
                meta=json.loads(row.meta) if row.meta else None,
                created_at=row.created_at
            )
            # 이미 DB에 저장된 객체이므로 merge를 사용하여 세션에 등록
            # (이후 조회 시 사용 가능하도록)
            message = await self.db.merge(message)
            await self.db.flush()
            return message
        else:
            # turn이 지정된 경우: 기존 방식 사용
            message = PromptMessage(
                session_id=session_id,
                turn=turn,
                role=role,
                content=content,
                token_count=token_count,
                meta=meta,
                created_at=datetime.utcnow()
            )
            self.db.add(message)
            await self.db.flush()
            return message
    
    async def get_next_turn_number(self, session_id: int) -> int:
        """
        다음 턴 번호 계산
        
        ⚠️ **DEPRECATED**: 이 메서드는 더 이상 사용하지 않습니다.
        대신 `add_message(turn=None)`을 사용하여 DB에서 자동으로 turn 번호를 계산하세요.
        
        [Atomic Increment 방식으로 변경됨]
        - `add_message(turn=None)`을 호출하면 DB에서 자동으로 MAX(turn) + 1 계산
        - 동시성 안전 보장 (DB 레벨에서 원자적 처리)
        - UPDATE 없이 INSERT만 사용
        
        [계산 방법]
        1. DB에서 해당 세션의 최대 turn 번호 조회
        2. 없으면 1 (첫 턴)
        3. 있으면 MAX(turn) + 1
        
        [사용처]
        - ⚠️ 레거시 코드 및 테스트 스크립트에서만 사용
        - 새로운 코드에서는 `add_message(turn=None)` 사용 권장
        
        Args:
            session_id: 세션 ID
            
        Returns:
            다음 턴 번호 (1부터 시작)
        """
        import warnings
        warnings.warn(
            "get_next_turn_number() is deprecated. Use add_message(turn=None) instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        from sqlalchemy import func
        
        # 해당 세션의 최대 turn 번호 조회
        query = select(func.max(PromptMessage.turn)).where(
            PromptMessage.session_id == session_id
        )
        result = await self.db.execute(query)
        max_turn = result.scalar_one_or_none()
        
        # 최대 turn이 없으면 첫 턴 (1)
        if max_turn is None:
            return 1
        
        # 최대 turn이 있으면 다음 턴 (max_turn + 1)
        return max_turn + 1
    
    async def save_messages_batch(
        self,
        messages: List[dict]
    ) -> List[PromptMessage]:
        """
        메시지 일괄 저장 (성능 최적화)
        
        [목적]
        - 제출 시 모든 턴의 메시지를 한 번에 저장
        - 여러 add_message() 호출보다 효율적
        
        [사용처]
        - submit_code() 시 Redis의 모든 메시지를 PostgreSQL로 이관
        - 대량 데이터 마이그레이션
        
        [성능]
        - bulk insert 패턴 사용
        - 여러 메시지를 한 트랜잭션에서 처리
        - N개 메시지 → 1번의 flush
        
        [예시]
        ```python
        messages = [
            {
                "session_id": 123,
                "turn": 1,
                "role": PromptRoleEnum.USER,
                "content": "...",
                "token_count": 50,
                "meta": {...}
            },
            {
                "session_id": 123,
                "turn": 1,
                "role": PromptRoleEnum.AI,  # DB ENUM 정의에 맞춰 'AI' 사용
                "content": "...",
                "token_count": 120
            }
        ]
        await repo.save_messages_batch(messages)
        ```
        
        Args:
            messages: 메시지 dict 리스트
                각 dict는 session_id, turn, role, content를 포함
                token_count, meta는 선택
        
        Returns:
            생성된 PromptMessage 리스트
        """
        message_objects = []
        for msg_data in messages:
            message = PromptMessage(
                session_id=msg_data["session_id"],
                turn=msg_data["turn"],
                role=msg_data["role"],
                content=msg_data["content"],
                token_count=msg_data.get("token_count", 0),
                meta=msg_data.get("meta"),
                created_at=datetime.utcnow()
            )
            message_objects.append(message)
            self.db.add(message)
        
        await self.db.flush()
        return message_objects
    
    async def update_session_tokens(
        self,
        session_id: int,
        additional_tokens: int
    ) -> None:
        """
        세션 토큰 사용량 업데이트
        
        [호출 시점]
        - LLM API 호출 후 (Intent Analyzer, Writer, Evaluators)
        - 각 노드에서 토큰 사용 시 누적
        
        [동작]
        - 기존 total_tokens에 additional_tokens 더하기
        - 누적 방식 (덮어쓰기 아님)
        
        [참고]
        - total_tokens는 prompt_messages의 token_count 합계와 일치해야 함
        - 검증: get_total_tokens_by_session()으로 확인 가능
        
        [현재 상태]
        - ⏳ 아직 API에서 호출 안 함
        - 향후 LLM 호출 시 토큰 수 추적 필요
        
        Args:
            session_id: 세션 ID
            additional_tokens: 추가 토큰 수 (양수)
        """
        session = await self.get_session_by_id(session_id)
        if session:
            session.total_tokens += additional_tokens
            await self.db.flush()
    
    async def end_session(
        self,
        session_id: int
    ) -> None:
        """
        세션 종료 처리
        
        [호출 시점]
        - 사용자가 코드 제출 완료 (submit_code)
        - 세션 타임아웃 발생
        - 사용자가 명시적으로 세션 종료
        
        [동작]
        - ended_at을 현재 시각(UTC)으로 설정
        - total_tokens는 별도로 업데이트 (update_session_tokens)
        
        [참고]
        - ended_at이 NULL → 진행 중인 세션
        - ended_at이 있음 → 종료된 세션
        - 종료된 세션은 get_active_session()에서 조회 안 됨
        
        [현재 상태]
        - ⏳ 아직 API에서 호출 안 함
        - 향후 submit_code()에서 호출 예정
        
        Args:
            session_id: 세션 ID
        """
        session = await self.get_session_by_id(session_id)
        if session:
            session.ended_at = datetime.utcnow()
            await self.db.flush()
    
    async def get_conversation_history(
        self,
        session_id: int
    ) -> List[dict]:
        """
        대화 히스토리를 LangChain 형식으로 반환
        
        [목적]
        - PostgreSQL 메시지를 LangChain 호환 형식으로 변환
        - LLM API 호출 시 context로 전달
        
        [반환 형식]
        [
            {
                "role": "user",
                "content": "두 수의 합을 구하는 함수를 만들어줘",
                "turn": 1,
                "token_count": 15
            },
            {
                "role": "assistant",
                "content": "좋습니다. 먼저...",
                "turn": 1,
                "token_count": 120
            },
            ...
        ]
        
        [사용처]
        - API 응답 (GET /api/session/{session_id}/history)
        - LangChain context window 구성
        - 세션 복구 시 이전 대화 로드
        
        Args:
            session_id: 세션 ID
        
        Returns:
            대화 히스토리 dict 리스트 (턴 순서대로)
        """
        messages = await self.get_session_messages(session_id)
        return [
            {
                "role": msg.role.value,
                "content": msg.content,
                "turn": msg.turn,
                "token_count": msg.token_count
            }
            for msg in messages
        ]



