"""주문 CRUD."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models import Order


async def get_order(db: AsyncSession, order_id: str) -> Order | None:
    """주문 번호로 주문을 조회합니다.

    Args:
        db: 비동기 DB 세션.
        order_id: 주문 번호.

    Returns:
        Order 인스턴스, 없으면 None.
    """
    result = await db.execute(select(Order).where(Order.order_id == order_id))
    return result.scalar_one_or_none()


async def cancel_order(db: AsyncSession, order_id: str) -> Order:
    """'상품 준비 중' 상태의 주문을 취소 처리합니다.

    동시 취소 요청 방지를 위해 SELECT FOR UPDATE로 잠금 후 상태를 변경합니다.

    Args:
        db: 비동기 DB 세션.
        order_id: 취소할 주문 번호.

    Returns:
        취소 처리된 Order 인스턴스.

    Raises:
        ValueError: 주문이 존재하지 않거나 취소 가능 상태가 아닌 경우.
    """
    async with db.begin():
        result = await db.execute(select(Order).where(Order.order_id == order_id).with_for_update())
        order = result.scalar_one_or_none()

        if order is None:
            raise ValueError(f"존재하지 않는 주문 번호입니다: {order_id}")

        if order.status != "상품 준비 중":
            raise ValueError(f"취소 불가 상태입니다: {order.status}")

        order.status = "취소 완료"
        order.updated_at = datetime.now(UTC)

    await db.refresh(order)
    return order
