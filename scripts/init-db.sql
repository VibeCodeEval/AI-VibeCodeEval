-- AI Vibe Coding Test - 초기 데이터베이스 스키마
-- 스키마: ai_vibe_coding_test (PostgreSQL 14+)

-- 0) 기본 설정 및 확장
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- (선택) UUID 필요시
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- (선택) 텍스트 검색 최적화

-- 스키마 생성
CREATE SCHEMA IF NOT EXISTS ai_vibe_coding_test;

-- 0.1) 공통 ENUM 타입 정의
CREATE TYPE ai_vibe_coding_test.difficulty_enum AS ENUM ('EASY', 'MEDIUM', 'HARD');
CREATE TYPE ai_vibe_coding_test.problem_status_enum AS ENUM ('DRAFT', 'REVIEW', 'PUBLISHED', 'ARCHIVED');
CREATE TYPE ai_vibe_coding_test.exam_state_enum AS ENUM ('WAITING', 'RUNNING', 'ENDED');
CREATE TYPE ai_vibe_coding_test.prompt_role_enum AS ENUM ('USER', 'AI');
CREATE TYPE ai_vibe_coding_test.submission_status_enum AS ENUM ('QUEUED', 'RUNNING', 'DONE', 'FAILED');
CREATE TYPE ai_vibe_coding_test.run_grp_enum AS ENUM ('SAMPLE', 'PUBLIC', 'PRIVATE');
CREATE TYPE ai_vibe_coding_test.verdict_enum AS ENUM ('AC', 'WA', 'TLE', 'MLE', 'RE');
CREATE TYPE ai_vibe_coding_test.admin_role_enum AS ENUM ('ADMIN', 'MASTER'); -- 2.1 admins 규칙 반영
CREATE TYPE ai_vibe_coding_test.evaluation_type_enum AS ENUM ('TURN_EVAL', 'HOLISTIC_FLOW'); -- 평가 유형

-- 1) 관리자 및 권한 (Admins)

