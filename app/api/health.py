"""헬스체크 엔드포인트."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def health_check() -> dict[str, str]:
    """서버 상태 확인 엔드포인트."""
    return {"status": "Server is running", "version": "2.0.0"}
