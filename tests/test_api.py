"""API 엔드포인트 테스트."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    """DB, Redis, RAG를 mock 처리한 TestClient 픽스처."""
    with (
        patch("app.main.initialize_rag"),
        patch("app.main.initialize_redis", new_callable=AsyncMock),
        patch("app.main.close_redis", new_callable=AsyncMock),
        patch("app.main.engine") as mock_engine,
    ):
        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_conn.execute = AsyncMock(return_value=None)
        mock_engine.connect.return_value = mock_conn
        mock_engine.dispose = AsyncMock()

        from app.main import app

        with TestClient(app) as c:
            yield c


def test_health_check(client: TestClient) -> None:
    """헬스체크 엔드포인트 테스트."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "Server is running"


@patch("app.api.webhook.chat_log_repo.list_chat_logs", new_callable=AsyncMock, return_value=[])
def test_get_chat_logs_empty(mock_list, client: TestClient) -> None:
    """빈 로그 조회 테스트."""
    response = client.get("/api/logs")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["logs"] == []


@patch("app.api.webhook.chat_log_repo.update_feedback", new_callable=AsyncMock, return_value=None)
def test_feedback_not_found(mock_update, client: TestClient) -> None:
    """존재하지 않는 로그에 피드백 시 404 반환 테스트."""
    response = client.put(
        "/api/logs/00000000-0000-0000-0000-000000000000/feedback",
        json={"feedback": "up"},
    )
    assert response.status_code == 404


def test_webhook_ignores_bot_message(client: TestClient) -> None:
    """봇 자신의 메시지를 무시하는지 테스트."""
    response = client.post(
        "/webhook",
        json={
            "category": "group_channel:message_send",
            "sender": {"user_id": "ai_agent_bot"},
            "payload": {"message": "test"},
            "channel": {"channel_url": "test_channel"},
        },
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
