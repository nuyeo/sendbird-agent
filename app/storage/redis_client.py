"""Redis 비동기 클라이언트 싱글톤."""

from __future__ import annotations

import redis.asyncio as aioredis  # type: ignore[import]

from app.config import settings

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    """애플리케이션 생명주기 동안 재사용되는 Redis 클라이언트를 반환합니다.

    Returns:
        redis.asyncio.Redis 인스턴스.

    Raises:
        RuntimeError: initialize_redis()가 먼저 호출되지 않은 경우.
    """
    if _redis is None:
        raise RuntimeError("Redis가 초기화되지 않았습니다. initialize_redis()를 먼저 호출하세요.")
    return _redis


async def initialize_redis() -> None:
    """애플리케이션 시작 시 Redis 연결 풀을 초기화합니다."""
    global _redis
    _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    await _redis.ping()


async def close_redis() -> None:
    """애플리케이션 종료 시 Redis 연결을 닫습니다."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def ping() -> bool:
    """Redis 연결 상태를 확인합니다.

    Returns:
        연결이 정상이면 True.
    """
    try:
        client = get_redis()
        return await client.ping()
    except Exception:
        return False
