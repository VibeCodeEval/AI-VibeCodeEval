"""
환경 설정 모듈
PostgreSQL, Redis, LLM API 등의 설정을 관리합니다.
"""
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """애플리케이션 환경 설정"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"  # 알 수 없는 환경 변수는 무시
    )
    
    # 앱 기본 설정
    APP_NAME: str = "AI Vibe Coding Test Worker"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    
    # FastAPI 설정
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # PostgreSQL 설정 (Spring Boot와 공유)
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "ai_vibe_coding_test"
    
    @property
    def POSTGRES_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    @property
    def POSTGRES_URL_SYNC(self) -> str:
        return f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # Redis 설정 (세션 상태 관리)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    
    @property
    def REDIS_URL(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    # LLM API 설정
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    
    # Vertex AI 설정 (Google Cloud)
    USE_VERTEX_AI: bool = False  # Vertex AI 사용 여부
    GOOGLE_PROJECT_ID: Optional[str] = None  # GCP 프로젝트 ID
    GOOGLE_SERVICE_ACCOUNT_JSON: Optional[str] = None  # Service Account JSON (문자열)
    GOOGLE_LOCATION: str = "us-central1"  # GCP 리전
    
    # 기본 LLM 설정
    DEFAULT_LLM_MODEL: str = "gemini-2.5-flash"  # .env에서 오버라이드 가능 (기본값)
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 4096
    
    # Judge0 설정 (코드 실행 평가)
    JUDGE0_API_URL: str = "http://localhost:2358"  # 또는 "https://judge0-ce.p.rapidapi.com" (RapidAPI 사용 시)
    JUDGE0_API_KEY: Optional[str] = None
    JUDGE0_USE_RAPIDAPI: bool = False  # RapidAPI 사용 여부
    JUDGE0_RAPIDAPI_HOST: str = "judge0-ce.p.rapidapi.com"  # RapidAPI Host
    
    # 큐 시스템 설정
    USE_REDIS_QUEUE: bool = True  # True: Redis 큐, False: 메모리 큐
    
    # Spring Boot 콜백 설정
    SPRING_CALLBACK_URL: str = "http://localhost:8080/api/ai/callback"
    SPRING_API_KEY: Optional[str] = None
    
    # SQS 설정 (선택사항)
    AWS_REGION: str = "ap-northeast-2"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    SQS_QUEUE_URL: Optional[str] = None
    
    # LangGraph 체크포인트 설정
    CHECKPOINT_TTL_SECONDS: int = 86400  # 24시간 (제출 완료 후 Redis 세션 자동 삭제)
    
    # LangSmith 설정 (개발 환경에서 사용)
    # 공식 문서: https://docs.langchain.com/langsmith/create-account-api-key
    LANGCHAIN_TRACING_V2: bool = False  # 개발 환경에서만 True로 설정
    LANGCHAIN_API_KEY: Optional[str] = None  # LangSmith API Key
    LANGCHAIN_PROJECT: str = "langgraph-eval-dev"  # LangSmith 프로젝트 이름
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"  # LangSmith API 엔드포인트
    
    # Middleware 설정
    MIDDLEWARE_RATE_LIMIT_MAX_CALLS: int = 15  # Rate limit 최대 호출 횟수
    MIDDLEWARE_RATE_LIMIT_PERIOD: float = 60.0  # Rate limit 기간 (초)
    MIDDLEWARE_RETRY_MAX_RETRIES: int = 3  # 최대 재시도 횟수
    MIDDLEWARE_RETRY_INITIAL_DELAY: float = 1.0  # 초기 대기 시간 (초)
    MIDDLEWARE_RETRY_MAX_DELAY: float = 60.0  # 최대 대기 시간 (초)
    MIDDLEWARE_RETRY_BACKOFF_STRATEGY: str = "exponential"  # 백오프 전략 (exponential, linear, fixed)
    MIDDLEWARE_LOGGING_ENABLED: bool = True  # Logging Middleware 활성화 여부


@lru_cache()
def get_settings() -> Settings:
    """싱글톤 설정 객체 반환"""
    return Settings()


settings = get_settings()


