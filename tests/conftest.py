"""테스트 공통 픽스처."""

from __future__ import annotations

import os

# Settings 초기화 전에 환경변수를 설정해야 하므로 모듈 최상단에서 처리
os.environ.setdefault("OPENAI_API_KEY", "test_openai_key")
os.environ.setdefault("POSTGRES_URL", "postgresql+psycopg://cs_agent:pw@localhost:5432/cs_agent")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_at_least_32_chars_long")
# 테스트에서는 slowapi rate limit을 비활성화 (테스트 격리 + 동일 클라이언트 IP 반복 호출)
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
