"""FastAPI 애플리케이션 엔트리포인트."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.rag import initialize_rag
from app.api.health import router as health_router
from app.api.webhook import router as webhook_router
from app.observability.logger import get_logger, setup_logging

setup_logging()
logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """애플리케이션 라이프사이클 관리."""
    logger.info("서버 시작 및 AI 에이전트 초기화 중...")
    try:
        initialize_rag()
        logger.info("AI 에이전트 초기화 완료")
    except Exception:
        logger.exception("AI 에이전트 초기화 실패")
        raise
    yield
    logger.info("서버 종료 중...")


app = FastAPI(
    title="Sendbird AI Agent",
    description="Real-time AI customer support agent",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 배포 시에는 프론트엔드 도메인만 허용
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(webhook_router)
