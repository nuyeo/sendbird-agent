"""프롬프트 로더 단위 테스트."""

import pytest
from pydantic import ValidationError

from app.prompt.loader import PromptConfig, load_prompt


def test_load_prompt_cs_agent_v1() -> None:
    """cs_agent_v1 프롬프트가 정상적으로 로드되는지 확인."""
    config = load_prompt("cs_agent_v1")
    assert config.version == "1.0.0"
    assert config.description
    assert "Customer Support Agent" in config.system_prompt
    assert "Sendbird Store" in config.system_prompt


def test_load_prompt_has_required_guidelines() -> None:
    """프롬프트에 핵심 가이드라인이 포함되어 있는지 확인."""
    config = load_prompt("cs_agent_v1")
    assert "search_faq" in config.system_prompt
    assert "search_order_status" in config.system_prompt
    assert "Korean" in config.system_prompt


def test_load_prompt_not_found() -> None:
    """존재하지 않는 프롬프트 로드 시 FileNotFoundError 발생 확인."""
    with pytest.raises(FileNotFoundError):
        load_prompt("nonexistent_prompt")


def test_prompt_config_validation() -> None:
    """필수 필드 누락 시 ValidationError 발생 확인."""
    with pytest.raises(ValidationError):
        PromptConfig(version="1.0.0", description="test")  # system_prompt 누락
