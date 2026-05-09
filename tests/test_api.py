"""API 엔드포인트 테스트."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

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


def test_root_returns_liveness(client: TestClient) -> None:
    """루트 엔드포인트는 의존성 검사 없이 정적 응답을 반환해야 합니다."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "Server is running"


def _patch_health_engine_ok() -> Any:
    """app.api.health.engine.connect()가 정상 동작하도록 mock합니다.

    engine.connect()는 sync 메서드이므로 MagicMock을 사용하고, 반환되는
    AsyncConnection 객체만 async context manager로 동작하도록 만듭니다.
    """
    mock_conn = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)
    mock_conn.execute = AsyncMock(return_value=None)
    mock_engine = MagicMock()
    mock_engine.connect.return_value = mock_conn
    return patch("app.api.health.engine", mock_engine)


def test_health_returns_dependency_status(client: TestClient) -> None:
    """/health는 PG/Redis 상태를 포함해 readiness를 보고해야 합니다."""
    with (
        _patch_health_engine_ok(),
        patch("app.api.health.redis_client.ping", new_callable=AsyncMock, return_value=True),
    ):
        response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["dependencies"] == {"postgres": "ok", "redis": "ok"}


def test_health_returns_503_when_redis_down(client: TestClient) -> None:
    """Redis ping이 실패하면 /health는 503과 함께 degraded 상태를 반환합니다."""
    with (
        _patch_health_engine_ok(),
        patch("app.api.health.redis_client.ping", new_callable=AsyncMock, return_value=False),
    ):
        response = client.get("/health")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded"
    assert data["dependencies"]["redis"] == "unavailable"
    assert data["dependencies"]["postgres"] == "ok"


def test_health_returns_503_when_redis_raises(client: TestClient) -> None:
    """Redis ping이 ConnectionError를 던져도 /health는 500이 아닌 503을 반환합니다."""
    with (
        _patch_health_engine_ok(),
        patch(
            "app.api.health.redis_client.ping",
            new_callable=AsyncMock,
            side_effect=ConnectionError("connection refused"),
        ),
    ):
        response = client.get("/health")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded"
    assert data["dependencies"]["redis"] == "unavailable"


def test_metrics_endpoint_exposes_prometheus_format(client: TestClient) -> None:
    """/metrics는 Prometheus exposition format으로 메트릭을 노출해야 합니다."""
    response = client.get("/metrics")
    assert response.status_code == 200
    body = response.text
    # WebSocket 활성 연결 게이지가 등록되어 있어야 함
    assert "ws_active_connections" in body
    # AI latency 히스토그램이 등록되어 있어야 함
    assert "ai_response_latency_seconds" in body


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
