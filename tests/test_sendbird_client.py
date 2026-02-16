"""Sendbird 클라이언트 모듈 테스트."""

from app.sendbird.client import SENDBIRD_API_URL


def test_sendbird_api_url_format():
    """Sendbird API URL이 올바른 형식인지 확인."""
    assert SENDBIRD_API_URL.startswith("https://api-")
    assert SENDBIRD_API_URL.endswith("/v3")
