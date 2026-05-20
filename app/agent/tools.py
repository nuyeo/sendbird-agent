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

    배송 상태, 상품명, 가격, 구매일, 수령일, 그리고 수령 후 경과일
    (days_since_delivery)을 반환합니다. 미수령(배송 중/준비 중)이면 수령 관련
    정보는 '미수령'으로 표시됩니다. 환불 계산 전에 반드시 이 도구를 먼저
    호출해야 합니다.
    """
    logger.info("주문 조회 도구 호출", order_id=order_id)
    async with AsyncSessionLocal() as db:
        order = await order_repo.get_order(db, order_id)

    if order is None:
        return "조회된 주문 내역이 없습니다. 주문 번호를 다시 확인해주세요."

    today = datetime.now().date()
    purchased_days = (today - order.purchased_at).days

    if order.delivered_at is None:
        delivery_info = "- 수령일: 미수령 (수령 후 7일이 환불 기준이므로 아직 환불 계산 불가)"
    else:
        delivered_days = (today - order.delivered_at).days
        delivery_info = (
            f"- 수령일: {order.delivered_at} (수령 후 {delivered_days}일 경과, "
            f"days_since_delivery={delivered_days})"
        )

    return (
        f"주문번호: {order_id}\n"
        f"- 상태: {order.status}\n"
        f"- 상품: {order.item}\n"
        f"- 가격: {order.price}원\n"
        f"- 구매일: {order.purchased_at} (구매 후 {purchased_days}일 경과)\n"
        f"{delivery_info}"
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
def refund_calculator(price: int, days_since_delivery: int) -> str:
    """상품 가격(price)과 수령 후 경과일(days_since_delivery)을 받아 환불액을 계산합니다.

    환불 정책은 "수령 후 7일" 기준이므로 days_since_delivery만 사용합니다.
    호출 전에 반드시 search_order_status로 정확한 가격과 수령 후 경과일을 확인해야
    합니다. 미수령(아직 배송 중 또는 준비 중) 상태이면 이 도구를 호출하지 말고
    사용자에게 수령 후 환불 정책을 안내하세요.
    """
    logger.info("환불 계산 도구 호출", price=price, days_since_delivery=days_since_delivery)
    if days_since_delivery < 0:
        return "수령 전 주문은 환불 계산이 불가능합니다. 수령 후 다시 문의해주세요."
    if days_since_delivery <= 7:
        return f"전액 환불 가능합니다. (예상 환불액: {price}원)"
    if days_since_delivery <= 14:
        refund_amount = int(price * 0.9)
        return f"90% 환불 가능합니다. (예상 환불액: {refund_amount}원)"
    return "수령 후 14일이 지나 환불이 불가능합니다."


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
