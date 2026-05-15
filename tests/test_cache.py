"""시맨틱 캐시 단위 테스트."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.agent.cache import _cache_key, _normalize_query, get_cached_response, set_cached_response


def test_normalize_query_lowercases() -> None:
    assert _normalize_query("배송 조회") == "배송 조회"
    assert _normalize_query("HELLO WORLD") == "hello world"


def test_normalize_query_collapses_whitespace() -> None:
    assert _normalize_query("  hello   world  ") == "hello world"
    assert _normalize_query("a\tb") == "a b"


def test_cache_key_same_for_normalized_equivalent() -> None:
    """대소문자/공백이 달라도 같은 키를 생성해야 합니다."""
    assert _cache_key("반품 정책", "user1") == _cache_key("반품 정책  ", "user1")
    assert _cache_key("hello", "user1") == _cache_key("HELLO", "user1")


def test_cache_key_different_for_different_queries() -> None:
    assert _cache_key("배송 조회", "user1") != _cache_key("반품 정책", "user1")


def test_cache_key_different_for_different_users() -> None:
    """같은 쿼리라도 user_id가 다르면 다른 키를 반환해야 합니다."""
    assert _cache_key("환불 정책", "user1") != _cache_key("환불 정책", "user2")


@pytest.mark.asyncio
async def test_get_cached_response_returns_none_on_miss() -> None:
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    with patch("app.agent.cache.get_redis", return_value=mock_redis):
        result = await get_cached_response("없는 질문", user_id="user1")
    assert result is None


@pytest.mark.asyncio
async def test_get_cached_response_returns_cached_value() -> None:
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value="캐시된 응답")
    with patch("app.agent.cache.get_redis", return_value=mock_redis):
        result = await get_cached_response("반품 방법이 뭔가요", user_id="user1")
    assert result == "캐시된 응답"


@pytest.mark.asyncio
async def test_get_cached_response_returns_none_on_redis_error() -> None:
    """Redis 장애 시 None을 반환해야 합니다 (fail-open)."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=ConnectionError("Redis 연결 실패"))
    with patch("app.agent.cache.get_redis", return_value=mock_redis):
        result = await get_cached_response("질문", user_id="user1")
    assert result is None


@pytest.mark.asyncio
async def test_set_cached_response_calls_setex() -> None:
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()
    with patch("app.agent.cache.get_redis", return_value=mock_redis):
        await set_cached_response("질문", "응답", user_id="user1")
    mock_redis.setex.assert_awaited_once()
    args = mock_redis.setex.call_args[0]
    assert args[2] == "응답"


@pytest.mark.asyncio
async def test_set_cached_response_does_not_raise_on_redis_error() -> None:
    """Redis 장애 시 예외를 삼키고 정상 종료해야 합니다 (fail-open)."""
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock(side_effect=ConnectionError("Redis 연결 실패"))
    with patch("app.agent.cache.get_redis", return_value=mock_redis):
        await set_cached_response("질문", "응답", user_id="user1")  # 예외 없어야 함


@pytest.mark.asyncio
async def test_get_cached_response_disabled_when_ttl_zero() -> None:
    """semantic_cache_ttl_seconds=0 이면 캐시를 조회하지 않아야 합니다."""
    mock_redis = AsyncMock()
    with (
        patch("app.agent.cache.settings") as mock_settings,
        patch("app.agent.cache.get_redis", return_value=mock_redis),
    ):
        mock_settings.semantic_cache_ttl_seconds = 0
        result = await get_cached_response("질문", user_id="user1")
    mock_redis.get.assert_not_called()
    assert result is None


@pytest.mark.asyncio
async def test_set_cached_response_skipped_when_ttl_zero() -> None:
    """semantic_cache_ttl_seconds=0 이면 캐시를 저장하지 않아야 합니다."""
    mock_redis = AsyncMock()
    with (
        patch("app.agent.cache.settings") as mock_settings,
        patch("app.agent.cache.get_redis", return_value=mock_redis),
    ):
        mock_settings.semantic_cache_ttl_seconds = 0
        await set_cached_response("질문", "응답", user_id="user1")
    mock_redis.setex.assert_not_called()
