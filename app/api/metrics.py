"""Prometheus 메트릭 노출 엔드포인트."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.config import settings

router = APIRouter()

_BEARER_PREFIX = "Bearer "


@router.get("/metrics")
def metrics(request: Request) -> Response:
    """Prometheus 스크레이프 엔드포인트.

    `settings.metrics_bearer_token`이 설정된 경우 `Authorization: Bearer <token>`
    헤더를 요구한다. 비어 있으면 가드는 비활성화되며, 운영 환경에서는 ingress/LB
    레벨에서 접근을 제한하거나 토큰을 지정해 telemetry 노출을 차단한다.

    Args:
        request: FastAPI 요청 객체. 인증 헤더 검사용.

    Returns:
        Prometheus exposition format 응답.

    Raises:
        HTTPException: 토큰이 설정되어 있으나 헤더가 없거나 일치하지 않을 때 401.
    """
    expected = settings.metrics_bearer_token
    if expected:
        auth = request.headers.get("Authorization", "")
        if not auth.startswith(_BEARER_PREFIX) or not hmac.compare_digest(
            auth[len(_BEARER_PREFIX) :], expected
        ):
            raise HTTPException(status_code=401, detail="Unauthorized")

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
