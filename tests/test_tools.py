from app.tools import refund_calculator, search_order_status

def test_refund_calculator_full_refund():
    # 7일 이내 전액 환불 테스트
    # [수정] 함수 호출 대신 .invoke({"인자명": 값}) 사용
    result = refund_calculator.invoke({"price": 10000, "days_passed": 3})
    assert "전액 환불" in result
    assert "10000원" in result

def test_refund_calculator_partial_refund():
    # 14일 이내 90% 환불 테스트
    result = refund_calculator.invoke({"price": 10000, "days_passed": 10})
    assert "90%" in result
    assert "9000원" in result

def test_refund_calculator_expired():
    # 기간 만료 테스트
    result = refund_calculator.invoke({"price": 10000, "days_passed": 15})
    assert "불가능" in result or "만료" in result

def test_search_order_exists():
    # 존재하는 주문 조회
    # [수정] 문자열 하나만 넣을 때도 딕셔너리 형태 권장
    result = search_order_status.invoke({"order_id": "A101"})
    # MOCK_DB 데이터에 따라 검증 (A101은 배송 완료 상태)
    assert "주문번호: A101" in result
    assert "배송 완료" in result

def test_search_order_not_found():
    # 없는 주문 조회
    result = search_order_status.invoke({"order_id": "Z999"})
    assert "조회된 주문 내역이 없습니다" in result