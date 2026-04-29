"""Webhook 핸들러 및 로그 관리 엔드포인트."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.rag import get_ai_response
from app.observability.logger import bind_request_context, generate_request_id, get_logger
from app.sendbird.client import send_message
from app.storage.database import get_db
from app.storage.repositories import chat_log_repo

logger = get_logger()

router = APIRouter()

_AI_ERROR_MESSAGE = "죄송합니다. 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."


class FeedbackRequest(BaseModel):
    """피드백 요청 모델."""

    feedback: str = Field(..., description="Feedback type: 'up' or 'down'")


@router.post("/webhook")
async def sendbird_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Sendbird 웹훅 이벤트를 처리합니다.

    Args:
        request: FastAPI 요청 객체.
        background_tasks: 백그라운드 태스크 매니저.
        db: 비동기 DB 세션.

    Returns:
        상태 응답 딕셔너리 또는 에러 JSONResponse.
    """
    request_id = generate_request_id()
    bind_request_context(request_id)

    try:
        data = await request.json()
    except Exception:
        logger.warning("잘못된 JSON 요청 수신")
        return JSONResponse(status_code=400, content={"detail": "Invalid JSON body"})

    category = data.get("category")

    if category == "group_channel:message_send":
        sender = data.get("sender", {})
        user_id = sender.get("user_id", "Unknown")

        if user_id == "ai_agent_bot":
            return {"status": "ok"}

        payload = data.get("payload", {})
        user_message = payload.get("message", "")
        channel_url = data.get("channel", {}).get("channel_url")

        if not channel_url:
            logger.warning("channel_url이 없는 웹훅 수신", user_id=user_id)
            return {"status": "ok"}

        logger.info("사용자 메시지 수신", user_id=user_id, message_preview=user_message[:50])

        start_time = time.time()

        try:
            result = await asyncio.to_thread(get_ai_response, user_message, user_id)
            ai_answer = result["output"]
            token_usage = result["token_usage"]
            latency_ms = round((time.time() - start_time) * 1000)

            logger.info("AI 응답 생성 완료", user_id=user_id, latency_ms=latency_ms)

            await chat_log_repo.create_chat_log(
                db,
                log_id=request_id,
                user_id=user_id,
                question=user_message,
                answer=ai_answer,
                latency_ms=latency_ms,
                token_usage=token_usage,
            )

            background_tasks.add_task(send_message, channel_url, ai_answer)

        except Exception:
            logger.exception("메시지 처리 중 오류 발생", user_id=user_id)
            background_tasks.add_task(send_message, channel_url, _AI_ERROR_MESSAGE)

    return {"status": "ok"}


@router.put("/api/logs/{log_id}/feedback")
async def update_feedback(
    log_id: str,
    request: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """특정 대화 로그에 피드백을 업데이트합니다.

    Args:
        log_id: 로그 항목 UUID.
        request: 피드백 요청.
        db: 비동기 DB 세션.

    Returns:
        성공 응답 또는 에러.
    """
    log = await chat_log_repo.update_feedback(db, log_id=log_id, feedback=request.feedback)
    if log is None:
        logger.warning("로그를 찾을 수 없음", log_id=log_id)
        raise HTTPException(status_code=404, detail="Log not found")

    logger.info("피드백 추가", log_id=log_id, feedback=request.feedback)
    return {"status": "success", "log_id": log_id, "feedback": request.feedback}


@router.get("/api/logs")
async def get_chat_logs(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """최신 순으로 대화 로그를 반환합니다.

    Args:
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
                "timestamp": log.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
            for log in logs
        ],
        "total": len(logs),
    }
