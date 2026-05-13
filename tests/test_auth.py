"""JWT 발급/검증 및 dev-token 엔드포인트 테스트."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api.auth import issue_token, verify_token
from app.config import settings


def test_issue_and_verify_round_trip() -> None:
    """발급된 토큰은 검증 시 동일한 user_id를 반환해야 합니다."""
    token, expires_in = issue_token("user_42")
    assert isinstance(token, str) and token
    assert expires_in == settings.jwt_expire_minutes * 60
    assert verify_token(token) == "user_42"


def test_verify_token_rejects_invalid_signature() -> None:
    """다른 키로 서명된 토큰은 거부되어야 합니다."""
    forged = jwt.encode(
        {"sub": "user_42", "exp": int((datetime.now(UTC) + timedelta(minutes=5)).timestamp())},
        f"{settings.jwt_secret_key}_invalid_signature",
        algorithm="HS256",
    )
    with pytest.raises(ValueError):
        verify_token(forged)


def test_verify_token_rejects_expired_token() -> None:
    """이미 만료된 토큰은 거부되어야 합니다."""
    past = datetime.now(UTC) - timedelta(minutes=5)
    expired = jwt.encode(
        {"sub": "user_42", "exp": int(past.timestamp())},
        settings.jwt_secret_key,
        algorithm="HS256",
    )
    with pytest.raises(ValueError):
        verify_token(expired)


def test_verify_token_rejects_missing_sub() -> None:
    """sub 클레임이 없는 토큰은 거부되어야 합니다."""
    future = datetime.now(UTC) + timedelta(minutes=5)
    no_sub = jwt.encode(
        {"foo": "bar", "exp": int(future.timestamp())},
        settings.jwt_secret_key,
        algorithm="HS256",
    )
    with pytest.raises(ValueError):
        verify_token(no_sub)


def test_verify_token_rejects_missing_exp() -> None:
    """exp 클레임이 없는 토큰은 거부되어야 합니다."""
    no_exp = jwt.encode({"sub": "user_42"}, settings.jwt_secret_key, algorithm="HS256")
    with pytest.raises(ValueError):
        verify_token(no_exp)


@pytest.fixture()
def client() -> Iterator[TestClient]:
    """DB/Redis/RAG를 mock 처리한 TestClient 픽스처."""
    with (
        patch("app.main.initialize_rag", new_callable=AsyncMock),
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


def test_dev_token_endpoint_in_debug_mode(client: TestClient) -> None:
    """debug=True일 때 dev-token 엔드포인트가 토큰을 발급해야 합니다."""
    with patch.object(settings, "debug", True):
        response = client.post("/api/auth/dev-token", json={"user_id": "alice"})
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body and body["access_token"]
    assert body["expires_in"] == settings.jwt_expire_minutes * 60
    assert verify_token(body["access_token"]) == "alice"


def test_dev_token_endpoint_returns_404_in_production(client: TestClient) -> None:
    """debug=False일 때 dev-token 엔드포인트는 404를 반환해야 합니다."""
    with patch.object(settings, "debug", False):
        response = client.post("/api/auth/dev-token", json={"user_id": "alice"})
    assert response.status_code == 404


def test_dev_token_endpoint_rejects_empty_user_id(client: TestClient) -> None:
    """빈 user_id는 422로 거부되어야 합니다."""
    with patch.object(settings, "debug", True):
        response = client.post("/api/auth/dev-token", json={"user_id": ""})
    assert response.status_code == 422
