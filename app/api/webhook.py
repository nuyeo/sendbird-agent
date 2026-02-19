"""Webhook 핸들러 및 로그 관리 엔드포인트."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.agent.rag import get_ai_response
from app.observability.logger import bind_request_context, generate_request_id, get_logger
from app.sendbird.client import send_message

logger = get_logger()

router = APIRouter()

# 인메모리 대화 로그 저장소
MAX_CHAT_LOGS = 1000
chat_logs: list[dict[str, Any]] = []


class FeedbackRequest(BaseModel):
    """피드백 요청 모델."""

    feedback: str = Field(..., description="Feedback type: 'up' or 'down'")


@router.post("/webhook")
async def sendbird_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Response:
    """Sendbird 웹훅 이벤트를 처리합니다.

    Args:
        request: FastAPI 요청 객체.
        background_tasks: 백그라운드 태스크 매니저.

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

        # 봇 자신의 메시지 무시
        if user_id == "ai_agent_bot":
            return {"status": "ok"}

        payload = data.get("payload", {})
        user_message = payload.get("message", "")
        channel_url = data.get("channel", {}).get("channel_url")

        if not channel_url:
            logger.warning("channel_url이 없는 웹훅 수신", user_id=user_id)
            return {"status": "ok"}

        logger.info(
            "사용자 메시지 수신",
            user_id=user_id,
            message_preview=user_message[:50],
        )

        # AI 응답 시간 측정
        start_time = time.time()

        try:
            result = await asyncio.to_thread(get_ai_response, user_message, user_id)
            ai_answer = result["output"]
            token_usage = result["token_usage"]
            latency_ms = round((time.time() - start_time) * 1000)

            logger.info(
                "AI 응답 생성 완료",
                user_id=user_id,
                latency_ms=latency_ms,
                token_usage=token_usage,
            )

            # 대화 로그 저장
            log_entry = {
                "id": request_id,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "user_id": user_id,
                "question": user_message,
                "answer": ai_answer,
                "latency_ms": latency_ms,
                "token_usage": token_usage,
                "feedback": None,
            }
            chat_logs.insert(0, log_entry)
            if len(chat_logs) > MAX_CHAT_LOGS:
                chat_logs.pop()

            # 비동기로 응답 전송
            background_tasks.add_task(send_message, channel_url, ai_answer)

        except Exception:
            logger.exception("메시지 처리 중 오류 발생", user_id=user_id)
            error_msg = "죄송합니다. 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
            background_tasks.add_task(send_message, channel_url, error_msg)

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
            logger.info(
                "피드백 추가",
                log_id=log_id,
                feedback=request.feedback,
            )
            return {"status": "success", "log_id": log_id, "feedback": request.feedback}

    logger.warning("로그를 찾을 수 없음", log_id=log_id)
    raise HTTPException(status_code=404, detail="Log not found")


@router.get("/api/logs")
def get_chat_logs() -> dict[str, Any]:
    """모든 대화 로그를 반환합니다.

    Returns:
        로그 리스트와 총 개수를 담은 딕셔너리.
    """
    return {"logs": chat_logs, "total": len(chat_logs)}
