"""YAML 프롬프트 로더 모듈."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel

# 프로젝트 루트 디렉토리
_BASE_DIR = Path(__file__).resolve().parent.parent.parent


class PromptConfig(BaseModel):
    """프롬프트 설정 스키마."""

    version: str
    description: str
    system_prompt: str


def load_prompt(name: str) -> PromptConfig:
    """YAML 파일에서 프롬프트 설정을 로드합니다.

    Args:
        name: 프롬프트 파일명 (확장자 제외).

    Returns:
        검증된 프롬프트 설정 객체.

    Raises:
        FileNotFoundError: YAML 파일이 존재하지 않을 때.
        ValueError: YAML 파일이 비어있거나 올바른 매핑이 아닐 때.
        pydantic.ValidationError: YAML 내용이 스키마에 맞지 않을 때.
    """
    if "/" in name or "\\" in name or ".." in name:
        raise ValueError(f"유효하지 않은 프롬프트 이름: {name}")
    path = _BASE_DIR / "prompts" / f"{name}.yaml"
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"프롬프트 파일이 올바른 YAML 매핑이 아닙니다: {path}")
    return PromptConfig(**data)
