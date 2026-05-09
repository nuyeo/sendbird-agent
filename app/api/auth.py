"""JWT 발급/검증 및 dev용 토큰 엔드포인트.

NOTE: 이 모듈은 의도적으로 `from __future__ import annotations`를 사용하지
않는다. `@limiter.limit` 데코레이터가 함수를 래핑하면서 래퍼의 `__globals__`이
`slowapi.extension` 모듈을 가리키게 되어, FastAPI가 문자열 어노테이션을
해석할 때 프로젝트 정의 타입(예: `DevTokenRequest`)을 찾지 못해 본문을 query로
오인하는 422 오류가 발생한다. 실제 클래스 객체가 어노테이션에 그대로 들어가도록
future annotations를 끄면 회피된다.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.rate_limit import limiter
from app.config import settings

_JWT_ALGORITHM = "HS256"

router = APIRouter()


class DevTokenRequest(BaseModel):
    """dev 토큰 발급 요청 모델."""

    user_id: str = Field(..., min_length=1, max_length=100)


class DevTokenResponse(BaseModel):
    """dev 토큰 발급 응답 모델."""

    access_token: str
    expires_in: int


def issue_token(user_id: str) -> tuple[str, int]:
    """user_id를 sub 클레임으로 가지는 JWT를 발급합니다.

    Args:
        user_id: 토큰에 묶을 사용자 식별자.

    Returns:
        (jwt_string, expires_in_seconds) 튜플.
    """
    expire_seconds = settings.jwt_expire_minutes * 60
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expire_seconds)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=_JWT_ALGORITHM)
    return token, expire_seconds


def verify_token(token: str) -> str:
    """JWT를 검증하고 sub(user_id)를 반환합니다.

    Args:
        token: 검증할 JWT 문자열.

    Returns:
        토큰의 sub 클레임(user_id).

    Raises:
        ValueError: 서명/만료 검증 실패 또는 sub 클레임 누락 시.
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[_JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise ValueError(f"Invalid JWT: {exc}") from exc

    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise ValueError("JWT에 sub(user_id) 클레임이 없습니다")
    return user_id


@router.post("/api/auth/dev-token", response_model=DevTokenResponse)
@limiter.limit(settings.rate_limit_dev_token)
def issue_dev_token(request: Request, body: DevTokenRequest) -> DevTokenResponse:
    """dev 환경에서 임의 user_id로 JWT를 발급합니다.

    debug=True일 때만 활성화되는 개발용 엔드포인트입니다. 프로덕션에서는
    대시보드 로그인 흐름이 발급을 담당하도록 별도 PR에서 교체합니다.

    slowapi가 첫 인자에서 starlette Request를 추출하므로 시그니처에 명시한다.
    실제 본문은 `body` 인자로 받는다.

    Args:
        request: starlette 요청 객체 (slowapi 의존성).
        body: user_id를 담은 요청 본문.

    Returns:
        access_token과 만료 시간(초).

    Raises:
        HTTPException: debug=False 환경에서 호출 시 404.
    """
    if not settings.debug:
        raise HTTPException(status_code=404, detail="Not Found")

    token, expires_in = issue_token(body.user_id)
    return DevTokenResponse(access_token=token, expires_in=expires_in)
