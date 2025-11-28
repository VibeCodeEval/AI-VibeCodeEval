"""
데이터베이스 Enum 타입 정의
Spring Boot와 동일한 값을 사용해야 함
"""
import enum


class DifficultyEnum(str, enum.Enum):
    """문제 난이도"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class ProblemStatusEnum(str, enum.Enum):
    """문제 상태"""
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ExamStateEnum(str, enum.Enum):
    """시험 상태"""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    ENDED = "ended"


class ExamParticipantStateEnum(str, enum.Enum):
    """시험 참가자 상태"""
    REGISTERED = "registered"
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    TIMEOUT = "timeout"
    DISQUALIFIED = "disqualified"


class SubmissionStatusEnum(str, enum.Enum):
    """제출 상태"""
    PENDING = "pending"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    ERROR = "error"


class PromptRoleEnum(str, enum.Enum):
    """프롬프트 역할"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class TestRunGrpEnum(str, enum.Enum):
    """테스트 실행 그룹"""
    SAMPLE = "sample"
    HIDDEN = "hidden"


class VerdictEnum(str, enum.Enum):
    """평가 결과"""
    PENDING = "pending"
    ACCEPTED = "accepted"
    WRONG_ANSWER = "wrong_answer"
    TIME_LIMIT_EXCEEDED = "time_limit_exceeded"
    MEMORY_LIMIT_EXCEEDED = "memory_limit_exceeded"
    RUNTIME_ERROR = "runtime_error"
    COMPILATION_ERROR = "compilation_error"
    INTERNAL_ERROR = "internal_error"


class WriterResponseStatus(str, enum.Enum):
    """Writer LLM 응답 상태 (그래프에서 사용)"""
    SUCCESS = "success"
    FAILED_TECHNICAL = "failed_technical"
    FAILED_GUARDRAIL = "failed_guardrail"
    FAILED_THRESHOLD = "failed_threshold"
    FAILED_RATE_LIMIT = "failed_rate_limit"
    FAILED_WRITING = "failed_writing"


class IntentAnalyzerStatus(str, enum.Enum):
    """Intent Analyzer 상태 (그래프에서 사용)"""
    PASSED_HINT = "passed_hint"
    FAILED_GUARDRAIL = "failed_guardrail"
    FAILED_RATE_LIMIT = "failed_rate_limit"
    PASSED_SUBMIT = "passed_submit"


class CodeIntentType(str, enum.Enum):
    """코드 의도 타입 (8가지 패턴 - Claude Prompt Engineering)"""
    SYSTEM_PROMPT = "system_prompt"  # 신규 추가
    RULE_SETTING = "rule_setting"
    GENERATION = "generation"
    OPTIMIZATION = "optimization"
    DEBUGGING = "debugging"
    TEST_CASE = "test_case"
    HINT_OR_QUERY = "hint_or_query"
    FOLLOW_UP = "follow_up"



