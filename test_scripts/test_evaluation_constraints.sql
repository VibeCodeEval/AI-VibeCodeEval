-- prompt_evaluations 안전장치 테스트

-- 테스트용 세션 생성 (실제로는 exam_participants가 필요하지만 테스트용)
-- 실제 테스트는 exam_participants가 있어야 하므로 주석 처리

-- 1. 정상 케이스: Turn 평가 (turn NOT NULL)
-- INSERT INTO ai_vibe_coding_test.prompt_evaluations (session_id, turn, evaluation_type, score)
-- VALUES (1, 1, 'turn_eval', 85.5);
-- ✅ 성공해야 함

-- 2. 정상 케이스: Holistic 평가 (turn NULL)
-- INSERT INTO ai_vibe_coding_test.prompt_evaluations (session_id, turn, evaluation_type, score)
-- VALUES (1, NULL, 'holistic_flow', 90.0);
-- ✅ 성공해야 함

-- 3. 오류 케이스: Turn 평가인데 turn이 NULL
-- INSERT INTO ai_vibe_coding_test.prompt_evaluations (session_id, turn, evaluation_type, score)
-- VALUES (1, NULL, 'turn_eval', 85.5);
-- ❌ CHECK 제약 조건 위반 에러 발생해야 함

-- 4. 오류 케이스: Holistic 평가인데 turn이 NOT NULL
-- INSERT INTO ai_vibe_coding_test.prompt_evaluations (session_id, turn, evaluation_type, score)
-- VALUES (1, 1, 'holistic_flow', 90.0);
-- ❌ CHECK 제약 조건 위반 에러 발생해야 함

-- 5. 오류 케이스: Holistic 평가 중복
-- INSERT INTO ai_vibe_coding_test.prompt_evaluations (session_id, turn, evaluation_type, score)
-- VALUES (1, NULL, 'holistic_flow', 90.0);
-- INSERT INTO ai_vibe_coding_test.prompt_evaluations (session_id, turn, evaluation_type, score)
-- VALUES (1, NULL, 'holistic_flow', 95.0);
-- ❌ Unique Index 위반 에러 발생해야 함

SELECT '안전장치 테스트 스크립트 준비 완료' AS status;


