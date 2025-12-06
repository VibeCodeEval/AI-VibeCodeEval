-- prompt_evaluations 테이블 안전장치 추가
-- 1. Check Constraint: evaluation_type에 따른 turn NULL 규칙 강제
-- 2. Unique Index: 중복 방지 (턴 평가, 전체 평가 각각)

-- 안전장치 1: Check Constraint
-- "Holistic 평가(holistic_flow, holistic_performance)면 turn은 NULL이어야 함"
-- "Turn 평가(turn_eval)면 turn은 NOT NULL이어야 함"
ALTER TABLE ai_vibe_coding_test.prompt_evaluations
ADD CONSTRAINT check_valid_turn_logic
CHECK (
    -- 경우 1: 전체 평가(Holistic)면 -> turn은 반드시 NULL
    (evaluation_type IN ('holistic_flow', 'holistic_performance') AND turn IS NULL)
    OR
    -- 경우 2: 턴 평가(Turn)면 -> turn은 반드시 NOT NULL
    (evaluation_type = 'turn_eval' AND turn IS NOT NULL)
);

-- 안전장치 2-1: 턴 평가용 유니크 인덱스
-- "같은 세션, 같은 턴에는 평가가 하나만 있어야 한다"
-- (evaluation_type별로도 구분되므로 기존 UNIQUE 제약과 함께 작동)
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_turn_eval 
ON ai_vibe_coding_test.prompt_evaluations (session_id, turn, evaluation_type) 
WHERE turn IS NOT NULL;

-- 안전장치 2-2: 전체 평가용 유니크 인덱스
-- "같은 세션에서 각 Holistic 타입은 딱 한 줄만 존재해야 한다"
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_holistic_flow_eval 
ON ai_vibe_coding_test.prompt_evaluations (session_id) 
WHERE evaluation_type = 'holistic_flow';

CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_holistic_performance_eval 
ON ai_vibe_coding_test.prompt_evaluations (session_id) 
WHERE evaluation_type = 'holistic_performance';


