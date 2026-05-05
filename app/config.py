"""애플리케이션 설정 모듈."""

from __future__ import annotations

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

# .env 파일을 os.environ에 로드 (LangChain 등 서드파티가 직접 환경변수를 참조)
load_dotenv()


class Settings(BaseSettings):
    """환경변수 기반 애플리케이션 설정."""

    # OpenAI
    openai_api_key: str

    # Agent
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.0
    chunk_size: int = 500
    chunk_overlap: int = 0

    # PostgreSQL
    postgres_url: str = "postgresql+psycopg://cs_agent:cs_agent_pw@localhost:5432/cs_agent"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    session_ttl_seconds: int = 86400  # 24시간

    # JWT (WebSocket 인증)
    jwt_secret_key: str = Field(..., min_length=32)
    jwt_expire_minutes: int = Field(60, ge=1)

    # 동시 LLM 호출 제한 (단일 워커 기준)
    max_concurrent_llm: int = Field(50, ge=1)

    # Server
    debug: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
