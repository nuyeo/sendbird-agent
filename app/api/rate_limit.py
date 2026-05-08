"""REST 엔드포인트용 rate limiter 싱글톤.

slowapi의 Limiter를 Redis storage로 구성한다. Redis를 backing store로 사용해
멀티 워커 환경에서도 일관된 rate limit이 적용되도록 한다.

테스트에서는 settings.rate_limit_enabled=false로 비활성화한다.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings


def _build_limiter() -> Limiter:
    """설정값에 따라 Limiter 인스턴스를 구성합니다.

    Returns:
        구성 완료된 Limiter. rate_limit_enabled=False면 비활성 상태.
    """
    limiter = Limiter(
        key_func=get_remote_address,
        storage_uri=settings.redis_url,
        strategy="fixed-window",
    )
    if not settings.rate_limit_enabled:
        limiter.enabled = False
    return limiter


limiter = _build_limiter()
