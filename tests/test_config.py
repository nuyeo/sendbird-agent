"""설정 모듈 테스트."""

from app.config import settings


def test_settings_loads() -> None:
    """settings 객체가 정상적으로 로드되는지 확인."""
    assert settings.llm_model == "gpt-4o-mini"
    assert settings.llm_temperature == 0.0
    assert settings.chunk_size == 500
    assert settings.chunk_overlap == 0


def test_settings_has_required_fields() -> None:
    """필수 환경변수가 설정되어 있는지 확인."""
    assert settings.sendbird_app_id
    assert settings.sendbird_api_token
    assert settings.openai_api_key
