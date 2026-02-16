"""Webhook 핸들러 및 로그 관리 엔드포인트."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field

from app.agent.rag import get_ai_response
from app.sendbird.client import send_message

logger = logging.getLogger(__name__)

router = APIRouter()

# 인메모리 대화 로그 저장소
chat_logs: list[dict[str, Any]] = []


class FeedbackRequest(BaseModel):
    """피드백 요청 모델."""

    feedback: str = Field(..., description="Feedback type: 'up' or 'down'")


@router.post("/webhook")
async def sendbird_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """Sendbird 웹훅 이벤트를 처리합니다.

    Args:
        request: FastAPI 요청 객체.
        background_tasks: 백그라운드 태스크 매니저.

    Returns:
        상태 응답 딕셔너리.
    """
    data = await request.json()
    category = data.get("category")

    if category == "group_channel:message_send":
        sender = data.get("sender", {})
        user_id = sender.get("user_id", "Unknown")

        # 봇 자신의 메시지 무시
        if user_id == "ai_agent_bot":
            return {"status": "ok"}

        payload = data.get("payload", {})
        user_message = payload.get("message", "")
        channel_url = data.get("channel", {}).get("channel_url")

        logger.info(f"Received message from {user_id}: {user_message[:50]}...")

        # AI 응답 시간 측정
        start_time = time.time()

        try:
            ai_answer = get_ai_response(user_message, user_id=user_id)
            duration = round((time.time() - start_time) * 1000)

            logger.info(f"Generated response in {duration}ms")

            # 대화 로그 저장
            log_entry = {
                "id": str(uuid.uuid4()),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "user_id": user_id,
                "question": user_message,
                "answer": ai_answer,
                "duration": duration,
                "feedback": None,
            }
            chat_logs.insert(0, log_entry)

            # 비동기로 응답 전송
            background_tasks.add_task(send_message, channel_url, ai_answer)

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)

    return {"status": "ok"}


@router.put("/api/logs/{log_id}/feedback")
def update_feedback(log_id: str, request: FeedbackRequest) -> dict[str, Any]:
    """특정 대화 로그에 피드백을 업데이트합니다.

    Args:
        log_id: 로그 항목 UUID.
        request: 피드백 요청.

    Returns:
        성공 응답 또는 에러.
    """
    for log in chat_logs:
        if log["id"] == log_id:
            log["feedback"] = request.feedback
            logger.info(f"Feedback '{request.feedback}' added to log {log_id}")
            return {"status": "success", "log_id": log_id, "feedback": request.feedback}

    logger.warning(f"Log not found: {log_id}")
    raise HTTPException(status_code=404, detail="Log not found")


@router.get("/api/logs")
def get_chat_logs() -> dict[str, Any]:
    """모든 대화 로그를 반환합니다.

    Returns:
        로그 리스트와 총 개수를 담은 딕셔너리.
    """
    return {"logs": chat_logs, "total": len(chat_logs)}
