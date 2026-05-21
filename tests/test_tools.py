"""에이전트 도구 단위 테스트."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.tools import refund_calculator, search_order_status


def test_refund_calculator_full_refund() -> None:
    """수령 후 7일 이내 전액 환불 테스트."""
    result = refund_calculator.invoke({"price": 10000, "days_since_delivery": 3})
    assert "전액 환불" in result
    assert "10000원" in result


def test_refund_calculator_partial_refund() -> None:
    """수령 후 8~14일 90% 환불 테스트."""
    result = refund_calculator.invoke({"price": 10000, "days_since_delivery": 10})
    assert "90%" in result
    assert "9000원" in result


def test_refund_calculator_expired() -> None:
    """수령 후 14일 초과 환불 불가 테스트."""
    result = refund_calculator.invoke({"price": 10000, "days_since_delivery": 15})
    assert "불가능" in result


@pytest.mark.asyncio
@patch("app.agent.tools.order_repo.get_order")
async def test_search_order_exists(mock_get: AsyncMock) -> None:
    """존재하는 주문 조회 테스트 (DB mock)."""
    from app.storage.models import Order

    mock_order = Order(
        order_id="A101",
        status="배송 완료",
        item="무선 키보드",
        price=50000,
        purchased_at=date(2025, 1, 1),
    )
    mock_get.return_value = mock_order

    result = await search_order_status.ainvoke({"order_id": "A101"})
    assert "주문번호: A101" in result
    assert "배송 완료" in result


@pytest.mark.asyncio
@patch("app.agent.tools.order_repo.get_order", new_callable=AsyncMock, return_value=None)
async def test_search_order_not_found(mock_get: AsyncMock) -> None:
    """없는 주문 조회 테스트 (DB mock)."""
    result = await search_order_status.ainvoke({"order_id": "Z999"})
    assert "조회된 주문 내역이 없습니다" in result
