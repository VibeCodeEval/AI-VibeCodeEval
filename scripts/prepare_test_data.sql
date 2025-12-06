-- 테스트 데이터 준비 스크립트
SET search_path TO ai_vibe_coding_test;

-- 참조 테이블 생성 (없으면)
INSERT INTO exams (id, title, state, version) 
VALUES (1, '테스트 시험', 'WAITING', 1) 
ON CONFLICT (id) DO NOTHING;

INSERT INTO participants (id, name) 
VALUES (1, '테스트 참가자') 
ON CONFLICT (id) DO NOTHING;

INSERT INTO problems (id, title, difficulty, status) 
VALUES (1, '테스트 문제', 'MEDIUM', 'PUBLISHED') 
ON CONFLICT (id) DO NOTHING;

INSERT INTO problem_specs (spec_id, problem_id, version, content_md) 
VALUES (10, 1, 1, '테스트 스펙') 
ON CONFLICT (spec_id) DO NOTHING;

-- exam_participants 삽입 (중요!)
INSERT INTO exam_participants (exam_id, participant_id, spec_id, state, token_limit, token_used) 
VALUES (1, 1, 10, 'REGISTERED', 20000, 0) 
ON CONFLICT (exam_id, participant_id) DO NOTHING;

-- 확인
SELECT '테스트 데이터 확인' as info;
SELECT * FROM exam_participants WHERE exam_id = 1 AND participant_id = 1;


