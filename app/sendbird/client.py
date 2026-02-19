"""Sendbird API 클라이언트 모듈."""

from __future__ import annotations

import httpx

from app.config import settings
from app.observability.logger import get_logger

logger = get_logger()

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
            logger.debug("Sendbird 메시지 전송 완료", channel_url=channel_url)
    except httpx.TimeoutException:
        logger.error("Sendbird 메시지 전송 타임아웃", channel_url=channel_url)
    except httpx.HTTPStatusError as e:
        logger.error(
            "Sendbird API 에러 응답",
            channel_url=channel_url,
            status_code=e.response.status_code,
        )
    except httpx.HTTPError:
        logger.exception("Sendbird 메시지 전송 실패", channel_url=channel_url)
