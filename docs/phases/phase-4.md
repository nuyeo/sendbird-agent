# Phase 4: Observability 강화

## 목표

structlog 도입으로 구조화된 로깅을 구현하고, 기존 대시보드와 연동을 강화한다.

## 배경/맥락

현재 로깅이 기본 print/logging 수준이라 운영 시 디버깅이 어렵다. 구조화된 로그를 통해 요청 추적, 성능 측정, 할루시네이션 모니터링이 가능해진다.

## 요구사항

- [ ] `app/observability/logger.py` — structlog 설정
- [ ] `app/observability/metrics.py` — 메트릭 수집
- [ ] 기존 `/api/logs` 엔드포인트에 구조화된 필드 추가
- [ ] 요청별 request_id 추적

## 기술적 결정사항

- 로깅 라이브러리: `structlog` (JSON 포맷)
- 추가 필드: latency, token_usage, intent, hallucination_check

## structlog 설정 참고

```python
# app/observability/logger.py
import structlog
import uuid

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)

def get_logger():
    return structlog.get_logger()

def create_request_context() -> dict:
    return {"request_id": str(uuid.uuid4())}
```

## 대시보드 연동

기존 `/api/logs` 엔드포인트에 다음 필드를 추가한다:
- `latency` — 응답 생성 소요 시간
- `token_usage` — LLM 토큰 사용량
- `intent` — 분류된 사용자 의도
- `hallucination_check` — 할루시네이션 검증 결과

## 관련 파일

- `app/observability/logger.py` — 신규 생성
- `app/observability/metrics.py` — 신규 생성
- `app/api/webhook.py` — 로깅 적용
- `main.py` (또는 `app/main.py`) — 미들웨어 설정

## 완료 기준

- 모든 요청에 request_id가 부여됨
- 로그가 JSON 포맷으로 출력됨
- 대시보드에서 latency, token_usage 확인 가능
