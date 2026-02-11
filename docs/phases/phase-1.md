# Phase 1: 프로젝트 구조 리팩토링

## 목표

현재 flat한 구조를 모듈별로 분리하여 이후 Phase의 기반을 마련한다.

## 배경/맥락

v1의 코드가 `main.py`, `app/rag.py`, `app/tools.py`에 집중되어 있어 기능 확장이 어렵다. 모듈별로 분리하면 프롬프트 외부화, 평가 파이프라인, Observability 등을 독립적으로 추가할 수 있다.

## 요구사항

- [ ] `app/config.py` 생성 (Pydantic Settings로 환경변수 관리)
- [ ] `app/sendbird/client.py` 분리 (Sendbird API 클라이언트)
- [ ] `app/agent/rag.py` 분리 (RAG 파이프라인)
- [ ] `app/agent/tools.py` 분리 (Tool 정의)
- [ ] `app/agent/chain.py` 분리 (Router Chain: 의도 분류)
- [ ] `app/api/webhook.py` 분리 (Webhook 핸들러)
- [ ] `app/api/health.py` 분리 (헬스체크)
- [ ] `app/main.py` 정리 (API 라우터만 등록)
- [ ] `pyproject.toml` 생성 (requirements.txt 대체)

## 목표 디렉토리 구조

```
sendbird-agent/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI 앱 (기존 root main.py에서 이전)
│   ├── config.py                # 환경변수 관리 (Pydantic Settings)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── webhook.py           # POST /webhook 핸들러
│   │   └── health.py            # GET / 헬스체크
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── chain.py             # Router Chain (의도 분류 → RAG or Tool)
│   │   ├── rag.py               # RAG 파이프라인
│   │   ├── tools.py             # Tool 정의
│   │   └── state.py             # 대화 상태 관리
│   ├── prompt/
│   │   ├── __init__.py
│   │   └── loader.py            # YAML 프롬프트 로더
│   ├── evaluation/
│   │   ├── __init__.py
│   │   ├── judge.py             # LLM-as-Judge
│   │   └── hallucination.py     # Self-Correction
│   ├── observability/
│   │   ├── __init__.py
│   │   ├── logger.py            # structlog 설정
│   │   └── metrics.py           # 메트릭 수집
│   └── sendbird/
│       ├── __init__.py
│       └── client.py            # Sendbird API 클라이언트
├── prompts/                      # 프롬프트 YAML (Phase 2에서 추가)
├── eval/                         # 평가 파이프라인 (Phase 3에서 추가)
├── dashboard/                    # 기존 유지
├── data/                         # 기존 유지
├── tests/                        # 기존 유지 + 확장
├── .github/workflows/            # 기존 유지 + 확장
├── pyproject.toml                # requirements.txt 대체
├── Dockerfile                    # Phase 5에서 추가
└── docker-compose.yaml           # Phase 5에서 추가
```

## 기술적 결정사항

- 환경변수 관리: `python-dotenv` → `pydantic-settings`
- 의존성 관리: `requirements.txt` → `pyproject.toml`
- 린팅/포맷팅: `ruff` 도입

## 리팩토링 순서 (의존성 순)

한 번에 다 바꾸지 말고, 파일 하나씩 옮기면서 임포트가 깨지지 않는지 확인한다.

```
① config.py 생성 (의존성 없음)
② sendbird/client.py 분리 (config만 의존)
③ agent/rag.py 분리 (config, 외부 라이브러리만 의존)
④ agent/tools.py 분리 (config만 의존)
⑤ agent/chain.py 분리 (rag, tools 의존)
⑥ api/webhook.py 분리 (chain, sendbird 의존)
⑦ api/health.py 분리 (의존성 없음)
⑧ main.py 정리 (api 라우터만 등록)
```

## 파일 이전 후 확인 체크리스트

파일 하나를 옮길 때마다 아래를 확인한다.

```bash
# 임포트 에러 확인
python -c "from app.config import settings; print('OK')"

# 서버 실행 확인
uvicorn app.main:app --reload --port 8001

# 기존 테스트 통과 확인
pytest tests/
```

## config.py 참고 구현

```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    sendbird_app_id: str
    sendbird_api_token: str
    openai_api_key: str
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.3
    chunk_size: int = 500
    chunk_overlap: int = 50
    retrieval_top_k: int = 5
    retrieval_score_threshold: float = 0.7
    debug: bool = False

    class Config:
        env_file = ".env"

settings = Settings()
```

## pyproject.toml 참고

```toml
[project]
name = "sendbird-ai-agent"
version = "2.0.0"
description = "Enterprise AI Agent Backend with RAG & Tool Calling"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn>=0.30.0",
    "langchain>=0.3.0",
    "langchain-openai>=0.2.0",
    "langchain-community>=0.3.0",
    "chromadb>=0.5.0",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "httpx>=0.27.0",
    "structlog>=24.0",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.24", "ruff>=0.8.0", "mypy>=1.13"]
eval = ["ragas>=0.2.0"]

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

## 관련 파일

- `main.py` — 분해 대상 (엔트리포인트)
- `app/rag.py` — `app/agent/rag.py`로 이전
- `app/tools.py` — `app/agent/tools.py`로 이전

## 완료 기준

- 목표 디렉토리 구조대로 파일이 분리됨
- `uvicorn app.main:app --reload --port 8001`로 서버 정상 실행
- `pytest tests/` 전체 통과
- 기존 기능(Webhook, RAG, Tool Calling) 정상 동작
