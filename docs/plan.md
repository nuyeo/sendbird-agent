# CS 에이전트 프로덕션 스케일업 아키텍처 플랜

## Context

현재 v2까지 리팩토링된 FastAPI + LangChain 기반 CS 챗봇을 전국 서비스 규모(동시 수십~수백 명)로 확장하고, Sendbird UI 의존성을 제거해 자체 채팅 UI를 구축한다.

**현재 코드의 주요 병목 (스케일 시 즉각 터지는 것들)**

| 문제 | 코드 위치 | 증상 |
|---|---|---|
| 인메모리 세션 저장 | `app/agent/rag.py:34` `chat_history_store: dict` | 재시작 시 히스토리 전소, 다중 워커 간 불공유 |
| 인메모리 로그 저장 | `app/api/webhook.py:27` `chat_logs: list` | 최대 1000개 후 유실, 다중 워커 간 불공유 |
| 동기 LLM 호출 | `webhook.py:87` `asyncio.to_thread(get_ai_response, ...)` | 스레드 풀 한계 도달 시 큐잉 없이 즉시 503 |
| Sendbird 종속 UI | `sendbird/client.py` + 외부 Sendbird SDK | 커스터마이징 불가, 비용 선형 증가 |
| 로컬 ChromaDB | `agent/rag.py:57` persist_directory | 다중 인스턴스 공유 불가 |
| Mock DB | `agent/tools.py:9` MOCK_DB | 서비스 재시작 시 상태 초기화, 실제 DB 없음 |

---

## 아키텍처 의사결정 (핵심 trade-off)

### Decision 1: 채팅 UI 방식

```
Option A: Next.js 확장 (기존 dashboard/ 연장)
  장점: 동일 스택, 공통 auth/스타일, 배포 단순, 완전한 제어
  단점: 채팅 컴포넌트(메시지 버블, 타이핑 인디케이터, 파일 업로드) 직접 구현

Option B: Chatwoot (오픈소스 CS 플랫폼, Ruby on Rails)
  장점: 상담원 라우팅, 티켓 시스템, 멀티채널 내장
  단점: Rails 서버 별도 운영, LLM 통합이 webhook 방식으로 복잡, 중소형 규모엔 과도

추천: Option A (Next.js 확장)
  중소형 규모에서 Chatwoot의 운영 복잡도 > 이점
  기존 Next.js 16 + React 19 + Tailwind 4 스택 그대로 재사용
```

### Decision 2: 실시간 통신 방식

```
Option A: WebSocket (양방향)
  장점: 낮은 지연, 자연스러운 채팅 UX, 스트리밍 응답 지원
  단점: 수평 확장 시 Redis pub/sub 필요, 연결 상태 관리 복잡
  
Option B: SSE (Server-Sent Events, 서버→클라이언트 단방향)
  장점: 단순, HTTP 위에서 작동, 프록시 통과 쉬움
  단점: 클라이언트→서버는 별도 REST API 필요, 양방향 UX가 어색

추천: WebSocket
  채팅 UX 특성상 양방향이 자연스러움
  중소형 규모(수백 동접)에서 uvicorn + Redis pub/sub으로 충분히 관리 가능
```

### Decision 3: 세션/상태 저장소

```
Option A: Redis
  장점: O(1) 접근, TTL 기반 자동 만료, pub/sub으로 워커 간 브로드캐스트, 검증된 채팅 히스토리 패턴
  단점: 추가 인프라, 영속성 설정 주의 필요

Option B: PostgreSQL만 사용
  장점: 단일 스택, 트랜잭션 안전
  단점: 채팅 히스토리 조회가 DB I/O, 실시간 pub/sub 별도 구현 어려움

추천: Redis (세션/pub/sub) + PostgreSQL (영구 로그/비즈니스 데이터)
  Redis는 채팅 히스토리 + WebSocket 브로드캐스트
  PostgreSQL은 chat_logs, orders, feedback 영구 저장
```

### Decision 4: 벡터 DB

