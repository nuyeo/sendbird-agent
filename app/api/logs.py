"""대화 로그 조회 및 피드백 API."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rate_limit import limiter
from app.config import settings
from app.observability.logger import get_logger
from app.storage.database import get_db
from app.storage.repositories import chat_log_repo

logger = get_logger()

router = APIRouter()


class FeedbackRequest(BaseModel):
    """피드백 요청 모델."""

    feedback: Literal["up", "down"] = Field(..., description="Feedback type: 'up' or 'down'")


@router.put("/api/logs/{log_id}/feedback")
@limiter.limit(settings.rate_limit_logs_feedback)
async def update_feedback(
    request: Request,
    log_id: str,
    body: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """특정 대화 로그에 피드백을 업데이트합니다.

    Args:
        request: starlette 요청 객체 (slowapi 의존성).
        log_id: 로그 항목 UUID.
        body: 피드백 요청 본문.
        db: 비동기 DB 세션.

    Returns:
        성공 응답 또는 에러.
    """
    log = await chat_log_repo.update_feedback(db, log_id=log_id, feedback=body.feedback)
    if log is None:
        logger.warning("로그를 찾을 수 없음", log_id=log_id)
        raise HTTPException(status_code=404, detail="Log not found")

    logger.info("피드백 추가", log_id=log_id, feedback=body.feedback)
    return {"status": "success", "log_id": log_id, "feedback": body.feedback}


@router.get("/api/logs")
@limiter.limit(settings.rate_limit_logs_read)
async def get_chat_logs(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """최신 순으로 대화 로그를 반환합니다.

    Args:
        request: starlette 요청 객체 (slowapi 의존성).
        db: 비동기 DB 세션.

    Returns:
        로그 리스트와 총 개수를 담은 딕셔너리.
    """
    logs = await chat_log_repo.list_chat_logs(db)
    return {
        "logs": [
            {
                "id": str(log.id),
                "user_id": log.user_id,
                "question": log.question,
                "answer": log.answer,
                "latency_ms": log.latency_ms,
                "token_usage": log.token_usage,
                "feedback": log.feedback,
                "timestamp": log.created_at.isoformat(),
            }
            for log in logs
        ],
        "total": len(logs),
    }
