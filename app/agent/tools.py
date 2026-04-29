"""CS 에이전트 도구 (주문 조회, 취소, 환불 계산, 상담원 연결)."""

from __future__ import annotations

from datetime import datetime

from langchain.tools import tool

from app.observability.logger import get_logger
from app.storage.database import AsyncSessionLocal
from app.storage.repositories import order_repo

logger = get_logger()


@tool
async def search_order_status(order_id: str) -> str:
    """주문 번호(order_id)를 받아서 상세 정보를 조회합니다.

    배송 상태, 상품명, 가격, 구매일, 그리고 오늘 기준 경과일(days_passed)을 반환합니다.
    환불 계산 전에 반드시 이 도구를 먼저 사용해야 합니다.
    """
    logger.info("주문 조회 도구 호출", order_id=order_id)
    async with AsyncSessionLocal() as db:
        order = await order_repo.get_order(db, order_id)

    if order is None:
        return "조회된 주문 내역이 없습니다. 주문 번호를 다시 확인해주세요."

    days_passed = (datetime.now().date() - order.purchased_at).days
    return (
        f"주문번호: {order_id}\n"
        f"- 상태: {order.status}\n"
        f"- 상품: {order.item}\n"
        f"- 가격: {order.price}원\n"
        f"- 구매일: {order.purchased_at} ({days_passed}일 경과)"
    )


@tool
async def cancel_order(order_id: str) -> str:
    """주문 번호를 받아 취소를 처리합니다. '상품 준비 중'일 때만 가능합니다."""
    logger.info("주문 취소 도구 호출", order_id=order_id)
    async with AsyncSessionLocal() as db:
        try:
            await order_repo.cancel_order(db, order_id)
        except ValueError as e:
            return str(e)

    return f"주문 {order_id}가 정상적으로 취소되었습니다."


@tool
def refund_calculator(price: int, days_passed: int) -> str:
    """상품 가격(price)과 경과일(days_passed)을 받아 환불액을 계산합니다.

    호출 전에 반드시 search_order_status로 정확한 가격과 경과일을 확인해야 합니다.
    """
    logger.info("환불 계산 도구 호출", price=price, days_passed=days_passed)
    if days_passed <= 7:
        return f"전액 환불 가능합니다. (예상 환불액: {price}원)"
    elif days_passed <= 14:
        refund_amount = int(price * 0.9)
        return f"90% 환불 가능합니다. (예상 환불액: {refund_amount}원)"
    else:
        return "구매 후 14일이 지나 환불이 불가능합니다."


@tool
def transfer_to_human(reason: str) -> str:
    """사용자가 상담원 연결을 강력히 원하거나, AI가 해결할 수 없는 문제일 때 이 도구를 사용합니다.

    reason에는 연결 요청 사유를 요약해서 적습니다.
    """
    logger.info("상담원 연결 요청", reason=reason)
    return (
        "상담원 연결 요청이 시스템에 접수되었습니다. "
        "잠시만 기다려주시면 담당자가 채팅방에 입장할 것입니다."
    )