```
Option A: ChromaDB 서버 모드
  장점: 현재 코드 변경 최소, HTTP API로 다중 인스턴스 공유
  단점: 별도 Chroma 서버 운영

Option B: pgvector (PostgreSQL 익스텐션)
  장점: PostgreSQL 하나로 통합, 운영 단순화, SQL JOIN 가능
  단점: 기존 LangChain Chroma 코드 교체 필요

추천: Docker Compose 초기에는 ChromaDB 서버 모드 유지 (변경 최소화)
  트래픽이 늘면 pgvector로 마이그레이션 고려
```

### Decision 5: LLM 요청 처리

```
Option A: 현재 방식 (asyncio.to_thread, 직접 처리)
  한계: 스레드 풀 고갈 시 503, 재시도 로직 없음

Option B: Celery + Redis 큐
  장점: 작업 큐, 재시도, 우선순위 제어
  단점: Celery worker 별도 운영, 응답을 WebSocket으로 전달하는 양방향 브릿지 복잡

Option C: asyncio + Semaphore로 동시성 제한 + 응답 스트리밍
  장점: 추가 인프라 없음, WebSocket과 자연스럽게 통합, LangChain 스트리밍 API 활용
  단점: 단일 프로세스 내에서만 제어

추천: Option C (중소형 규모)
  asyncio.Semaphore로 동시 LLM 호출 수 제한 (예: 최대 50)
  LangChain astream으로 토큰 단위 WebSocket 스트리밍
  트래픽 급증 시 Celery로 전환 (인터페이스 분리로 교체 용이하게 설계)
```

---

## 목표 아키텍처

```
Customer Browser          Admin Browser (Next.js dashboard)
     │ WebSocket                │ REST API / WebSocket
     │                          │
     └──────────┬───────────────┘
                │
        FastAPI (uvicorn, 멀티워커)
        ┌───────────────────────────────┐
        │  WebSocket Manager            │
        │  (Redis pub/sub 브로드캐스트)  │
        │                               │
        │  LangChain Agent              │
        │  (asyncio.Semaphore 제한)     │
        │  LLM 스트리밍 응답             │
        └──────────┬────────────────────┘
                   │
        ┌──────────┼──────────────────┐
        │          │                  │
      Redis    PostgreSQL         ChromaDB
   (세션/pub)  (로그/주문/피드백)  (벡터 DB, 서버 모드)
                   │
              OpenAI API
```

---

## Phase 계획

### Phase A: 데이터 영속성 & Docker 기반 세팅
**목표**: 인메모리 저장소 제거, 로컬 개발환경 Docker Compose 구성
**브랜치**: `feat/persistence-layer`

작업:
1. `docker-compose.yml` 작성 (FastAPI + Redis + PostgreSQL + ChromaDB)
2. `app/storage/` 모듈 신규 생성
   - `redis_client.py` — 세션 히스토리 (기존 `chat_history_store` dict 대체)
   - `postgres_client.py` — chat_logs, feedback 영구 저장 (기존 list 대체)
3. `app/agent/rag.py` 수정
   - `get_session_history()` → Redis 기반으로 교체
   - ChromaDB client를 HTTP 서버 모드로 전환
4. `app/api/webhook.py` 수정
   - `chat_logs` list → PostgreSQL INSERT
   - `/api/logs`, `/api/logs/{id}/feedback` → PostgreSQL SELECT/UPDATE
5. `app/agent/tools.py`
   - MOCK_DB → PostgreSQL 테이블로 마이그레이션 (SQLAlchemy 모델 추가)

수정 대상 파일:
- `app/agent/rag.py` (get_session_history 함수)
- `app/api/webhook.py` (chat_logs 전체)
- `app/agent/tools.py` (MOCK_DB)
- `app/config.py` (DB URL 설정 추가)
- `docker-compose.yml` (신규)

검증: `pytest` 전체 통과 + `docker compose up` 후 기능 동작 확인

---

### Phase B: Sendbird 제거 & WebSocket 채팅 UI 구축
**목표**: Sendbird 의존성 제거, FastAPI WebSocket + Next.js 자체 UI 구축
**브랜치**: `feat/custom-chat-ui`

작업:
1. FastAPI WebSocket 엔드포인트 추가 (`app/api/chat_ws.py`)
   - `WebSocketManager` 클래스 (연결 관리 + Redis pub/sub 브로드캐스트)
   - `/ws/{user_id}` 엔드포인트
   - LangChain `astream()` 으로 토큰 단위 스트리밍
   - asyncio.Semaphore로 동시 LLM 호출 제한
