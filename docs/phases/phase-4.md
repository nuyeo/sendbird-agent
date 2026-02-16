# Phase 4: Observability 강화

## 목표

structlog 도입으로 구조화된 로깅을 구현하고, 기존 대시보드와 연동을 강화한다.

## 배경/맥락

현재 로깅이 기본 print/logging 수준이라 운영 시 디버깅이 어렵다. 구조화된 로그를 통해 요청 추적, 성능 측정, 할루시네이션 모니터링이 가능해진다.

## 요구사항

- [x] `app/observability/logger.py` — structlog 설정
- [x] 기존 코드의 logging을 structlog로 전환
- [x] 기존 `/api/logs` 엔드포인트에 구조화된 필드 추가 (latency, token_usage)
- [x] 요청별 request_id 추적
- [x] `get_ai_response`에서 token_usage 반환

### 검토 후 변경된 사항

- ~~`app/observability/metrics.py`~~: 별도 메트릭 모듈 불필요. structlog 필드로 충분
- ~~`intent` 필드~~: 의도 분류 로직이 없으므로 제거 (YAGNI)
- ~~`hallucination_check` 필드~~: Phase 3 eval에서 faithfulness 측정 중이므로 제거 (YAGNI)

## 기술적 결정사항

- 로깅 라이브러리: `structlog` (JSON 포맷)
- 추가 필드: latency, token_usage
- `get_ai_response` 반환을 `dict`로 확장하여 token_usage 포함

## structlog 설정 참고

```python
# app/observability/logger.py (간략화된 예시)
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
)

def get_logger(**kwargs) -> FilteringBoundLogger:
    return structlog.get_logger(**kwargs)

def bind_request_context(request_id: str) -> None:
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
```

## 대시보드 연동

기존 `/api/logs` 엔드포인트에 다음 필드를 추가한다:
- `latency` — 응답 생성 소요 시간 (ms)
- `token_usage` — LLM 토큰 사용량 (prompt + completion)

## 관련 파일

- `app/observability/logger.py` — 신규 생성
- `app/api/webhook.py` — structlog 적용, token_usage 추가
- `app/agent/rag.py` — `get_ai_response`에서 token_usage 반환
- `app/main.py` — structlog 초기화

## 완료 기준

- 모든 요청에 request_id가 부여됨
- 로그가 JSON 포맷으로 출력됨
- 대시보드에서 latency, token_usage 확인 가능
- `ruff check` 통과
- 기존 테스트 통과
