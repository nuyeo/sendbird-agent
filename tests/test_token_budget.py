"""토큰 예산 미들웨어 단위 테스트."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.api.middleware import is_within_budget, record_token_spend


@pytest.mark.asyncio
async def test_is_within_budget_unlimited_when_zero() -> None:
    """token_budget_daily=0 이면 항상 True를 반환해야 합니다."""
    with patch("app.api.middleware.settings") as mock_settings:
        mock_settings.token_budget_daily = 0
        result = await is_within_budget("user1")
    assert result is True


@pytest.mark.asyncio
async def test_is_within_budget_true_when_under_limit() -> None:
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value="5000")
    with (
        patch("app.api.middleware.settings") as mock_settings,
        patch("app.api.middleware.get_redis", return_value=mock_redis),
    ):
        mock_settings.token_budget_daily = 100_000
        result = await is_within_budget("user1")
    assert result is True


@pytest.mark.asyncio
async def test_is_within_budget_false_when_at_limit() -> None:
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value="100000")
    with (
        patch("app.api.middleware.settings") as mock_settings,
        patch("app.api.middleware.get_redis", return_value=mock_redis),
    ):
        mock_settings.token_budget_daily = 100_000
        result = await is_within_budget("user1")
    assert result is False


@pytest.mark.asyncio
async def test_is_within_budget_true_when_no_record() -> None:
    """오늘 사용 기록이 없으면 True를 반환해야 합니다."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    with (
        patch("app.api.middleware.settings") as mock_settings,
        patch("app.api.middleware.get_redis", return_value=mock_redis),
    ):
        mock_settings.token_budget_daily = 100_000
        result = await is_within_budget("user1")
    assert result is True


@pytest.mark.asyncio
async def test_record_token_spend_skipped_when_unlimited() -> None:
    """token_budget_daily=0 이면 Redis를 호출하지 않아야 합니다."""
    mock_redis = AsyncMock()
    with (
        patch("app.api.middleware.settings") as mock_settings,
        patch("app.api.middleware.get_redis", return_value=mock_redis),
    ):
        mock_settings.token_budget_daily = 0
        await record_token_spend("user1", 1000)
    mock_redis.incrby.assert_not_called()


@pytest.mark.asyncio
async def test_record_token_spend_increments_and_sets_expire_on_first_call() -> None:
    """첫 기록 시 INCRBY 후 EXPIRE를 설정해야 합니다."""
    mock_redis = AsyncMock()
    mock_redis.incrby = AsyncMock(return_value=1000)  # 첫 기록 = tokens와 동일
    mock_redis.expire = AsyncMock()
    with (
        patch("app.api.middleware.settings") as mock_settings,
        patch("app.api.middleware.get_redis", return_value=mock_redis),
    ):
        mock_settings.token_budget_daily = 100_000
        await record_token_spend("user1", 1000)
    mock_redis.incrby.assert_awaited_once()
    mock_redis.expire.assert_awaited_once()


@pytest.mark.asyncio
async def test_record_token_spend_no_expire_on_subsequent_calls() -> None:
    """이미 사용 기록이 있으면 EXPIRE를 재설정하지 않아야 합니다."""
    mock_redis = AsyncMock()
    mock_redis.incrby = AsyncMock(return_value=5000)  # 이전 누계 있음
    mock_redis.expire = AsyncMock()
    with (
        patch("app.api.middleware.settings") as mock_settings,
        patch("app.api.middleware.get_redis", return_value=mock_redis),
    ):
        mock_settings.token_budget_daily = 100_000
        await record_token_spend("user1", 500)
    mock_redis.expire.assert_not_called()


@pytest.mark.asyncio
async def test_record_token_spend_skipped_when_tokens_zero() -> None:
    mock_redis = AsyncMock()
    with (
        patch("app.api.middleware.settings") as mock_settings,
        patch("app.api.middleware.get_redis", return_value=mock_redis),
    ):
        mock_settings.token_budget_daily = 100_000
        await record_token_spend("user1", 0)
    mock_redis.incrby.assert_not_called()
