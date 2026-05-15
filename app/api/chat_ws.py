"""WebSocket 채팅 엔드포인트 및 연결 관리자."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.agent.cache import get_cached_response, set_cached_response
from app.agent.rag import get_ai_response
from app.api.auth import verify_token
from app.api.middleware import is_within_budget, record_token_spend
from app.config import settings
from app.observability.logger import bind_request_context, generate_request_id, get_logger
from app.observability.metrics import (
    ai_response_latency_seconds,
    ai_response_total,
    record_token_usage,
    semantic_cache_hits_total,
    token_budget_exceeded_total,
    ws_active_connections,
)
from app.storage.database import AsyncSessionLocal
from app.storage.repositories import chat_log_repo

logger = get_logger()

router = APIRouter()

_WS_CLOSE_UNAUTHORIZED = 4001
_WS_CLOSE_INVALID_PAYLOAD = 4002

_llm_semaphore: asyncio.Semaphore | None = None


def _get_llm_semaphore() -> asyncio.Semaphore:
    """동시 LLM 호출을 제한하는 세마포어를 lazy 초기화합니다.

    asyncio.Semaphore는 생성 시점의 이벤트 루프에 바인딩되므로,
    설정 임포트 시점이 아닌 첫 사용 시점에 만들어야 합니다.
    """
    global _llm_semaphore
    if _llm_semaphore is None:
        _llm_semaphore = asyncio.Semaphore(settings.max_concurrent_llm)
    return _llm_semaphore


class WebSocketManager:
    """user_id별 활성 WebSocket 연결을 추적합니다.

    동일 user_id가 여러 탭/디바이스에서 접속할 수 있으므로 세트로 관리합니다.
    """

    def __init__(self) -> None:
        """연결 매핑을 초기화합니다."""
        self._connections: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        """클라이언트 연결을 수락하고 추적 목록에 추가합니다.

        Args:
            user_id: JWT 검증을 통과한 사용자 식별자.
            websocket: 수락할 WebSocket 객체.
        """
        await websocket.accept()
        async with self._lock:
            self._connections.setdefault(user_id, set()).add(websocket)

    async def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        """추적 목록에서 연결을 제거합니다.

        Args:
            user_id: 연결을 등록할 때 사용한 사용자 식별자.
            websocket: 제거할 WebSocket 객체.
        """
        async with self._lock:
            sessions = self._connections.get(user_id)
            if sessions is None:
                return
            sessions.discard(websocket)
            if not sessions:
                del self._connections[user_id]

    async def send_personal(self, user_id: str, message: dict[str, Any]) -> None:
        """동일 user_id의 모든 활성 연결로 메시지를 전송합니다.

        Args:
            user_id: 대상 사용자 식별자.
            message: 전송할 JSON 직렬화 가능한 페이로드.
        """
        async with self._lock:
            sessions = list(self._connections.get(user_id, set()))
        for ws in sessions:
            try:
                await ws.send_json(message)
            except Exception:
                logger.exception("WebSocket 전송 실패", user_id=user_id)

    def active_user_count(self) -> int:
        """현재 추적 중인 고유 사용자 수를 반환합니다."""
        return len(self._connections)


manager = WebSocketManager()


async def _handle_user_message(session_id: str, message: str) -> dict[str, Any]:
    """LLM 호출을 세마포어로 제한한 뒤 응답을 반환합니다.

    Args:
        session_id: LLM 대화 메모리 키 (연결당 unique).
        message: 사용자 메시지.

    Returns:
        get_ai_response가 반환하는 {"output", "token_usage"} 딕셔너리.
    """
    semaphore = _get_llm_semaphore()
    async with semaphore:
        return await get_ai_response(message, session_id)


async def _persist_chat_log(
    *,
    log_id: str,
    user_id: str,
    question: str,
    answer: str,
    latency_ms: int,
    token_usage: dict[str, Any] | None,
) -> None:
    """대화 로그를 PostgreSQL에 저장합니다.

    저장 실패는 사용자 응답을 막지 않도록 예외를 삼킵니다.

    Args:
        log_id: 메시지 단위 요청 ID(UUID 문자열).
        user_id: 사용자 식별자.
        question: 사용자 질문.
        answer: AI 응답.
        latency_ms: 응답 생성 소요 시간(ms).
        token_usage: OpenAI usage 딕셔너리.
    """
    try:
        async with AsyncSessionLocal() as db:
            await chat_log_repo.create_chat_log(
                db,
                log_id=log_id,
                user_id=user_id,
                question=question,
                answer=answer,
                latency_ms=latency_ms,
                token_usage=token_usage,
            )
    except Exception:
        logger.exception("chat_log 저장 실패", user_id=user_id, log_id=log_id)


@router.websocket("/ws/{user_id}")
async def chat_websocket(
    websocket: WebSocket,
    user_id: str,
    token: str = Query(..., description="JWT access token"),
) -> None:
    """사용자별 채팅 WebSocket 엔드포인트.

    JWT 검증 통과 후 user_message 타입 메시지를 받아 AI 응답을 1회 전송합니다.
    동시 LLM 호출은 settings.max_concurrent_llm 세마포어로 제한되며,
    각 메시지는 chat_logs 테이블에 영속화됩니다.

    Args:
        websocket: 클라이언트 WebSocket 연결.
        user_id: URL 경로의 사용자 식별자.
        token: JWT access token (query param).
    """
    connection_id = generate_request_id()
    bind_request_context(connection_id)

    try:
        token_user_id = verify_token(token)
    except ValueError as exc:
        logger.warning("WebSocket 인증 실패", user_id=user_id, reason=str(exc))
        await websocket.close(code=_WS_CLOSE_UNAUTHORIZED)
        return

    if token_user_id != user_id:
        logger.warning(
            "WebSocket user_id 불일치",
            url_user_id=user_id,
            token_user_id=token_user_id,
        )
        await websocket.close(code=_WS_CLOSE_UNAUTHORIZED)
        return

    await manager.connect(user_id, websocket)
    ws_active_connections.inc()
    logger.info("WebSocket 연결 수립", user_id=user_id)

    try:
        while True:
            try:
                payload = await websocket.receive_json()
            except WebSocketDisconnect:
                raise
            except Exception:
                logger.warning("잘못된 JSON 메시지", user_id=user_id)
                await websocket.close(code=_WS_CLOSE_INVALID_PAYLOAD)
                return

            message_type = payload.get("type")
            if message_type != "user_message":
                await websocket.send_json({"type": "error", "message": "Unsupported message type"})
                continue

            user_message = payload.get("message", "")
            if not isinstance(user_message, str) or not user_message.strip():
                await websocket.send_json({"type": "error", "message": "Empty message"})
                continue

            # 메시지 단위로 request_id를 새로 발급해 chat_logs와 로그 컨텍스트를 연결
            message_id = generate_request_id()
            bind_request_context(message_id)

            # ── 1. 시맨틱 캐시 확인 (LLM 호출 우회) ────────────────────────
            cached_output = await get_cached_response(user_message)
            if cached_output is not None:
                semantic_cache_hits_total.inc()
                ai_response_total.labels(status="success").inc()
                logger.info("캐시 히트 응답 반환", user_id=user_id)
                await websocket.send_json({"type": "ai_response", "message": cached_output})
                continue

            # ── 2. 일일 토큰 예산 확인 ──────────────────────────────────────
            if not await is_within_budget(user_id):
                token_budget_exceeded_total.inc()
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": (
                            "오늘 사용 가능한 메시지 한도를 초과했습니다. 내일 다시 이용해 주세요."
                        ),
                    }
                )
                continue

            # ── 3. LLM 호출 ─────────────────────────────────────────────────
            await websocket.send_json({"type": "typing"})

            start_time = time.time()
            with ai_response_latency_seconds.time():
                result = await _handle_user_message(connection_id, user_message)
            latency_ms = round((time.time() - start_time) * 1000)

            token_usage = result.get("token_usage")
            record_token_usage(token_usage)
            # get_ai_response가 LLM 예외를 흡수하고 fallback 메시지를 돌려주므로,
            # 외부 except 블록만으로는 실패를 감지할 수 없다. error 플래그로 분기한다.
            is_error = result.get("error", False)
            status_label = "error" if is_error else "success"
            ai_response_total.labels(status=status_label).inc()

            logger.info("AI 응답 생성 완료", user_id=user_id, latency_ms=latency_ms)

            # ── 4. 성공 응답을 캐시에 저장 + 토큰 예산 기록 ────────────────
            if not is_error:
                await set_cached_response(user_message, result["output"])
                if token_usage:
                    await record_token_spend(user_id, token_usage.get("total_tokens", 0))

            await _persist_chat_log(
                log_id=message_id,
                user_id=user_id,
                question=user_message,
                answer=result["output"],
                latency_ms=latency_ms,
                token_usage=token_usage,
            )

            await websocket.send_json({"type": "ai_response", "message": result["output"]})

    except WebSocketDisconnect:
        logger.info("WebSocket 연결 종료", user_id=user_id)
    except Exception:
        ai_response_total.labels(status="error").inc()
        logger.exception("WebSocket 처리 중 오류", user_id=user_id)
    finally:
        await manager.disconnect(user_id, websocket)
        ws_active_connections.dec()
