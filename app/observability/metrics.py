"""Prometheus 메트릭 정의 및 수집 헬퍼.

Phase D(토큰 비용 최적화)의 기저선 측정을 위해 latency, token usage,
WebSocket 동시 연결 수를 노출합니다. prometheus-client의 기본 레지스트리를
그대로 사용하므로 `/metrics` 엔드포인트에서 generate_latest()로 노출됩니다.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# 응답 latency 분포 (초). bucket은 LLM 응답 특성에 맞춰 0.5~30s 범위.
ai_response_latency_seconds = Histogram(
    "ai_response_latency_seconds",
    "LLM 응답 생성 소요 시간(초)",
    buckets=(0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 13.0, 21.0, 30.0),
)

# OpenAI usage 카운터. token type별로 라벨 분리해 비용 분석 가능.
ai_token_usage_total = Counter(
    "ai_token_usage_total",
    "누적 OpenAI 토큰 사용량",
    labelnames=("type",),
)

# 현재 활성 WebSocket 연결 수 (단일 워커 기준).
ws_active_connections = Gauge(
    "ws_active_connections",
    "현재 워커 프로세스의 활성 WebSocket 연결 수",
)

# AI 응답 결과별 카운터 (성공/오류 분리).
ai_response_total = Counter(
    "ai_response_total",
    "AI 응답 처리 결과",
    labelnames=("status",),
)


def record_token_usage(token_usage: dict[str, int] | None) -> None:
    """OpenAI usage 딕셔너리에서 토큰 사용량을 카운터에 누적합니다.

    Args:
        token_usage: `{"prompt_tokens": int, "completion_tokens": int, ...}`
            형태의 딕셔너리. None이면 아무것도 수행하지 않습니다.
    """
    if not token_usage:
        return
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = token_usage.get(key)
        if isinstance(value, int) and value > 0:
            ai_token_usage_total.labels(type=key).inc(value)
