"""Sendbird API 클라이언트 모듈."""

from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

SENDBIRD_API_URL = f"https://api-{settings.sendbird_app_id}.sendbird.com/v3"


async def send_message(channel_url: str, message: str) -> None:
    """Sendbird 채널에 메시지를 전송합니다.

    Args:
        channel_url: Sendbird 채널 URL.
        message: 전송할 메시지 내용.
    """
    headers = {
        "Content-Type": "application/json; charset=utf8",
        "Api-Token": settings.sendbird_api_token,
    }
    payload = {
        "message_type": "MESG",
        "user_id": "ai_agent_bot",
        "message": message,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = f"{SENDBIRD_API_URL}/group_channels/{channel_url}/messages"
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.debug(f"Message sent to channel {channel_url}")
    except httpx.HTTPError:
        logger.exception("Failed to send message to Sendbird")
