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
  단점: 채팅 컴포넌트(메시지 버블, 타이핑 인디케이터) 직접 구현

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
  장점: 낮은 지연, 자연스러운 채팅 UX
  단점: 수평 확장 시 Redis pub/sub 필요, 연결 상태 관리 복잡
  
Option B: SSE (Server-Sent Events, 서버→클라이언트 단방향)
  장점: 단순, HTTP 위에서 작동, 프록시 통과 쉬움
  단점: 클라이언트→서버는 별도 REST API 필요, 양방향 UX가 어색

추천: WebSocket
  채팅 UX 특성상 양방향이 자연스러움
  중소형 규모(수백 동접)에서 uvicorn + Redis pub/sub으로 충분히 관리 가능
```

**응답 방식**: 토큰 단위 스트리밍 불필요. `agent_executor.ainvoke()` 완료 후 전체 메시지를 1회 전송.
- 도구 호출 중간 상태가 클라이언트에 노출되지 않아 보안상 낫고, 구현이 단순
- 타이핑 인디케이터(처리 중 표시)로 UX 보완

**WebSocket pub/sub 채널 네임스페이스**:
- `chat:{user_id}` — 사용자 개인 채널 (AI 응답 전달)
- `admin:monitor` — 관리자 모니터링 채널 (전체 대화 구독)

### Decision 3: 세션/상태 저장소

```
Option A: Redis
  장점: O(1) 접근, TTL 기반 자동 만료, pub/sub으로 워커 간 브로드캐스트
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
  장점: 현재 코드 변경 최소 (로컬→HTTP 전환)
  단점: 별도 Chroma 서버 운영, PostgreSQL 있는데 3번째 스토리지 추가

Option B: pgvector (PostgreSQL 익스텐션)
  장점: Redis + PostgreSQL만으로 통합, 운영 단순화, SQL JOIN 가능
       실제 코드 변경: rag.py에서 Chroma(...) → PGVector(...) 약 3줄
       (requirements.txt에 SQLAlchemy==2.0.44, langchain-community에 PGVector 내장)
  단점: IVFFlat/HNSW 인덱스 설정 필요, 검색 품질 검증 필요

추천: Phase A에서 pgvector 함께 도입 (운영 단순화 이점 > 코드 변경 비용)
```

### Decision 5: LLM 요청 처리 (메시지 큐 불필요 사유)

```
Option A: 현재 방식 (asyncio.to_thread, 직접 처리)
  한계: 스레드 풀 고갈 시 503, 재시도 로직 없음

Option B: Celery + Redis 큐
  장점: 작업 큐, 재시도, 우선순위 제어
  단점: Celery worker 별도 프로세스 운영, WebSocket 결과 전달 브릿지 복잡

Option C: asyncio + Semaphore로 동시성 제한
  장점: 추가 인프라 없음, WebSocket과 자연스럽게 통합
  단점: 단일 프로세스 내에서만 제어

추천: Option C (중소형 규모)
  asyncio.Semaphore(50)로 동시 LLM 호출 수 제한
  agent_executor.ainvoke()로 비동기 처리, 완성 후 WebSocket 전송
```

**메시지 큐(Celery)가 지금 불필요한 이유**:
- 메시지 큐의 결과 → WebSocket 브릿지가 복잡 (Worker가 별도 프로세스라 Redis pub/sub 콜백 추가 필요)
- OpenAI API 자체 rate limit(TPM/RPM)이 우리 Semaphore보다 먼저 걸리는 경우가 대부분 → 큐의 우선순위 제어 효과 제한적
- 일시적 OpenAI 오류는 Phase C의 `tenacity` 재시도로 충분히 커버 가능
- 인터페이스(`get_ai_response()` 함수)를 유지하면 추후 내부 구현만 Celery 태스크로 교체 가능 (호출부 변경 없음)

**메시지 큐로 전환해야 하는 신호**:
- 동시 수천 명 동접 + 멀티 서버 (Semaphore가 프로세스 단위라 서버간 제어 불가)
- LLM 호출이 평균 30초+ 걸림 (HTTP/WebSocket 타임아웃 위험)
- VIP 고객 우선 큐, DLQ(Dead Letter Queue) 등 고급 큐 기능 요구

### Decision 6: 인증/인가 (추가)

Sendbird 제거 후 `/ws/{user_id}` 엔드포인트 인증이 필요합니다.

```
Option A: JWT 토큰 (WebSocket 핸드셰이크 시 query param)
  예: ws://host/ws/user123?token=<JWT>
  장점: stateless, FastAPI 기존 인증 패턴과 동일
  단점: 토큰 갱신을 WebSocket 연결 중 처리해야 함

