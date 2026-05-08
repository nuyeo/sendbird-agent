"""Prometheus 메트릭 노출 엔드포인트."""

from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

router = APIRouter()


@router.get("/metrics")
def metrics() -> Response:
    """Prometheus 스크레이프 엔드포인트.

    기본 레지스트리에 등록된 모든 메트릭을 텍스트 포맷으로 반환합니다.

    Returns:
        Prometheus exposition format 응답.
    """
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
