"""structlog 기반 구조화된 로깅 설정 모듈."""

from __future__ import annotations

import logging
import sys
import uuid

import structlog


def setup_logging() -> None:
    """structlog과 표준 logging을 JSON 출력으로 설정합니다."""
    # structlog 설정
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # 표준 logging도 structlog을 통해 출력되도록 설정
    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )


def get_logger(**kwargs: object) -> structlog.stdlib.BoundLogger:
    """structlog 로거 인스턴스를 반환합니다."""
    return structlog.get_logger(**kwargs)


def generate_request_id() -> str:
    """새로운 request_id를 생성합니다."""
    return str(uuid.uuid4())


def bind_request_context(request_id: str) -> None:
    """현재 컨텍스트에 request_id를 바인딩합니다."""
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
