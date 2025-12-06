-- prompt_evaluations 테이블 수정 마이그레이션
-- turn을 NULL 허용으로 변경하고 prompt_messages와 Foreign Key 추가

-- 1. 기존 테이블이 있다면 제약 조건 제거
ALTER TABLE ai_vibe_coding_test.prompt_evaluations 
DROP CONSTRAINT IF EXISTS prompt_evaluations_session_id_turn_evaluation_type_key;

-- 2. turn 컬럼을 NULL 허용으로 변경
ALTER TABLE ai_vibe_coding_test.prompt_evaluations
ALTER COLUMN turn DROP NOT NULL;

-- 3. prompt_messages와의 Foreign Key 추가 (turn이 NULL이 아닌 경우만)
-- 주의: turn이 NULL인 경우는 Foreign Key 제약이 적용되지 않음
ALTER TABLE ai_vibe_coding_test.prompt_evaluations
ADD CONSTRAINT fk_evaluation_message
FOREIGN KEY (session_id, turn) 
REFERENCES ai_vibe_coding_test.prompt_messages(session_id, turn)
ON DELETE CASCADE;

-- 4. UNIQUE 제약 조건 재생성 (turn이 NULL일 수 있으므로)
ALTER TABLE ai_vibe_coding_test.prompt_evaluations
ADD CONSTRAINT prompt_evaluations_session_turn_type_unique
UNIQUE(session_id, turn, evaluation_type);

-- 5. 인덱스 확인 (이미 있으면 무시)
CREATE INDEX IF NOT EXISTS idx_prompt_evaluations_session 
ON ai_vibe_coding_test.prompt_evaluations(session_id, turn);


