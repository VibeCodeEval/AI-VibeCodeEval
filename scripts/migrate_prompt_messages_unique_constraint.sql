-- prompt_messages 테이블의 UNIQUE 제약조건 수정
-- (session_id, turn) → (session_id, turn, role)
-- 같은 turn에 USER와 AI 메시지를 모두 저장할 수 있도록 변경

-- 1. 기존 UNIQUE 제약조건 제거
ALTER TABLE ai_vibe_coding_test.prompt_messages
DROP CONSTRAINT IF EXISTS prompt_messages_session_id_turn_key;

-- 2. 새로운 UNIQUE 제약조건 추가 (session_id, turn, role)
ALTER TABLE ai_vibe_coding_test.prompt_messages
ADD CONSTRAINT prompt_messages_session_id_turn_role_key
UNIQUE(session_id, turn, role);

-- 3. 기존 인덱스 확인 (필요시 재생성)
-- 기존 인덱스는 그대로 유지 (성능에 영향 없음)


