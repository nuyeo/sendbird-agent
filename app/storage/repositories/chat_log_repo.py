"""대화 로그 CRUD."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models import ChatLog


async def create_chat_log(
    db: AsyncSession,
    *,
    log_id: str,
    user_id: str,
    question: str,
    answer: str,
    latency_ms: int | None = None,
    token_usage: dict[str, Any] | None = None,
) -> ChatLog:
    """새 대화 로그를 INSERT합니다.

    Args:
        db: 비동기 DB 세션.
        log_id: 요청 ID (UUID 문자열).
        user_id: 사용자 식별자.
        question: 사용자 질문.
        answer: AI 응답.
        latency_ms: 응답 생성 소요 시간(ms).
        token_usage: OpenAI usage 딕셔너리.

    Returns:
        저장된 ChatLog 인스턴스.
    """
    log = ChatLog(
        id=uuid.UUID(log_id),
        user_id=user_id,
        question=question,
        answer=answer,
        latency_ms=latency_ms,
        token_usage=token_usage,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def list_chat_logs(db: AsyncSession, *, limit: int = 100) -> list[ChatLog]:
    """최신 순으로 대화 로그를 조회합니다.

    Args:
        db: 비동기 DB 세션.
        limit: 최대 반환 개수.

    Returns:
        ChatLog 리스트.
    """
    result = await db.execute(select(ChatLog).order_by(ChatLog.created_at.desc()).limit(limit))
    return list(result.scalars().all())


async def update_feedback(db: AsyncSession, *, log_id: str, feedback: str) -> ChatLog | None:
    """특정 로그에 피드백을 업데이트합니다.

    Args:
        db: 비동기 DB 세션.
        log_id: 대상 로그 UUID 문자열.
        feedback: 'up' 또는 'down'.

    Returns:
        업데이트된 ChatLog 인스턴스, 없으면 None.
    """
    try:
        target_id = uuid.UUID(log_id)
    except ValueError:
        return None

    await db.execute(update(ChatLog).where(ChatLog.id == target_id).values(feedback=feedback))
    await db.commit()

    result = await db.execute(select(ChatLog).where(ChatLog.id == target_id))
    return result.scalar_one_or_none()
