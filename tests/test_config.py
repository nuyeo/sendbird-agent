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
    assert settings.openai_api_key
    assert settings.jwt_secret_key


def test_llm_reliability_defaults() -> None:
    """LLM 호출 신뢰성 기본값이 합리적인 범위인지 확인합니다."""
    assert settings.llm_timeout_seconds > 0
    assert settings.llm_max_retries >= 0