2. `app/sendbird/` 모듈 제거 (또는 옵션으로 비활성화)
3. `dashboard/app/chat/` 신규 페이지 추가 (고객 채팅 UI)
   - WebSocket 훅 (`useWebSocket`)
   - 메시지 버블 컴포넌트
   - 타이핑 인디케이터 (스트리밍 토큰 표시)
4. `dashboard/app/admin/` 업데이트 (기존 page.tsx 확장)
   - 실시간 채팅 모니터링 (WebSocket 구독)
   - 상담원 수동 개입 (인간 핸드오프 UI)

수정 대상 파일:
- `app/api/chat_ws.py` (신규)
- `app/main.py` (라우터 추가)
- `dashboard/app/chat/page.tsx` (신규)
- `dashboard/app/admin/page.tsx` (기존 확장)

검증: 브라우저에서 WebSocket 채팅 → 스트리밍 응답 확인, 다중 탭에서 동시 접속 테스트

---

### Phase C: 신뢰성 & 운영 강화
**목표**: 프로덕션 신뢰성 (에러 처리, rate limit, 모니터링)
**브랜치**: `feat/reliability`

작업:
1. Rate limiting (slowapi 또는 미들웨어)
2. WebSocket 재연결 로직 (클라이언트측 exponential backoff)
3. LLM 호출 타임아웃 + 재시도 (`tenacity` 이미 requirements에 있음)
4. `/metrics` 엔드포인트 (Prometheus 포맷) — latency, token usage, concurrent connections
5. 헬스체크 강화 (`/health`에 Redis/PostgreSQL 연결 상태 포함)
6. 알림 (상담원 핸드오프 시 Slack webhook 또는 이메일)

검증: 부하 테스트 (`locust` 또는 `k6`로 동시 100 연결 시뮬레이션)

---

### Phase D: 토큰 비용 최적화
**목표**: 수백~수천 동접 규모에서 LLM 토큰 비용을 50~70% 절감
**브랜치**: `feat/token-cost-optimization`
**전제**: Phase C에서 구축된 토큰/비용 메트릭 위에서 진행

#### 의사결정: 어느 기법을 어디에 적용할 것인가

```
기법 ①: Prompt Caching (OpenAI/Anthropic 네이티브)
  효과: 시스템 프롬프트 + 도구 정의 = 매 호출 동일 토큰을 50% 할인
  비용: 거의 0 (코드 변경 최소)
  CS 챗봇 적합도: ★★★★★ (시스템 프롬프트 + 5개 도구 = 매번 ~2K 토큰 반복)

기법 ②: Semantic Cache (Redis + 임베딩 유사도)
  효과: "환불 어떻게 해요?" 같은 반복 FAQ는 LLM 호출 자체 생략
  비용: 임베딩 1회 호출 (~$0.00002) vs LLM 호출 (~$0.001~0.01)
  CS 챗봇 적합도: ★★★★★ (CS는 동일/유사 질문 비율이 높음, 30~50% 캐시 적중 기대)
  주의: 답변이 시간 의존적인 경우(예: 주문 상태) 캐싱 제외 필요

기법 ③: Chat History Trimming/Summarization
  효과: 현재 RunnableWithMessageHistory는 전체 히스토리 전송 → 대화 길어질수록 토큰 선형 증가
  방법: trim_messages(token=2000) 슬라이딩 윈도우 또는 ConversationSummaryBufferMemory
  CS 챗봇 적합도: ★★★★ (CS 대화는 평균 5~10턴, 하지만 일부 사용자가 수십 턴 진행)

기법 ④: Model Routing (intent 분류 → 모델 선택)
  효과: 단순 FAQ는 gpt-4o-mini, 복잡한 멀티툴 호출은 gpt-4o
  비용: 분류용 작은 모델 호출 (~$0.0001 추가) vs 비싼 모델 절감
  CS 챗봇 적합도: ★★★ (현재 gpt-3.5-turbo 단일 모델 사용 중이라 효과 제한적, 모델 업그레이드와 함께)

기법 ⑤: Token Budget & Rate Limiting
  효과: 어뷰징/무한 루프로 인한 비용 폭증 방지
  방법: 사용자별 일일 토큰 한도 (Redis 카운터)
  CS 챗봇 적합도: ★★★★ (운영 안전망)

기법 ⑥: Batch API (50% 할인)
  효과: 비실시간 작업 (eval, 재학습 데이터 생성)에 사용
  CS 챗봇 적합도: ★★ (실시간 채팅엔 부적합, eval/ 파이프라인에 한정)
```

