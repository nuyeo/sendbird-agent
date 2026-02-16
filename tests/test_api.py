"""API 엔드포인트 테스트."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.webhook import chat_logs


# lifespan에서 RAG 초기화를 건너뛰기 위해 mock 처리
@patch("app.main.initialize_rag")
def test_health_check(mock_init):
    """헬스체크 엔드포인트 테스트."""
    from app.main import app

    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "Server is running"
    assert data["version"] == "2.0.0"


@patch("app.main.initialize_rag")
def test_get_chat_logs_empty(mock_init):
    """빈 로그 조회 테스트."""
    from app.main import app

    client = TestClient(app)
    chat_logs.clear()
    response = client.get("/api/logs")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["logs"] == []


@patch("app.main.initialize_rag")
def test_feedback_not_found(mock_init):
    """존재하지 않는 로그에 피드백 시 404 반환 테스트."""
    from app.main import app

    client = TestClient(app)
    chat_logs.clear()
    response = client.put(
        "/api/logs/nonexistent-id/feedback",
        json={"feedback": "up"},
    )
    assert response.status_code == 404


@patch("app.main.initialize_rag")
def test_webhook_ignores_bot_message(mock_init):
    """봇 자신의 메시지를 무시하는지 테스트."""
    from app.main import app

    client = TestClient(app)
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
