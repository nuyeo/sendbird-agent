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


@patch("app.api.logs.chat_log_repo.list_chat_logs", new_callable=AsyncMock, return_value=[])
def test_get_chat_logs_empty(mock_list, client: TestClient) -> None:
    """빈 로그 조회 테스트."""
    response = client.get("/api/logs")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["logs"] == []


@patch("app.api.logs.chat_log_repo.update_feedback", new_callable=AsyncMock, return_value=None)
def test_feedback_not_found(mock_update, client: TestClient) -> None:
    """존재하지 않는 로그에 피드백 시 404 반환 테스트."""
    response = client.put(
        "/api/logs/00000000-0000-0000-0000-000000000000/feedback",
        json={"feedback": "up"},
    )
    assert response.status_code == 404


def test_feedback_rejects_invalid_value(client: TestClient) -> None:
    """허용되지 않은 피드백 값은 422로 거부되는지 테스트."""
    response = client.put(
        "/api/logs/00000000-0000-0000-0000-000000000000/feedback",
        json={"feedback": "maybe"},
    )
    assert response.status_code == 422


def test_webhook_endpoint_removed(client: TestClient) -> None:
    """Sendbird webhook 엔드포인트가 제거되었는지 확인."""
    response = client.post("/webhook", json={})
    assert response.status_code == 404
