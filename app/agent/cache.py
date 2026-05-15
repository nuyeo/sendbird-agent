"""정확 매칭 기반 시맨틱 캐시.

사용자 쿼리를 소문자 + 공백 정규화한 뒤 SHA-256 해시를 Redis 키로 사용합니다.
FAQ 반복 질문에서 30~40% 적중률을 기대할 수 있으며, 캐시 히트 시 LLM 호출을
완전히 우회해 토큰 비용을 절감합니다.

Vector Search 유사도 캐시는 추후 필요 시 도입합니다.
"""

from __future__ import annotations

import hashlib
import re

from app.config import settings
from app.observability.logger import get_logger
from app.storage.redis_client import get_redis

logger = get_logger()

_CACHE_KEY_PREFIX = "semantic_cache:"


def _normalize_query(query: str) -> str:
    """쿼리를 정규화합니다 (소문자 변환 + 연속 공백 단일화).

    Args:
        query: 원본 사용자 쿼리.

    Returns:
        정규화된 쿼리 문자열.
    """
    return re.sub(r"\s+", " ", query.lower().strip())


def _cache_key(query: str) -> str:
    """정규화된 쿼리의 SHA-256 앞 16자리를 Redis 키로 반환합니다.

    Args:
        query: 원본 사용자 쿼리.

    Returns:
        "semantic_cache:<16자리 hex>" 형식의 Redis 키.
    """
    normalized = _normalize_query(query)
    digest = hashlib.sha256(normalized.encode()).hexdigest()[:16]
    return f"{_CACHE_KEY_PREFIX}{digest}"


async def get_cached_response(query: str) -> str | None:
    """Redis에서 쿼리에 해당하는 캐시 응답을 조회합니다.

    Args:
        query: 사용자 쿼리.

    Returns:
        캐시된 응답 문자열. 없으면 None.
    """
    if settings.semantic_cache_ttl_seconds <= 0:
        return None
    redis = get_redis()
    key = _cache_key(query)
    cached = await redis.get(key)
    if cached:
        logger.info("시맨틱 캐시 히트", key=key)
    return cached


async def set_cached_response(query: str, response: str) -> None:
    """Redis에 응답을 캐시합니다.

    Args:
        query: 사용자 쿼리.
        response: LLM이 생성한 응답 문자열.
    """
    if settings.semantic_cache_ttl_seconds <= 0:
        return
    redis = get_redis()
    key = _cache_key(query)
    await redis.setex(key, settings.semantic_cache_ttl_seconds, response)
    logger.info("시맨틱 캐시 저장", key=key, ttl=settings.semantic_cache_ttl_seconds)
