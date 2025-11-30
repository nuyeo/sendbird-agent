from datetime import datetime, timedelta
from langchain.tools import tool

# 📌 가짜 DB (구매 날짜 추가 - 오늘 날짜 기준으로 동적 생성)
# C303은 '오늘' 구매한 것으로 설정 -> 경과일 0일 -> 전액 환불 대상
today = datetime.now()

MOCK_DB = {
    "A101": {
        "status": "배송 완료",
        "item": "무선 키보드",
        "price": 50000,
        "purchased_at": (today - timedelta(days=10)).strftime("%Y-%m-%d")  # 10일 전
    },
    "B202": {
        "status": "배송 중",
        "item": "게이밍 마우스",
        "price": 30000,
        "purchased_at": (today - timedelta(days=3)).strftime("%Y-%m-%d")  # 3일 전
    },
    "C303": {
        "status": "상품 준비 중",
        "item": "27인치 모니터",
        "price": 250000,
        "purchased_at": today.strftime("%Y-%m-%d")  # 오늘 (0일 전)
    }
}


@tool
def search_order_status(order_id: str) -> str:
    """
    주문 번호(order_id)를 받아서 상세 정보를 조회합니다.
    배송 상태, 상품명, 가격, 구매일, 그리고 오늘 기준 경과일(days_passed)을 반환합니다.
    환불 계산 전에 반드시 이 도구를 먼저 사용해야 합니다.
    """
    print(f"🚚 [Tool: 조회] 주문 ID: {order_id}")
    order = MOCK_DB.get(order_id)

    if order:
        # 경과일 계산 로직
        p_date = datetime.strptime(order['purchased_at'], "%Y-%m-%d")
        days_passed = (datetime.now() - p_date).days

        return (
            f"주문번호: {order_id}\n"
            f"- 상태: {order['status']}\n"
            f"- 상품: {order['item']}\n"
            f"- 가격: {order['price']}원\n"
            f"- 구매일: {order['purchased_at']} ({days_passed}일 경과)"
        )
    return "조회된 주문 내역이 없습니다. 주문 번호를 다시 확인해주세요."


@tool
def cancel_order(order_id: str) -> str:
    """
    주문 번호를 받아 취소를 처리합니다. '상품 준비 중'일 때만 가능합니다.
    """
    print(f"🗑️ [Tool: 취소] 주문 취소 시도: {order_id}")

    order = MOCK_DB.get(order_id)
    if not order:
        return "존재하지 않는 주문 번호입니다."

    if order['status'] == "상품 준비 중":
        order['status'] = "취소 완료"
        return f"주문 {order_id}가 정상적으로 취소되었습니다."
    else:
        return f"취소 실패: 현재 '{order['status']}' 상태이므로 취소가 불가능합니다."


@tool
def refund_calculator(price: int, days_passed: int) -> str:
    """
    상품 가격(price)과 경과일(days_passed)을 받아 환불액을 계산합니다.
    이 함수를 호출하기 전에 반드시 search_order_status를 통해 정확한 가격과 경과일을 확인해야 합니다.
    """
    print(f"💰 [Tool: 계산] 가격: {price}원, 경과일: {days_passed}일")

    if days_passed <= 7:
        refund_amount = price
        return f"전액 환불 가능합니다. (예상 환불액: {refund_amount}원)"
    elif days_passed <= 14:
        refund_amount = int(price * 0.9)
        return f"90% 환불 가능합니다. (예상 환불액: {refund_amount}원)"
    else:
        return "구매 후 14일이 지나 환불이 불가능합니다."

@tool
def transfer_to_human(reason: str) -> str:
    """
    사용자가 상담원 연결을 강력히 원하거나, AI가 해결할 수 없는 문제일 때 이 도구를 사용합니다.
    reason에는 연결 요청 사유를 요약해서 적습니다.
    """
    print(f"🚨 [Tool: Handoff] 상담원 연결 요청 발생! 사유: {reason}")
    # 실제로는 여기서 Sendbird Desk API를 호출하여 티켓을 생성해야 합니다.
    # 이번 프로젝트에서는 '연결 요청됨' 상태를 반환하여 대시보드에 표시합니다.
    return "상담원 연결 요청이 시스템에 접수되었습니다. 잠시만 기다려주시면 담당자가 채팅방에 입장할 것입니다."