Option B: 세션 쿠키
  장점: 브라우저 자동 처리
  단점: Redis 세션 스토어 필요

추천: Option A (JWT) — Phase A Redis 도입 시 blacklist로 무효화 가능
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
        │  ainvoke → 완성 응답 1회 전송 │
        └──────────┬────────────────────┘
                   │
        ┌──────────┼──────────────┐
        │          │              │
      Redis    PostgreSQL     (pgvector 내장)
   (세션/pub)  (로그/주문/피드백/벡터)
                   │
              OpenAI API (gpt-4o-mini)
```

**Phase 간 의존성**:
```
Phase A (Redis + PostgreSQL + pgvector) ──필수──→ Phase B (WebSocket pub/sub)
Phase C (메트릭 수집 기저선) ──────────────────→ Phase D (비용 최적화)
```

---

## PostgreSQL 스키마 설계

### 테이블 1: `chat_logs`

`webhook.py:27`의 `chat_logs: list` 대체.

```sql
CREATE TABLE chat_logs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     VARCHAR(100) NOT NULL,
    question    TEXT         NOT NULL,
    answer      TEXT         NOT NULL,
    latency_ms  INTEGER,
    token_usage JSONB,
    feedback    VARCHAR(10)  CHECK (feedback IN ('up', 'down')),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_chat_logs_user_id    ON chat_logs(user_id);
