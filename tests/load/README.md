# 부하 테스트 (k6)

Phase D before/after 비교용 베이스라인 측정. WebSocket 채팅 엔드포인트(`/ws/{user_id}`)에 동시 50명을 3분간 유지하면서 메시지 1회당 latency, 성공률, 핸드셰이크 성공률을 기록합니다.

## 사전 준비

1. 서버 기동 (`docker compose up` 또는 로컬 uvicorn)
2. `.env`에 `JWT_SECRET_KEY` 설정 (서버와 토큰 발급기가 같은 키 사용해야 함)
3. k6 설치 확인: `k6 version`

## 실행 순서

```powershell
# 1. 토큰 100개 미리 발급
python tests/load/seed_tokens.py --count 100

# 2. k6 실행 (기본: ws://localhost:8001)
k6 run tests/load/baseline.js

# 결과를 JSON으로 저장하고 싶으면
k6 run --summary-export tests/load/result-summary.json tests/load/baseline.js
```

## 시나리오

- ramp-up 30초 → 50 VU 유지 3분 → ramp-down 30초
- 각 VU는 사전 발급된 토큰을 회전 사용 (`__VU % token_count`)
- 메시지 간 1초 sleep (실유저 페이싱 흉내)

## 수집 메트릭

| 메트릭 | 의미 |
|---|---|
| `ai_message_latency_ms` | user_message 송신 → ai_response 수신까지 (ms) |
| `ai_message_success` | 정상 ai_response 수신 비율 |
| `ai_message_errors` | error 응답/타임아웃 누계 |
| `ws_handshake_ok` | WebSocket 핸드셰이크 101 응답 비율 |
| `ws_session_duration` (built-in) | 연결 수명 |
| `vus`, `iterations` (built-in) | 동시 사용자 수, 총 반복 횟수 |

## 결과 해석 가이드

- **p95 latency**: 사용자가 체감하는 응답 시간의 상한. Phase D Prompt Caching 적용 후 가장 큰 변화가 기대됨.
- **`ai_message_success` < 1.0**: LLM rate limit / 타임아웃 발생. semaphore 설정(`max_concurrent_llm`)과 OpenAI TPM 한도 확인.
- **`ws_handshake_ok` < 1.0**: 인증 실패 또는 서버 수용량 부족. JWT 만료(`jwt_expire_minutes`)와 워커 수 점검.

## 비용 주의

50 VU × 3분 × 메시지당 1초 페이싱 ≈ **약 9,000 메시지**. gpt-4o-mini 기준 메시지당 평균 500~1500 토큰 추정 시 USD $0.5~2 정도 소비 예상.

## 환경변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `BASE_WS` | `ws://localhost:8001` | 대상 서버 (스테이징/프로덕션 측정 시 변경) |
| `RESPONSE_TIMEOUT_MS` | `30000` | 단일 메시지 응답 대기 타임아웃 |
