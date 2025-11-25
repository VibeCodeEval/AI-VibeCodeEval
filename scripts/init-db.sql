-- AI Vibe Coding Test 데이터베이스 초기화 스크립트
-- Spring Boot에서 관리하는 테이블이지만, 로컬 테스트용으로 제공

-- 스키마 생성
CREATE SCHEMA IF NOT EXISTS ai_vibe_coding_test;

-- Enum 타입 생성
DO $$ BEGIN
    CREATE TYPE ai_vibe_coding_test.difficulty_enum AS ENUM ('easy', 'medium', 'hard');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE ai_vibe_coding_test.problem_status_enum AS ENUM ('draft', 'published', 'archived');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE ai_vibe_coding_test.exam_state_enum AS ENUM ('draft', 'scheduled', 'running', 'paused', 'ended');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE ai_vibe_coding_test.exam_participant_state_enum AS ENUM ('registered', 'waiting', 'in_progress', 'submitted', 'timeout', 'disqualified');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE ai_vibe_coding_test.submission_status_enum AS ENUM ('pending', 'evaluating', 'completed', 'error');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE ai_vibe_coding_test.prompt_role_enum AS ENUM ('system', 'user', 'assistant');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE ai_vibe_coding_test.test_run_grp_enum AS ENUM ('sample', 'hidden');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE ai_vibe_coding_test.verdict_enum AS ENUM ('pending', 'accepted', 'wrong_answer', 'time_limit_exceeded', 'memory_limit_exceeded', 'runtime_error', 'compilation_error', 'internal_error');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 참가자 테이블
CREATE TABLE IF NOT EXISTS participants (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(30),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 문제 세트 테이블
CREATE TABLE IF NOT EXISTS problem_sets (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    created_by BIGINT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 문제 테이블
CREATE TABLE IF NOT EXISTS problems (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(256) NOT NULL,
    difficulty ai_vibe_coding_test.difficulty_enum NOT NULL,
    tags JSONB,
    status ai_vibe_coding_test.problem_status_enum NOT NULL DEFAULT 'draft',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    current_spec_id BIGINT
);

-- 문제 스펙 테이블
CREATE TABLE IF NOT EXISTS problem_specs (
    id BIGSERIAL PRIMARY KEY,
    problem_id BIGINT NOT NULL REFERENCES problems(id),
    version INTEGER NOT NULL DEFAULT 1,
    content_md TEXT,
    checker_json JSONB,
    rubric_json JSONB,
    changelog_md TEXT,
    published_at TIMESTAMP WITH TIME ZONE
);

-- 문제 세트 항목 테이블
CREATE TABLE IF NOT EXISTS problem_set_items (
    id BIGSERIAL PRIMARY KEY,
    problem_set_id BIGINT NOT NULL REFERENCES problem_sets(id),
    problem_id BIGINT NOT NULL REFERENCES problems(id),
    weight INTEGER NOT NULL DEFAULT 1
);

-- 시험 테이블
CREATE TABLE IF NOT EXISTS exams (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    state ai_vibe_coding_test.exam_state_enum NOT NULL DEFAULT 'draft',
    problem_set_id BIGINT REFERENCES problem_sets(id),
    starts_at TIMESTAMP WITH TIME ZONE,
    ends_at TIMESTAMP WITH TIME ZONE,
    version INTEGER NOT NULL DEFAULT 1,
    created_by BIGINT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 시험 참가자 테이블
CREATE TABLE IF NOT EXISTS exam_participants (
    id BIGSERIAL PRIMARY KEY,
    exam_id BIGINT NOT NULL REFERENCES exams(id),
    participant_id BIGINT NOT NULL REFERENCES participants(id),
    state ai_vibe_coding_test.exam_participant_state_enum NOT NULL DEFAULT 'registered',
    token_limit INTEGER,
    token_used INTEGER NOT NULL DEFAULT 0,
    spec_id BIGINT REFERENCES problem_specs(id),
    joined_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(exam_id, participant_id)
);

-- 프롬프트 세션 테이블
CREATE TABLE IF NOT EXISTS prompt_sessions (
    id BIGSERIAL PRIMARY KEY,
    exam_id BIGINT NOT NULL REFERENCES exams(id),
    participant_id BIGINT NOT NULL REFERENCES participants(id),
    spec_id BIGINT REFERENCES problem_specs(id),
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP WITH TIME ZONE,
    total_tokens INTEGER NOT NULL DEFAULT 0
);

-- 프롬프트 메시지 테이블
CREATE TABLE IF NOT EXISTS prompt_messages (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES prompt_sessions(id),
    turn INTEGER NOT NULL,
    role ai_vibe_coding_test.prompt_role_enum NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER NOT NULL DEFAULT 0,
    meta JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 제출 테이블
CREATE TABLE IF NOT EXISTS submissions (
    id BIGSERIAL PRIMARY KEY,
    exam_id BIGINT NOT NULL REFERENCES exams(id),
    participant_id BIGINT NOT NULL REFERENCES participants(id),
    spec_id BIGINT NOT NULL REFERENCES problem_specs(id),
    lang VARCHAR(40) NOT NULL,
    status ai_vibe_coding_test.submission_status_enum NOT NULL DEFAULT 'pending',
    code_inline TEXT,
    code_sha256 CHAR(64),
    code_bytes INTEGER,
    code_loc INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 제출 실행 테이블
CREATE TABLE IF NOT EXISTS submission_runs (
    id BIGSERIAL PRIMARY KEY,
    submission_id BIGINT NOT NULL REFERENCES submissions(id),
    case_index INTEGER NOT NULL,
    grp ai_vibe_coding_test.test_run_grp_enum NOT NULL,
    verdict ai_vibe_coding_test.verdict_enum NOT NULL DEFAULT 'pending',
    time_ms INTEGER,
    mem_kb INTEGER,
    stdout_bytes INTEGER,
    stderr_bytes INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 점수 테이블
CREATE TABLE IF NOT EXISTS scores (
    id BIGSERIAL PRIMARY KEY,
    submission_id BIGINT NOT NULL UNIQUE REFERENCES submissions(id),
    prompt_score NUMERIC(5,2),
    perf_score NUMERIC(5,2),
    correctness_score NUMERIC(5,2),
    total_score NUMERIC(5,2),
    rubric_json JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_prompt_sessions_exam_participant ON prompt_sessions(exam_id, participant_id);
CREATE INDEX IF NOT EXISTS idx_prompt_messages_session_turn ON prompt_messages(session_id, turn);
CREATE INDEX IF NOT EXISTS idx_submissions_exam_participant ON submissions(exam_id, participant_id);

-- 외래 키 추가 (problems.current_spec_id)
ALTER TABLE problems 
    ADD CONSTRAINT fk_problems_current_spec 
    FOREIGN KEY (current_spec_id) REFERENCES problem_specs(id);

COMMENT ON TABLE participants IS '참가자 정보';
COMMENT ON TABLE problems IS '문제 정보';
COMMENT ON TABLE exams IS '시험 정보';
COMMENT ON TABLE prompt_sessions IS 'AI 대화 세션';
COMMENT ON TABLE submissions IS '코드 제출';
COMMENT ON TABLE scores IS '평가 점수';

