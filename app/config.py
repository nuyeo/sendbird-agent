"""애플리케이션 설정 모듈."""

from __future__ import annotations

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# .env 파일을 os.environ에 로드 (LangChain 등 서드파티가 직접 환경변수를 참조)
load_dotenv()


class Settings(BaseSettings):
    """환경변수 기반 애플리케이션 설정."""

    # Sendbird
    sendbird_app_id: str
    sendbird_api_token: str

    # OpenAI
    openai_api_key: str

    # Agent
    llm_model: str = "gpt-3.5-turbo"
    llm_temperature: float = 0.0
    chunk_size: int = 500
    chunk_overlap: int = 0

    # Server
    debug: bool = False

    model_config = {"env_file": ".env"}


settings = Settings()
