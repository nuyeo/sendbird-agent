# Phase 1: 프로젝트 구조 리팩토링

## 목표

현재 flat한 구조를 모듈별로 분리하여 이후 Phase의 기반을 마련한다.

## 배경/맥락

v1의 코드가 `main.py`, `app/rag.py`, `app/tools.py`에 집중되어 있어 기능 확장이 어렵다. 모듈별로 분리하면 프롬프트 외부화, 평가 파이프라인, Observability 등을 독립적으로 추가할 수 있다.

## 비즈니스 성과

- **개발 속도 향상**: 모듈 경계가 명확해져 Phase 2~5 작업 시 수정 범위가 줄어듦
- **온보딩 용이**: 새 팀원이 코드를 파악하는 시간 단축 (파일명만 보고 역할 파악 가능)
- **독립 테스트 가능**: 모듈별 단위 테스트로 회귀 버그 조기 발견
- **코드 리뷰 효율**: PR 단위가 모듈별로 분리되어 리뷰 부담 감소

## 요구사항

- [ ] `app/config.py` 생성 (Pydantic Settings로 환경변수 관리)
- [ ] `app/sendbird/client.py` 분리 (Sendbird API 클라이언트)
- [ ] `app/agent/rag.py` 분리 (RAG 파이프라인 + 대화 상태 관리)
- [ ] `app/agent/tools.py` 분리 (Tool 정의)
- [ ] `app/api/webhook.py` 분리 (Webhook 핸들러 + 로그 관리)
- [ ] `app/api/health.py` 분리 (헬스체크)
- [ ] `app/main.py` 정리 (API 라우터만 등록)
- [ ] `pyproject.toml` 생성 (requirements.txt 대체)
- [ ] 리팩토링 후 테스트 보강 (config, sendbird client, API 엔드포인트)

### 검토 후 제거된 항목

아래 항목은 YAGNI 원칙에 따라 Phase 1 범위에서 제외함:

- ~~`app/agent/chain.py`~~: 현재 LangChain의 `create_tool_calling_agent`가 의도 분류를 이미 처리함. 별도 Router Chain은 불필요
- ~~`app/agent/state.py`~~: 대화 상태 관리가 ~15줄로, `rag.py`에 유지하는 것이 탐색 효율적
- ~~`app/prompt/`~~: Phase 2에서 생성
- ~~`app/evaluation/`~~: Phase 3에서 생성
- ~~`app/observability/`~~: Phase 4에서 생성

## 목표 디렉토리 구조

```
sendbird-agent/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI 앱 (기존 root main.py에서 이전)
│   ├── config.py                # 환경변수 관리 (Pydantic Settings)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── webhook.py           # POST /webhook + 로그 API
│   │   └── health.py            # GET / 헬스체크
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── rag.py               # RAG 파이프라인 + 대화 상태 관리
│   │   └── tools.py             # Tool 정의
│   └── sendbird/
│       ├── __init__.py
│       └── client.py            # Sendbird API 클라이언트
├── dashboard/                    # 기존 유지
├── data/                         # 기존 유지
├── tests/                        # 기존 유지 + 확장
├── .github/workflows/            # 기존 유지
└── pyproject.toml                # requirements.txt 대체
```

## 기술적 결정사항

- 환경변수 관리: `python-dotenv` + `os.getenv()` → `pydantic-settings`
- 의존성 관리: `requirements.txt` → `pyproject.toml`
- 린팅/포맷팅: `ruff` 도입

## 리팩토링 순서 (의존성 순)

한 번에 다 바꾸지 말고, 파일 하나씩 옮기면서 임포트가 깨지지 않는지 확인한다.

```
① config.py 생성 (의존성 없음)
② sendbird/client.py 분리 (config만 의존)
③ agent/tools.py 이전 (config만 의존)
④ agent/rag.py 이전 (config, tools, 외부 라이브러리 의존)
⑤ api/webhook.py 분리 (rag, sendbird 의존)
⑥ api/health.py 분리 (의존성 없음)
⑦ main.py 정리 (api 라우터만 등록)
⑧ pyproject.toml 생성 + pytest.ini 통합
⑨ 테스트 보강
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

현재 코드에서 실제로 사용되는 값만 Settings로 추출한다.

```python
# app/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """애플리케이션 설정."""

    # Sendbird
    sendbird_app_id: str
    sendbird_api_token: str

    # OpenAI
    openai_api_key: str

    # Agent
    llm_model: str = "gpt-3.5-turbo"      # 현재 실제 사용 모델
    llm_temperature: float = 0.0           # 현재 실제 사용 값
    chunk_size: int = 500
    chunk_overlap: int = 0                 # 현재 실제 사용 값 (문서는 50이었으나 코드는 0)

    # Server
    debug: bool = False

    model_config = {"env_file": ".env"}


settings = Settings()
```

## pyproject.toml 참고

현재 실제 사용 중인 패키지만 포함한다. Phase별로 필요한 패키지는 해당 Phase에서 추가한다.

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
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.24", "ruff>=0.8.0"]

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["."]
```

## 관련 파일

- `main.py` — 분해 대상 (엔트리포인트)
- `app/rag.py` → `app/agent/rag.py`로 이전
- `app/tools.py` → `app/agent/tools.py`로 이전

## 완료 기준

- 목표 디렉토리 구조대로 파일이 분리됨
- `uvicorn app.main:app --reload --port 8001`로 서버 정상 실행
- `pytest tests/` 전체 통과
- 기존 기능(Webhook, RAG, Tool Calling) 정상 동작
- config, sendbird client, API 엔드포인트에 대한 단위 테스트 추가
- `ruff check .` 통과
