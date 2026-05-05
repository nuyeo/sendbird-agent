"""WebSocket 채팅 엔드포인트 테스트."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api.auth import issue_token


@pytest.fixture()
def client() -> Iterator[TestClient]:
    """DB/Redis/RAG를 mock 처리한 TestClient 픽스처."""
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


def test_websocket_rejects_invalid_token(client: TestClient) -> None:
    """잘못된 토큰은 4001 코드로 종료되어야 합니다."""
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/alice?token=invalid"):
            pass
    assert exc_info.value.code == 4001


def test_websocket_rejects_user_id_mismatch(client: TestClient) -> None:
    """토큰의 sub와 URL user_id가 다르면 4001로 종료되어야 합니다."""
    token, _ = issue_token("alice")
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/ws/bob?token={token}"):
            pass
    assert exc_info.value.code == 4001


def test_websocket_handles_user_message(client: TestClient) -> None:
    """user_message 수신 시 typing → ai_response 순서로 응답해야 합니다."""
    token, _ = issue_token("alice")

    with (
        patch(
            "app.api.chat_ws.get_ai_response",
            return_value={"output": "안녕하세요, Alice 님", "token_usage": None},
        ),
        patch("app.api.chat_ws._persist_chat_log", new_callable=AsyncMock),
    ):
        with client.websocket_connect(f"/ws/alice?token={token}") as ws:
            ws.send_json({"type": "user_message", "message": "안녕"})

            typing = ws.receive_json()
            assert typing == {"type": "typing"}

            response = ws.receive_json()
            assert response["type"] == "ai_response"
            assert response["message"] == "안녕하세요, Alice 님"


def test_websocket_persists_chat_log(client: TestClient) -> None:
    """user_message 처리 시 chat_log가 영속화되어야 합니다."""
    token, _ = issue_token("alice")
    token_usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}

    with (
        patch(
            "app.api.chat_ws.get_ai_response",
            return_value={"output": "응답", "token_usage": token_usage},
        ),
        patch("app.api.chat_ws._persist_chat_log", new_callable=AsyncMock) as mock_persist,
    ):
        with client.websocket_connect(f"/ws/alice?token={token}") as ws:
            ws.send_json({"type": "user_message", "message": "주문 조회"})
            ws.receive_json()  # typing
            ws.receive_json()  # ai_response

    mock_persist.assert_awaited_once()
    kwargs = mock_persist.await_args.kwargs
    assert kwargs["user_id"] == "alice"
    assert kwargs["question"] == "주문 조회"
    assert kwargs["answer"] == "응답"
    assert kwargs["token_usage"] == token_usage
    assert isinstance(kwargs["latency_ms"], int)
    assert kwargs["latency_ms"] >= 0
    assert isinstance(kwargs["log_id"], str) and kwargs["log_id"]


def test_websocket_response_survives_persist_failure(client: TestClient) -> None:
    """chat_log 저장이 실패해도 사용자에게 응답을 전달해야 합니다."""
    token, _ = issue_token("alice")

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "app.api.chat_ws.get_ai_response",
            return_value={"output": "응답", "token_usage": None},
        ),
        patch("app.api.chat_ws.AsyncSessionLocal", return_value=mock_session),
        patch(
            "app.api.chat_ws.chat_log_repo.create_chat_log",
            new_callable=AsyncMock,
            side_effect=RuntimeError("DB down"),
        ),
    ):
        with client.websocket_connect(f"/ws/alice?token={token}") as ws:
            ws.send_json({"type": "user_message", "message": "안녕"})
            ws.receive_json()  # typing
            response = ws.receive_json()
            assert response["type"] == "ai_response"
            assert response["message"] == "응답"


def test_websocket_rejects_empty_message(client: TestClient) -> None:
    """빈 메시지에는 error 응답을 보내고 연결을 유지해야 합니다."""
    token, _ = issue_token("alice")

    with client.websocket_connect(f"/ws/alice?token={token}") as ws:
        ws.send_json({"type": "user_message", "message": "   "})
        response = ws.receive_json()
        assert response == {"type": "error", "message": "Empty message"}


def test_websocket_rejects_unknown_message_type(client: TestClient) -> None:
    """지원하지 않는 type은 error 응답으로 회신해야 합니다."""
    token, _ = issue_token("alice")

    with client.websocket_connect(f"/ws/alice?token={token}") as ws:
        ws.send_json({"type": "ping"})
        response = ws.receive_json()
        assert response == {"type": "error", "message": "Unsupported message type"}


def test_websocket_rejects_malformed_json(client: TestClient) -> None:
    """잘못된 JSON 페이로드는 4002 코드로 종료되어야 합니다."""
    token, _ = issue_token("alice")

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/ws/alice?token={token}") as ws:
            ws.send_text("{invalid-json")
            ws.receive_text()
    assert exc_info.value.code == 4002
