"""테스트 공통 픽스처."""

from __future__ import annotations

import os

# Settings 초기화 전에 환경변수를 설정해야 하므로 모듈 최상단에서 처리
os.environ.setdefault("SENDBIRD_APP_ID", "test_app_id")
os.environ.setdefault("SENDBIRD_API_TOKEN", "test_api_token")
os.environ.setdefault("OPENAI_API_KEY", "test_openai_key")
os.environ.setdefault("POSTGRES_URL", "postgresql+psycopg://cs_agent:pw@localhost:5432/cs_agent")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_at_least_32_chars_long")
