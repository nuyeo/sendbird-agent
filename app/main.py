"""FastAPI 애플리케이션 엔트리포인트."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.rag import initialize_rag
from app.api.health import router as health_router
from app.api.webhook import router as webhook_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """애플리케이션 라이프사이클 관리."""
    logger.info("Starting server and initializing AI agent...")
    try:
        initialize_rag()
        logger.info("AI agent initialized successfully")
    except Exception:
        logger.exception("Failed to initialize AI agent")
        raise
    yield
    logger.info("Shutting down server...")


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
