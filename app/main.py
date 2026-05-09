"""FastAPI 애플리케이션 엔트리포인트."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from app.agent.rag import initialize_rag
from app.api.auth import router as auth_router
from app.api.chat_ws import router as chat_ws_router
from app.api.health import router as health_router
from app.api.logs import router as logs_router
from app.api.metrics import router as metrics_router
from app.api.rate_limit import limiter
from app.observability.logger import get_logger, setup_logging
from app.storage.database import engine
from app.storage.redis_client import close_redis, initialize_redis

setup_logging()
logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """애플리케이션 라이프사이클 관리."""
    logger.info("서버 시작 중...")

    # PostgreSQL 연결 확인
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("PostgreSQL 연결 확인 완료")
    except Exception:
        logger.exception("PostgreSQL 연결 실패")
        raise

    # Redis 연결 초기화 및 확인
    try:
        await initialize_redis()
        logger.info("Redis 연결 확인 완료")
    except Exception:
        logger.exception("Redis 연결 실패")
        raise

    # AI 에이전트 초기화
    try:
        initialize_rag()
        logger.info("AI 에이전트 초기화 완료")
    except Exception:
        logger.exception("AI 에이전트 초기화 실패")
        raise

    yield

    logger.info("서버 종료 중...")
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title="CS AI Agent",
    description="Real-time AI customer support agent",
    version="2.0.0",
    lifespan=lifespan,
)

# slowapi: limiter 인스턴스 등록 + 초과 응답 핸들러 + 미들웨어
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 배포 시에는 프론트엔드 도메인만 허용
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(metrics_router)
app.include_router(logs_router)
app.include_router(auth_router)
app.include_router(chat_ws_router)
