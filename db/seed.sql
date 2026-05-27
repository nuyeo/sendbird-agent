-- MOCK_DB 초기 데이터 시딩
-- purchased_at을 CURRENT_DATE 기준 동적으로 생성해 테스트 일관성 유지

-- 배송 완료(A101)는 수령일(delivered_at) 보유, 배송 중/준비 중은 NULL.
INSERT INTO orders (order_id, status, item, price, purchased_at, delivered_at)
VALUES
    ('A101', '배송 완료',    '무선 키보드',   50000,  CURRENT_DATE - INTERVAL '10 days', CURRENT_DATE - INTERVAL '8 days'),
    ('B202', '배송 중',      '게이밍 마우스', 30000,  CURRENT_DATE - INTERVAL '3 days',  NULL),
    ('C303', '상품 준비 중', '27인치 모니터', 250000, CURRENT_DATE,                       NULL)
ON CONFLICT (order_id) DO NOTHING;
