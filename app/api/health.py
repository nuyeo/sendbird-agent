"""헬스체크 엔드포인트."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.observability.logger import get_logger
from app.storage import redis_client
from app.storage.database import engine

logger = get_logger()

router = APIRouter()


@router.get("/")
def root() -> dict[str, str]:
    """컨테이너 liveness 용 정적 응답.

    의존성을 검사하지 않으므로 K8s/Cloud Run liveness probe로 사용해도
    일시적인 DB/Redis 지연으로 컨테이너가 재시작되지 않습니다.

    Returns:
        서버 상태와 버전 정보.
    """
    return {"status": "Server is running", "version": "2.0.0"}


@router.get("/health")
async def health(response: Response) -> dict[str, object]:
    """애플리케이션 readiness probe.

    PostgreSQL과 Redis 연결을 실제로 점검합니다. 둘 중 하나라도 실패하면
    503을 반환해 로드밸런서가 트래픽 라우팅을 보류하도록 합니다.

    Args:
        response: FastAPI 응답 객체. 실패 시 503 코드를 설정.

    Returns:
        각 의존성의 상태(`"ok"` 또는 `"unavailable"`)와 전체 상태.
    """
    postgres_status: Literal["ok", "unavailable"] = "ok"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        postgres_status = "unavailable"
        logger.exception("PostgreSQL 헬스체크 실패")

    redis_status: Literal["ok", "unavailable"] = (
        "ok" if await redis_client.ping() else "unavailable"
    )

    overall = "ok" if postgres_status == "ok" and redis_status == "ok" else "degraded"
    if overall != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": overall,
        "dependencies": {
            "postgres": postgres_status,
            "redis": redis_status,
        },
    }
