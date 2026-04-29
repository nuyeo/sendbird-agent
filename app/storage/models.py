"""SQLAlchemy ORM 모델 정의."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import UUID, CheckConstraint, Date, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.database import Base


class ChatLog(Base):
    """대화 로그 테이블 (webhook.py의 chat_logs list 대체)."""

    __tablename__ = "chat_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_usage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    feedback: Mapped[str | None] = mapped_column(
        String(10),
        CheckConstraint("feedback IN ('up', 'down')", name="ck_chat_logs_feedback"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )


class Order(Base):
    """주문 테이블 (tools.py의 MOCK_DB dict 대체)."""

    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    item: Mapped[str] = mapped_column(String(200), nullable=False)
    price: Mapped[int] = mapped_column(
        Integer,
        CheckConstraint("price >= 0", name="ck_orders_price_non_negative"),
        nullable=False,
    )
    purchased_at: Mapped[date] = mapped_column(Date, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
