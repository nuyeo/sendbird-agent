"""PostgreSQL 비동기 엔진 및 세션 팩토리."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.postgres_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """SQLAlchemy 모델 베이스 클래스."""


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI Depends용 DB 세션 의존성.

    Yields:
        비동기 SQLAlchemy 세션.
    """
    async with AsyncSessionLocal() as session:
        yield session
