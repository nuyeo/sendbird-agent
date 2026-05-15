"""토큰 예산 유틸리티.

사용자별 일일 토큰 한도를 Redis INCR + EXPIRE로 관리합니다.
settings.token_budget_daily = 0 이면 무제한 동작합니다.

설계 의도:
- 어뷰징/무한 루프로 인한 LLM 비용 폭증 방지가 목적이므로 경쟁 조건(race
  condition)에 엄격하지 않아도 됩니다. 초 단위 동시 요청이 한도를 소폭 초과할 수
  있지만 이는 감수 가능한 범위입니다.
- LLM 호출 전에 check, 호출 후에 record를 분리해 실제 토큰 수로 정확히 기록합니다.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.config import settings
from app.observability.logger import get_logger
from app.storage.redis_client import get_redis

logger = get_logger()

_KEY_PREFIX = "token_budget:"
_DAY_TTL = 86_400  # 24시간


def _budget_key(user_id: str) -> str:
    """오늘 날짜 기준의 Redis 키를 반환합니다.

    Args:
        user_id: 사용자 식별자.

    Returns:
        "token_budget:<user_id>:<YYYY-MM-DD>" 형식의 키.
    """
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    return f"{_KEY_PREFIX}{user_id}:{today}"


async def is_within_budget(user_id: str) -> bool:
    """사용자의 일일 토큰 예산이 남아 있는지 확인합니다.

    LLM 호출 전에 호출해 한도 초과 시 호출 자체를 막습니다.

    Args:
        user_id: 사용자 식별자.

    Returns:
        예산 내에 있으면 True, 한도 초과면 False.
    """
    if settings.token_budget_daily <= 0:
        return True

    redis = get_redis()
    key = _budget_key(user_id)
    current = await redis.get(key)
    used = int(current) if current else 0

    if used >= settings.token_budget_daily:
        logger.warning(
            "일일 토큰 예산 초과",
            user_id=user_id,
            used=used,
            limit=settings.token_budget_daily,
        )
        return False
    return True


async def record_token_spend(user_id: str, tokens: int) -> None:
    """LLM 호출 후 실제 사용된 토큰 수를 일일 누계에 추가합니다.

    Args:
        user_id: 사용자 식별자.
        tokens: 이번 호출에서 사용된 총 토큰 수.
    """
    if settings.token_budget_daily <= 0 or tokens <= 0:
        return

    redis = get_redis()
    key = _budget_key(user_id)
    new_total = await redis.incrby(key, tokens)
    if new_total == tokens:
        # 오늘 첫 기록이면 TTL을 설정
        await redis.expire(key, _DAY_TTL)
    logger.info("토큰 예산 기록", user_id=user_id, added=tokens, total=new_total)
