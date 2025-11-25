"""
환경 설정 모듈
PostgreSQL, Redis, LLM API 등의 설정을 관리합니다.
"""
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """애플리케이션 환경 설정"""
    
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
    
    # 기본 LLM 설정
    DEFAULT_LLM_MODEL: str = "gemini-2.5-flash"  # .env에서 오버라이드 가능 (기본값)
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 4096
    
    # Judge0 설정 (코드 실행 평가)
    JUDGE0_API_URL: str = "http://localhost:2358"
    JUDGE0_API_KEY: Optional[str] = None
    
    # Spring Boot 콜백 설정
    SPRING_CALLBACK_URL: str = "http://localhost:8080/api/ai/callback"
    SPRING_API_KEY: Optional[str] = None
    
    # SQS 설정 (선택사항)
    AWS_REGION: str = "ap-northeast-2"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    SQS_QUEUE_URL: Optional[str] = None
    
    # LangGraph 체크포인트 설정
    CHECKPOINT_TTL_SECONDS: int = 3600  # 1시간
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """싱글톤 설정 객체 반환"""
    return Settings()


settings = get_settings()


