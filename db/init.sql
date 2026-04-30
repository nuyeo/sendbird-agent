-- Phase A 초기 스키마
-- 컨테이너 최초 실행 시 한 번만 실행됩니다.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 대화 로그 (webhook.py의 chat_logs list 대체)
CREATE TABLE IF NOT EXISTS chat_logs (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     VARCHAR(100) NOT NULL,
    question    TEXT         NOT NULL,
    answer      TEXT         NOT NULL,
    latency_ms  INTEGER,
    token_usage JSONB,
    feedback    VARCHAR(10)  CHECK (feedback IN ('up', 'down')),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_logs_user_id    ON chat_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_logs_created_at ON chat_logs(created_at DESC);

-- 주문 데이터 (tools.py의 MOCK_DB dict 대체)
CREATE TABLE IF NOT EXISTS orders (
    order_id     VARCHAR(20)  PRIMARY KEY,
    user_id      VARCHAR(100),
    status       VARCHAR(50)  NOT NULL,
    item         VARCHAR(200) NOT NULL,
    price        INTEGER      NOT NULL CHECK (price >= 0),
    purchased_at DATE         NOT NULL,
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