CREATE INDEX idx_chat_logs_created_at ON chat_logs(created_at DESC);
```

설계 이유:
- `id UUID`: `generate_request_id()`가 이미 UUID 형식 → 호환성 유지
- `token_usage JSONB`: OpenAI usage 구조체가 가변적, Phase D 비용 분석 시 `token_usage->>'completion_tokens'` 조회 가능
- `feedback CHECK`: 'up'/'down'만 허용하는 `FeedbackRequest` 모델과 DB 레벨에서 일치
- `created_at DESC` 인덱스: 관리자 대시보드의 최신 로그 조회 최적화

### 테이블 2: `orders`

`tools.py:9`의 `MOCK_DB` 대체.

```sql
CREATE TABLE orders (
    order_id     VARCHAR(20)  PRIMARY KEY,
    user_id      VARCHAR(100),
    status       VARCHAR(50)  NOT NULL,
    item         VARCHAR(200) NOT NULL,
    price        INTEGER      NOT NULL CHECK (price >= 0),
    purchased_at DATE         NOT NULL,
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_orders_user_id ON orders(user_id);
```

설계 이유:
- `order_id VARCHAR(20)`: MOCK_DB 키("A101", "B202") 형식 유지
- `status VARCHAR(50)` (ENUM 아님): 상태 추가 시 `ALTER TYPE` DDL 불필요
- `price INTEGER`: 환불 계산 로직이 정수 기반 (`int(price * 0.9)`)이므로 정수형 유지
- `updated_at`: `cancel_order` 도구의 상태 변경 감사 추적
- `user_id` nullable: MOCK_DB 호환, 이후 "내 주문 목록" 조회에 활용

`cancel_order` 도구 변경:
```python
# 전: MOCK_DB dict 직접 변경 → 재시작 시 초기화
# 후: PostgreSQL UPDATE (트랜잭션 안전)
await db.execute(
    "UPDATE orders SET status = '취소 완료', updated_at = NOW() WHERE order_id = $1",
    order_id
)
```

### 테이블 3: `sessions` (선택적, Phase B)

```sql
CREATE TABLE sessions (
    session_id    VARCHAR(100) PRIMARY KEY,
    user_id       VARCHAR(100) NOT NULL,
    started_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_active   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    message_count INTEGER      NOT NULL DEFAULT 0
);
```

설계 이유: Redis 히스토리는 TTL로 만료되지만 집계 데이터는 영구 저장 필요. Phase D Token Budget의 일일 한도 체크에 활용 가능.

---

## Phase 계획

### Phase A: 데이터 영속성 & Docker 기반 세팅
**목표**: 인메모리 저장소(`chat_history_store`, `chat_logs`, `MOCK_DB`)를 영속 스토리지로 교체하고, 로컬 개발환경을 Docker Compose로 구성한다.
**범위 (YAGNI)**: WebSocket/Sendbird 제거/JWT 인증은 Phase B 이후. Phase A는 **저장소 교체만** 다룬다.
**브랜치**: `feat/persistence-layer`

#### A-0. 사전 준비

추가할 의존성 (`requirements.txt`):
```
redis==5.2.1                     # Redis 클라이언트 (sync + asyncio)
langchain-redis==0.2.3           # RedisChatMessageHistory
psycopg[binary,pool]==3.2.3      # PostgreSQL 드라이버 (sync/async 모두 지원)
langchain-postgres==0.0.13       # PGVector (langchain-community에서 분리됨)
pgvector==0.3.6                  # pgvector Python 바인딩
```

> SQLAlchemy 2.0.44는 이미 포함, tenacity·pydantic-settings·structlog도 그대로 활용.

추가할 환경변수 (`.env.example`):
```
# Phase A 신규
REDIS_URL=redis://localhost:6379/0
POSTGRES_URL=postgresql+psycopg://cs_agent:cs_agent_pw@localhost:5432/cs_agent
LLM_MODEL=gpt-4o-mini

# 세션 TTL (초). 기본 24시간
SESSION_TTL_SECONDS=86400
```

#### A-1. Docker Compose & DB 초기화 (인프라 먼저)

**A-1-1. `docker-compose.yml` 작성**
- `postgres` 서비스: `pgvector/pgvector:pg16` 이미지 (PostgreSQL + pgvector 익스텐션 사전 설치)
- `redis` 서비스: `redis:7-alpine` (Phase D Step 2 진입 시 redis-stack으로 교체 검토)
- `app` 서비스: 현재 FastAPI를 컨테이너화 (Dockerfile은 Phase E에서 최적화, 여기는 개발용 최소)
- `volumes`: `postgres_data`, `redis_data` 영속화

**A-1-2. `db/init.sql` 작성** (postgres 컨테이너 초기 실행)
- `CREATE EXTENSION IF NOT EXISTS vector;`
- `CREATE EXTENSION IF NOT EXISTS pgcrypto;` (gen_random_uuid 용)
- `chat_logs`, `orders` 테이블 + 인덱스 생성 (위 스키마 그대로)
- `sessions` 테이블은 Phase B에서 생성 (지금 만들지 않음)

**A-1-3. `db/seed.sql` 작성** (orders 초기 데이터)
- 현재 `MOCK_DB`의 A101/B202/C303을 SQL INSERT로 변환
- `purchased_at`은 `CURRENT_DATE - INTERVAL '10 days'` 형태로 동적 생성 (테스트 환경 일관성 유지)

#### A-2. Storage 레이어 추가

**A-2-1. `app/storage/__init__.py`** — 빈 모듈

**A-2-2. `app/storage/database.py`** — SQLAlchemy 엔진/세션 팩토리
```python
# 핵심 구조 (의사코드)
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

engine = create_async_engine(settings.postgres_url, pool_size=10, max_overflow=20)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session
```

**A-2-3. `app/storage/models.py`** — SQLAlchemy 모델
- `ChatLog` 모델 (chat_logs 테이블 매핑)
- `Order` 모델 (orders 테이블 매핑)
- 모든 컬럼에 type hint, 한국어 docstring

**A-2-4. `app/storage/redis_client.py`** — Redis 연결 싱글톤
- `redis.asyncio.from_url(settings.redis_url)` 반환
- 연결 풀 + 헬스체크 함수 (`async def ping() -> bool`)

#### A-3. 인메모리 저장소 → 영속 저장소 교체

**A-3-1. `app/agent/rag.py`**
- `chat_history_store: dict` 제거
- `get_session_history()` 시그니처 유지하되 내부를 `RedisChatMessageHistory(session_id, redis_url, ttl=SESSION_TTL_SECONDS)`로 교체
- 벡터 DB: `Chroma(persist_directory=...)` → `PGVector(connection=..., collection_name="faq", embeddings=embeddings)`
- 문서 최초 인덱싱 로직: 벡터 DB가 비었을 때만 `PGVector.from_documents(...)` 호출 (현재 `db_path_obj.exists()` 체크 패턴을 SQL `SELECT COUNT(*)` 체크로 변경)
- `get_ai_response()` 시그니처/리턴 형식 그대로 유지 (호출부 영향 최소화)

**A-3-2. `app/agent/tools.py`**
- `MOCK_DB` dict 제거
- `search_order_status`, `cancel_order`를 동기 도구에서 **async tool**로 변경 (LangChain `@tool` 데코레이터는 async 함수도 지원)
- DB 세션은 `AsyncSessionLocal()` 컨텍스트 매니저로 도구 내부에서 직접 획득 (LangChain 도구는 FastAPI Depends를 못 받음)
- `cancel_order`의 상태 업데이트는 트랜잭션 안에서 SELECT FOR UPDATE → UPDATE (동시 취소 방지)
- `print(...)` 디버그 로그는 `logger.info(...)`로 교체

**A-3-3. `app/api/webhook.py`**
- `chat_logs: list` 제거, `MAX_CHAT_LOGS` 상수 제거
- 로그 INSERT: 새 함수 `app/storage/repositories/chat_log_repo.py`의 `create_chat_log(...)` 호출
- `GET /api/logs`: `SELECT ... ORDER BY created_at DESC LIMIT 100` (페이징은 Phase C에서)
- `PUT /api/logs/{log_id}/feedback`: `UPDATE chat_logs SET feedback = ... WHERE id = ...` (UUID 캐스팅 주의)
- DB 세션은 `Depends(get_db)`로 주입

**A-3-4. `app/storage/repositories/chat_log_repo.py`** (신규)
- `create_chat_log(...)`, `list_chat_logs(...)`, `update_feedback(...)` 함수
- Repository 패턴으로 webhook.py가 SQL을 직접 다루지 않게 분리

**A-3-5. `app/storage/repositories/order_repo.py`** (신규)
- `get_order(order_id)`, `cancel_order(order_id)` 함수
- tools.py가 직접 호출

#### A-4. 설정 & 라이프사이클

**A-4-1. `app/config.py`**
- `llm_model` 기본값 `gpt-3.5-turbo` → `gpt-4o-mini`
- `redis_url`, `postgres_url`, `session_ttl_seconds` 필드 추가
- `sendbird_*` 필드는 그대로 유지 (Phase B에서 제거)

**A-4-2. `app/main.py` 라이프사이클**
- `lifespan` 진입 시 PostgreSQL/Redis ping (실패 시 startup 실패)
- 종료 시 `engine.dispose()` + `redis.close()`

#### A-5. 테스트

**A-5-1. 기존 테스트 유지**
- `tests/test_webhook.py` 등이 인메모리 저장소를 가정한다면 fixture를 PostgreSQL/Redis 픽스처로 변경
- pytest-asyncio + `pytest-postgresql`(또는 testcontainers) 도입 검토
- 또는 단순화를 위해 단위 테스트는 mock으로, 통합 테스트만 실제 DB로 분리

**A-5-2. 신규 테스트**
- `tests/storage/test_chat_log_repo.py` — Repository 함수 단위 테스트
- `tests/storage/test_order_repo.py` — 동시 cancel 시 race condition 검증

#### A-6. 단계별 작업 순서 (의존 그래프)

```
1. requirements.txt 업데이트 → docker compose에 빌드 반영
2. docker-compose.yml + db/init.sql + db/seed.sql 작성 → docker compose up으로 DB 기동 확인
3. app/config.py 환경변수 추가 (.env.example 갱신)
4. app/storage/database.py + redis_client.py
5. app/storage/models.py
6. app/storage/repositories/ (chat_log_repo, order_repo)
7. app/agent/tools.py 수정 (MOCK_DB 제거)
8. app/agent/rag.py 수정 (Redis 히스토리 + pgvector)
9. app/api/webhook.py 수정 (Repository 호출)
10. app/main.py lifespan 수정
11. 테스트 추가/수정
12. ruff check --fix . && ruff format . && pytest
```

#### A-7. 검증 체크리스트

- [ ] `docker compose up` 성공, postgres/redis healthy
- [ ] `pytest` 전체 통과 (기존 + 신규)
- [ ] `uvicorn app.main:app` 기동 후 기존 webhook 흐름 동작 (Sendbird 통신은 Phase A 범위 외이지만 코드는 그대로 유지됨)
- [ ] 서버 재시작 후 채팅 히스토리 유지 확인 (`SELECT` 또는 직접 LangChain 호출)
- [ ] `uvicorn --workers 4` 멀티 워커 환경에서 한 워커가 만든 세션을 다른 워커가 읽을 수 있는지 확인
- [ ] `cancel_order` 동시 호출 시 한 번만 성공 (트랜잭션 검증)
- [ ] `ruff check .` 클린, `ruff format .` 적용

#### A-8. 의도적으로 Phase A에서 다루지 않는 것 (YAGNI)

- WebSocket / Sendbird 제거 → **Phase B**
- JWT 인증 → **Phase B** (Sendbird webhook은 자체 시그니처 검증이 있음)
- Rate limiting / `/metrics` → **Phase C**
- Semantic Cache / Token Budget → **Phase D**
- Alembic 마이그레이션 → 지금은 `init.sql`로 충분, 스키마가 늘면 그때 도입

---

### Phase B: Sendbird 제거 & WebSocket 채팅 UI 구축
**목표**: Sendbird 의존성 제거, FastAPI WebSocket + Next.js 자체 UI 구축
**전제**: Phase A (Redis) 완료 필수
**브랜치**: `feat/custom-chat-ui`

작업:
1. FastAPI WebSocket 엔드포인트 추가 (`app/api/chat_ws.py`)
   - `WebSocketManager` 클래스 (연결 관리 + Redis pub/sub 브로드캐스트)
   - `/ws/{user_id}` 엔드포인트 (JWT 인증 포함)
   - asyncio.Semaphore로 동시 LLM 호출 제한
   - `agent_executor.ainvoke()` → 완성 응답 1회 전송
2. `app/sendbird/` 모듈 제거
3. `dashboard/app/chat/` 신규 페이지 추가 (고객 채팅 UI)
   - WebSocket 훅 (`useWebSocket`)
   - 메시지 버블 컴포넌트
   - 타이핑 인디케이터 (처리 중 표시, 완성 후 메시지 표시)
4. `dashboard/app/admin/` 업데이트 (기존 page.tsx 확장)
   - 실시간 채팅 모니터링 (`admin:monitor` 채널 구독)

수정 대상 파일:
- `app/api/chat_ws.py` (신규)
- `app/main.py` (라우터 추가)
- `dashboard/app/chat/page.tsx` (신규)
- `dashboard/app/admin/page.tsx` (기존 확장)

검증: 브라우저에서 WebSocket 채팅 → AI 응답 수신 확인, 다중 탭에서 동시 접속 테스트

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

검증: 부하 테스트 (`locust` 또는 `k6`로 동시 100 연결 시뮬레이션)

---

### Phase D: 토큰 비용 최적화
**목표**: 수백~수천 동접 규모에서 LLM 토큰 비용을 50~70% 절감
**전제**: Phase C에서 구축된 토큰/비용 메트릭 기저선 측정 후 진행
**브랜치**: `feat/token-cost-optimization`

#### 최적화 기법 (효과 큰 것부터)

```
기법 ①: Prompt Caching (OpenAI 네이티브)
  효과: 시스템 프롬프트 + 도구 정의 매 호출 동일 토큰을 50% 할인
  CS 챗봇 적합도: ★★★★★

기법 ②: Semantic Cache
  Step 1 (기본 Redis): 정규화된 문자열 exact-match 캐시
    - 질문 소문자화 + 공백 정규화 → Redis SET 조회
    - FAQ 반복 질문 30~40% 적중 기대, 추가 인프라 없음
  Step 2 (Redis Stack): Vector Search 기반 유사도 캐시
    - docker-compose의 redis 이미지를 redis/redis-stack으로 변경
    - 유사도 임계값 0.95 이상 캐시 적중
    - Step 1 효과 측정 후 부족할 경우 진행
  CS 챗봇 적합도: ★★★★★

기법 ③: Chat History 트리밍
  효과: 대화 길어질수록 토큰 선형 증가 방지
  방법: LangChain trim_messages(max_tokens=2000, strategy="last")
  CS 챗봇 적합도: ★★★★

기법 ④: Token Budget 미들웨어
  효과: 어뷰징/무한 루프로 인한 비용 폭증 방지
  방법: 사용자별 일일 토큰 한도 (Redis INCR + EXPIRE)
  CS 챗봇 적합도: ★★★★
```

작업:
1. Prompt Caching 활성화 (`app/agent/rag.py`)
2. Semantic Cache Step 1 도입 (`app/agent/cache.py` 신규, exact-match)
3. Chat History 트리밍 (`app/agent/rag.py` 수정)
4. Token Budget 미들웨어 (`app/api/middleware.py` 신규)
5. eval 파이프라인 (`eval/cost_eval.py` 신규)

검증:
- 골든 QA Set으로 품질 회귀 없음 확인 (정확도 -5% 이내)
- 동일 질문 반복 시 토큰 비용 절감 측정
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