#### 작업 순서 (효과 큰 것부터)

1. **Prompt Caching 활성화** (`app/agent/rag.py`)
   - OpenAI: 1024 토큰 이상 자동 캐싱 — 시스템 프롬프트가 짧으면 패딩 또는 도구 설명 보강
   - 검증: 동일 질문 두 번 보냈을 때 `prompt_tokens_details.cached_tokens` 확인

2. **Semantic Cache 도입** (`app/agent/cache.py` 신규)
   - 사용자 질문을 임베딩 → Redis Vector Search 또는 단순 코사인 유사도
   - 임계값(예: 0.95) 이상 매치 시 캐시된 답변 반환
   - 캐시 키 분리: 시간 의존적 답변(주문 조회 등)은 도구 호출 결과를 보고 제외 결정
   - 캐시 TTL: FAQ는 7일, 정책 변경 시 무효화 메커니즘

3. **Chat History 트리밍** (`app/agent/rag.py` `get_session_history` 래핑)
   - LangChain `trim_messages` 적용 (max_tokens=2000, strategy="last")
   - 또는 N턴 초과 시 요약본으로 압축 (`ConversationSummaryBufferMemory` 패턴)

4. **Model Routing** (`app/agent/router.py` 신규, 선택적)
   - 간단한 의도 분류 (룰 기반 또는 small classifier)
   - 단순 FAQ → gpt-4o-mini, 복잡 도구 호출 → gpt-4o
   - eval 파이프라인으로 품질 회귀 검증 필수

5. **Token Budget 미들웨어** (`app/api/middleware.py` 신규)
   - 사용자별 일일/시간당 토큰 한도 (Redis INCR + EXPIRE)
   - 한도 초과 시 429 응답 또는 상담원 핸드오프

6. **eval 파이프라인 확장** (`eval/cost_eval.py` 신규)
   - 골든셋에 대해 비용 vs 품질 측정
   - 캐싱/트리밍/모델 변경 전후 회귀 검증

수정 대상 파일:
- `app/agent/rag.py` (Prompt Caching, history 트리밍)
- `app/agent/cache.py` (신규, Semantic Cache)
- `app/agent/router.py` (신규, 선택적)
- `app/api/middleware.py` (신규, Token Budget)
- `app/observability/metrics.py` (Phase C에서 시작 — `cache_hit_rate`, `cost_per_session` 메트릭 추가)
- `eval/cost_eval.py` (신규)

검증:
- 골든 QA Set으로 품질 회귀 없음 확인 (정확도 -5% 이내)
- 동일 질문 반복 시 토큰 비용 80% 이상 절감
- 부하 테스트로 캐시 적중률 측정 (목표: 30%+)

---

### Phase E: 클라우드 배포
**목표**: Docker Compose → 클라우드 배포 (GCP Cloud Run 또는 단일 VM)
**브랜치**: `ci/cloud-deploy`

작업:
1. `Dockerfile` 최적화 (멀티스테이지 빌드)
2. 환경변수 관리 (Secret Manager 또는 .env.production)
3. GitHub Actions CI/CD (테스트 → 빌드 → 배포)
4. 도메인 + SSL (Cloud Run 자동 또는 Nginx + Let's Encrypt)
5. 로그 집계 (GCP Logging 또는 Loki)

---

## 검증 전략

각 Phase 완료 후:
1. `pytest` 전체 통과
2. `docker compose up` 후 수동 e2e 테스트 (브라우저 채팅 → AI 응답 확인)
3. 다중 워커 환경에서 세션 유지 확인 (`uvicorn --workers 4`)
4. Phase C 이후: `k6` 부하 테스트 (100 VU, 5분 지속)