-- 2.1 admins
CREATE TABLE ai_vibe_coding_test.admins (
    id BIGSERIAL PRIMARY KEY,
    admin_number VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ai_vibe_coding_test.admin_role_enum NOT NULL DEFAULT 'ADMIN',
    is_2fa_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2.1.a admin_numbers (초대 코드 관리)
CREATE TABLE ai_vibe_coding_test.admin_numbers (
    id BIGSERIAL PRIMARY KEY,
    admin_number VARCHAR(50) NOT NULL UNIQUE,
    label VARCHAR(100),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    issued_by BIGINT REFERENCES ai_vibe_coding_test.admins(id),
    assigned_admin_id BIGINT REFERENCES ai_vibe_coding_test.admins(id),
    expires_at TIMESTAMPTZ,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2.15 admin_audit_logs (감사 로그)
CREATE TABLE ai_vibe_coding_test.admin_audit_logs (
    id BIGSERIAL PRIMARY KEY,
    admin_id BIGINT NOT NULL REFERENCES ai_vibe_coding_test.admins(id),
    action VARCHAR(100) NOT NULL,
    details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2) 문제 및 스펙 (Problems & Specs)

-- 2.3 problems
CREATE TABLE ai_vibe_coding_test.problems (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    difficulty ai_vibe_coding_test.difficulty_enum NOT NULL,
    tags JSONB DEFAULT '[]',
    status ai_vibe_coding_test.problem_status_enum NOT NULL DEFAULT 'DRAFT',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- current_spec_id는 problem_specs 생성 후 FK 추가 (순환 참조 방지)
    current_spec_id BIGINT 
);

-- 2.4 problem_specs
CREATE TABLE ai_vibe_coding_test.problem_specs (
    spec_id BIGSERIAL PRIMARY KEY,
    problem_id BIGINT NOT NULL REFERENCES ai_vibe_coding_test.problems(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    content_md TEXT,
    checker_json JSONB,
    rubric_json JSONB,
    changelog_md TEXT,
    published_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(problem_id, version)
);

-- problems테이블에 current_spec_id FK 추가
ALTER TABLE ai_vibe_coding_test.problems 
ADD CONSTRAINT fk_problems_current_spec 
FOREIGN KEY (current_spec_id) REFERENCES ai_vibe_coding_test.problem_specs(spec_id);

-- 2.5 problem_sets
CREATE TABLE ai_vibe_coding_test.problem_sets (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    created_by BIGINT REFERENCES ai_vibe_coding_test.admins(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2.6 problem_set_items
CREATE TABLE ai_vibe_coding_test.problem_set_items (
    id BIGSERIAL PRIMARY KEY,
    problem_set_id BIGINT NOT NULL REFERENCES ai_vibe_coding_test.problem_sets(id) ON DELETE CASCADE,
    problem_id BIGINT NOT NULL REFERENCES ai_vibe_coding_test.problems(id),
    weight INTEGER DEFAULT 1,
    UNIQUE(problem_set_id, problem_id)
);

-- 3) 시험 및 참가자 (Exams & Participants)

-- 2.7 exams
CREATE TABLE ai_vibe_coding_test.exams (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    state ai_vibe_coding_test.exam_state_enum NOT NULL DEFAULT 'WAITING',
    starts_at TIMESTAMPTZ,
    ends_at TIMESTAMPTZ,
    version INTEGER DEFAULT 1,
    created_by BIGINT REFERENCES ai_vibe_coding_test.admins(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2.8 entry_codes (입장 코드)
CREATE TABLE ai_vibe_coding_test.entry_codes (
    code VARCHAR(64) PRIMARY KEY,
    label VARCHAR(100),
    exam_id BIGINT NOT NULL REFERENCES ai_vibe_coding_test.exams(id) ON DELETE CASCADE,
    problem_set_id BIGINT REFERENCES ai_vibe_coding_test.problem_sets(id), -- NULL 가능 (단일 문제 시험 등)
    created_by BIGINT REFERENCES ai_vibe_coding_test.admins(id),
    expires_at TIMESTAMPTZ,
    max_uses INTEGER NOT NULL DEFAULT 1,
    used_count INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2.2 participants
CREATE TABLE ai_vibe_coding_test.participants (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(20) UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2.9 exam_participants (시험 참가 및 스펙 잠금)
CREATE TABLE ai_vibe_coding_test.exam_participants (
    id BIGSERIAL PRIMARY KEY,
    exam_id BIGINT NOT NULL REFERENCES ai_vibe_coding_test.exams(id) ON DELETE CASCADE,
    participant_id BIGINT NOT NULL REFERENCES ai_vibe_coding_test.participants(id) ON DELETE CASCADE,
    -- 시험 시작 시점의 스펙 버전 고정 (Snapshot)
    spec_id BIGINT NOT NULL REFERENCES ai_vibe_coding_test.problem_specs(spec_id), 
    
    state VARCHAR(20) DEFAULT 'ACTIVE', -- 필요시 ENUM으로 변경 가능
    token_limit INTEGER NOT NULL DEFAULT 0,
    token_used INTEGER NOT NULL DEFAULT 0,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE(exam_id, participant_id)
);

-- 4) 대화 세션 (Prompt Sessions)

-- 2.10 prompt_sessions
CREATE TABLE ai_vibe_coding_test.prompt_sessions (
    id BIGSERIAL PRIMARY KEY,
    exam_id BIGINT NOT NULL,
    participant_id BIGINT NOT NULL,
    -- 무결성: exam_participants에 존재하는 조합이어야 함
    FOREIGN KEY (exam_id, participant_id) REFERENCES ai_vibe_coding_test.exam_participants(exam_id, participant_id),
    
    spec_id BIGINT NOT NULL REFERENCES ai_vibe_coding_test.problem_specs(spec_id),
    total_tokens INTEGER DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ
);

-- 2.11 prompt_messages
CREATE TABLE ai_vibe_coding_test.prompt_messages (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES ai_vibe_coding_test.prompt_sessions(id) ON DELETE CASCADE,
    turn INTEGER NOT NULL,
    role ai_vibe_coding_test.prompt_role_enum NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER DEFAULT 0,
    meta JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Full Text Search용 컬럼
    fts tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    
    UNIQUE(session_id, turn)
);

CREATE INDEX idx_prompt_messages_fts ON ai_vibe_coding_test.prompt_messages USING GIN(fts);

-- 2.11.a prompt_evaluations (평가 결과 저장 - 4번, 6.a 노드)
CREATE TABLE ai_vibe_coding_test.prompt_evaluations (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES ai_vibe_coding_test.prompt_sessions(id) ON DELETE CASCADE,
    turn INTEGER,  -- 평가 대상 턴 (NULL이면 세션 전체 평가: HOLISTIC_FLOW)
    evaluation_type ai_vibe_coding_test.evaluation_type_enum NOT NULL,  -- 'TURN_EVAL', 'HOLISTIC_FLOW'
    details JSONB NOT NULL,  -- 모든 평가 데이터(점수, 분석 내용 등) 저장
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- turn이 NULL일 수 있으므로 UNIQUE 제약 조건 유지
    UNIQUE(session_id, turn, evaluation_type)
);

-- prompt_messages와의 Foreign Key (turn별 평가인 경우만)
ALTER TABLE ai_vibe_coding_test.prompt_evaluations
ADD CONSTRAINT fk_evaluation_message
FOREIGN KEY (session_id, turn) 
REFERENCES ai_vibe_coding_test.prompt_messages(session_id, turn)
ON DELETE CASCADE;

-- 안전장치 1: Check Constraint (ENUM 값에 맞춰 수정)
-- "Holistic 평가면 turn은 NULL, Turn 평가면 turn은 NOT NULL"
-- ENUM을 텍스트로 명시적 캐스팅하여 타입 불일치 방지
ALTER TABLE ai_vibe_coding_test.prompt_evaluations
ADD CONSTRAINT check_valid_turn_logic
CHECK (
    -- 경우 1: 전체 평가(HOLISTIC_FLOW)면 -> turn은 반드시 NULL
    (evaluation_type::text = 'HOLISTIC_FLOW' AND turn IS NULL)
    OR
    -- 경우 2: 턴 평가(TURN_EVAL)면 -> turn은 반드시 NOT NULL
    (evaluation_type::text = 'TURN_EVAL' AND turn IS NOT NULL)
);

-- 안전장치 2-1: 턴 평가용 유니크 인덱스 (ENUM 값 적용)
CREATE UNIQUE INDEX idx_unique_turn_eval 
ON ai_vibe_coding_test.prompt_evaluations (session_id, turn, evaluation_type) 
WHERE evaluation_type = 'TURN_EVAL';

-- 안전장치 2-2: 전체 평가용 유니크 인덱스 (ENUM 값 적용)
CREATE UNIQUE INDEX idx_unique_holistic_flow_eval 
ON ai_vibe_coding_test.prompt_evaluations (session_id) 
WHERE evaluation_type = 'HOLISTIC_FLOW';

-- 일반 인덱스
CREATE INDEX idx_prompt_evaluations_session ON ai_vibe_coding_test.prompt_evaluations(session_id, turn);

-- 5) 제출 및 채점 (Submissions & Scores)

-- 2.12 submissions
CREATE TABLE ai_vibe_coding_test.submissions (
    id BIGSERIAL PRIMARY KEY,
    exam_id BIGINT NOT NULL,
    participant_id BIGINT NOT NULL,
    FOREIGN KEY (exam_id, participant_id) REFERENCES ai_vibe_coding_test.exam_participants(exam_id, participant_id),
    
    spec_id BIGINT NOT NULL REFERENCES ai_vibe_coding_test.problem_specs(spec_id),
    
    lang VARCHAR(20) NOT NULL,
    status ai_vibe_coding_test.submission_status_enum NOT NULL DEFAULT 'QUEUED',
    code_inline TEXT,
    code_sha256 CHAR(64),
    code_bytes INTEGER,
    code_loc INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2.13 submission_runs (개별 테스트 케이스 실행 결과)
CREATE TABLE ai_vibe_coding_test.submission_runs (
    id BIGSERIAL PRIMARY KEY,
    submission_id BIGINT NOT NULL REFERENCES ai_vibe_coding_test.submissions(id) ON DELETE CASCADE,
    case_index INTEGER NOT NULL,
    grp ai_vibe_coding_test.run_grp_enum NOT NULL DEFAULT 'PUBLIC',
    verdict ai_vibe_coding_test.verdict_enum NOT NULL,
    time_ms NUMERIC(10, 3),
    mem_kb INTEGER,
    stdout_bytes INTEGER,
    stderr_bytes INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE(submission_id, case_index)
);

-- 2.14 scores (최종 점수)
CREATE TABLE ai_vibe_coding_test.scores (
    submission_id BIGINT PRIMARY KEY REFERENCES ai_vibe_coding_test.submissions(id) ON DELETE CASCADE,
    prompt_score NUMERIC(5, 2) DEFAULT 0,
    perf_score NUMERIC(5, 2) DEFAULT 0,
    correctness_score NUMERIC(5, 2) DEFAULT 0,
    total_score NUMERIC(5, 2) DEFAULT 0, -- (프롬프트 40 + 성능 30 + 정답 30)
    rubric_json JSONB, -- 상세 평가 내역
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 6) 통계 (Statistics)

-- 2.16 exam_statistics
CREATE TABLE ai_vibe_coding_test.exam_statistics (
    id BIGSERIAL PRIMARY KEY,
    exam_id BIGINT NOT NULL REFERENCES ai_vibe_coding_test.exams(id) ON DELETE CASCADE,
    
    -- 버킷(Snapshot) 기준 시간
    bucket_start TIMESTAMPTZ NOT NULL,
    bucket_sec INTEGER NOT NULL DEFAULT 60, -- 예: 60초 단위 집계
    
    -- 실시간 운영 메트릭
    active_examinees INTEGER DEFAULT 0,
    ws_connections INTEGER DEFAULT 0,
    judge_queue_depth INTEGER DEFAULT 0,
    avg_wait_sec NUMERIC(10, 3),
    avg_run_time_ms NUMERIC(12, 3),
    errors_rate_1m NUMERIC(8, 3),
    
    -- 누적 성과 메트릭
    submissions_total INTEGER DEFAULT 0,
    submissions_done INTEGER DEFAULT 0,
    pass_rate_weighted NUMERIC(6, 4), -- 0.0 ~ 1.0
    
    -- 점수 평균
    avg_prompt_score NUMERIC(5, 2),
    avg_perf_score NUMERIC(5, 2),
    avg_correctness_score NUMERIC(5, 2),
    avg_total_score NUMERIC(5, 2),
    
    -- 토큰 사용량
    token_used_total BIGINT DEFAULT 0,
    token_used_avg NUMERIC(10, 2),
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE(exam_id, bucket_start, bucket_sec)
);

CREATE INDEX idx_exam_stats_lookup ON ai_vibe_coding_test.exam_statistics(exam_id, bucket_start DESC);

-- 7) 트리거 함수 (updated_at 자동 갱신)
CREATE OR REPLACE FUNCTION ai_vibe_coding_test.update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 트리거 적용
CREATE TRIGGER update_admins_modtime 
    BEFORE UPDATE ON ai_vibe_coding_test.admins 
    FOR EACH ROW EXECUTE PROCEDURE ai_vibe_coding_test.update_modified_column();

CREATE TRIGGER update_admin_numbers_modtime 
    BEFORE UPDATE ON ai_vibe_coding_test.admin_numbers 
    FOR EACH ROW EXECUTE PROCEDURE ai_vibe_coding_test.update_modified_column();

CREATE TRIGGER update_exams_modtime 
    BEFORE UPDATE ON ai_vibe_coding_test.exams 
    FOR EACH ROW EXECUTE PROCEDURE ai_vibe_coding_test.update_modified_column();

CREATE TRIGGER update_submissions_modtime 
    BEFORE UPDATE ON ai_vibe_coding_test.submissions 
    FOR EACH ROW EXECUTE PROCEDURE ai_vibe_coding_test.update_modified_column();
