# 🛠 Sendbird AI Agent v2 — 리팩토링 & 개발 가이드

> 기존 레포(`nuyeo/sendbird-agent`)를 프로덕션급으로 고도화하기 위한 실행 가이드

---

## 🖥 IDE 추천

### 1순위: Cursor

AI Agent 프로젝트에는 **Cursor**를 강력 추천합니다.

- VS Code 기반이라 기존 익스텐션 전부 호환
- AI 코드 어시스턴트가 내장되어 있어 LangChain/FastAPI 코드 작성 시 생산성이 크게 올라감
- `.cursorrules` 파일에 프로젝트 컨텍스트를 넣어두면 프로젝트 전체를 이해한 상태로 코딩 보조
- 무료 플랜으로도 충분히 활용 가능
- 다운로드: https://cursor.com

### 2순위: VS Code

Cursor가 맞지 않다면 VS Code + 아래 익스텐션 조합도 좋습니다.

- **Python** (Microsoft) — 필수
- **Pylance** — 타입 체크, 자동완성
- **Ruff** — 포맷팅 + 린팅 (Black + isort + flake8 통합)
- **Even Better TOML** — pyproject.toml 편집
- **YAML** (Red Hat) — 프롬프트 YAML 편집
- **GitHub Copilot** — AI 코딩 어시스턴트 (유료)

### Cursor 사용 시 `.cursorrules` 설정

프로젝트 루트에 아래 파일을 만들어두면 AI가 프로젝트 맥락을 이해하고 도와줍니다.

```
# .cursorrules

이 프로젝트는 Sendbird AI Agent Backend입니다.
- Python 3.11, FastAPI, LangChain, ChromaDB 기반
- Sendbird Webhook으로 메시지를 수신하고 AI 응답을 생성하여 전송
- RAG (검색 증강 생성)와 Tool Calling을 지원
- 프롬프트는 YAML로 외부 관리
- 코드 스타일: Type Hint 필수, Ruff 포맷팅, Google Docstring
- 테스트: pytest + pytest-asyncio
```

---

## 📋 Step 0: 환경 준비

### 0-1. 레포 클론 & 브랜치 생성

```bash
git clone https://github.com/nuyeo/sendbird-agent.git
cd sendbird-agent

# v2 리팩토링 브랜치 생성
git checkout -b v2/refactor-structure
```

### 0-2. Python 환경 셋업

```bash
# pyenv 사용 시 (권장)
pyenv install 3.11.9
pyenv local 3.11.9

# 가상환경 생성
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 기존 의존성 설치
pip install -r requirements.txt
```

### 0-3. 현재 상태 확인

리팩토링 전에 반드시 현재 코드가 정상 동작하는지 확인하세요.

```bash
# 서버 실행 확인
uvicorn main:app --reload --port 8001

# 테스트 실행
pytest tests/
```

동작 확인이 끝나면 이 상태를 "baseline"으로 기억해두세요. 리팩토링 중 뭔가 깨졌을 때 돌아올 지점입니다.

---

## 📋 Step 1: 프로젝트 구조 리팩토링

> 🎯 목표: 현재 flat한 구조를 모듈별로 분리하여 Phase 3.5~6 작업의 기반 마련

### 1-1. 목표 디렉토리 구조

현재 구조에서 아래 구조로 점진적으로 마이그레이션합니다. 한 번에 다 바꾸지 말고, 파일 하나씩 옮기면서 임포트가 깨지지 않는지 확인하세요.

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
│   │   ├── rag.py               # RAG 파이프라인 (기존 코드 이전)
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
├── prompts/                      # ✨ 신규: 프롬프트 YAML
│   └── cs_agent_v1.yaml
├── eval/                         # ✨ 신규: 평가 파이프라인
│   ├── golden_qa.json
│   ├── run_eval.py
│   └── check_threshold.py
├── dashboard/                    # 기존 유지 (TypeScript)
├── data/                         # 기존 유지 (RAG 문서)
├── tests/                        # 기존 유지 + 확장
├── .github/workflows/            # 기존 유지 + 확장
├── .cursorrules                  # ✨ 신규
├── pyproject.toml                # ✨ 신규 (requirements.txt 대체)
├── Dockerfile                    # ✨ 신규
├── docker-compose.yaml           # ✨ 신규
└── README.md
```

### 1-2. 리팩토링 순서 (중요!)

파일을 옮길 때 아래 순서를 지키세요. 의존성이 적은 것부터 옮겨야 임포트 에러를 최소화할 수 있습니다.

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

### 1-3. config.py 생성 (첫 번째 작업)

기존에 `.env`에서 직접 읽던 환경변수를 Pydantic Settings로 관리합니다.

```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Sendbird
    sendbird_app_id: str
    sendbird_api_token: str

    # OpenAI
    openai_api_key: str

    # Agent
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.3
    chunk_size: int = 500
    chunk_overlap: int = 50
    retrieval_top_k: int = 5
    retrieval_score_threshold: float = 0.7

    # Server
    debug: bool = False

    class Config:
        env_file = ".env"

settings = Settings()
```

### 1-4. pyproject.toml 생성 (requirements.txt 대체)

```toml
# pyproject.toml
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
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "ruff>=0.8.0",
    "mypy>=1.13",
]
eval = [
    "ragas>=0.2.0",
]

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]

[tool.mypy]
python_version = "3.11"
strict = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### 1-5. 각 파일 이전 후 확인 체크리스트

파일 하나를 옮길 때마다 아래를 확인하세요.

```bash
# 임포트 에러 없는지 확인
python -c "from app.config import settings; print('OK')"
python -c "from app.agent.rag import ...; print('OK')"

# 서버 실행 확인
uvicorn app.main:app --reload --port 8001

# 기존 테스트 통과 확인
pytest tests/
```

---

## 📋 Step 2: 프롬프트 외부화 (Phase 3.5 시작)

> 🎯 목표: 코드에 하드코딩된 프롬프트를 YAML로 분리

### 2-1. 현재 코드에서 프롬프트 찾기

기존 코드에서 `system_prompt`, `SystemMessage`, `template` 등을 검색하여 하드코딩된 프롬프트를 모두 찾습니다.

```bash
# 프롬프트가 있을 법한 곳 검색
grep -rn "system" app/ --include="*.py" | grep -i "prompt\|message\|template"
```

### 2-2. YAML로 추출

```yaml
# prompts/cs_agent_v1.yaml
version: "1.0.0"
description: "기존 v1에서 추출한 프롬프트 (baseline)"
model: "gpt-4o-mini"
temperature: 0.3

system_prompt: |
  (기존 코드에서 추출한 시스템 프롬프트를 여기에 붙여넣기)

guardrails:
  - "답변에 확신이 없으면 '확인 후 안내드리겠습니다'로 응답"
  - "경쟁사 비교 질문에는 답변하지 않음"
```

### 2-3. 프롬프트 로더 구현

```python
# app/prompt/loader.py
from pathlib import Path
import yaml
from pydantic import BaseModel

class PromptConfig(BaseModel):
    version: str
    description: str
    model: str
    temperature: float
    system_prompt: str
    guardrails: list[str] = []

def load_prompt(name: str) -> PromptConfig:
    path = Path("prompts") / f"{name}.yaml"
    with open(path) as f:
        data = yaml.safe_load(f)
    return PromptConfig(**data)
```

### 2-4. 기존 코드에서 로더 사용으로 전환

```python
# Before (하드코딩)
system_message = SystemMessage(content="당신은 CS 에이전트입니다...")

# After (YAML 로드)
from app.prompt.loader import load_prompt
prompt_config = load_prompt("cs_agent_v1")
system_message = SystemMessage(content=prompt_config.system_prompt)
```

### 2-5. 커밋 & PR

```bash
git add .
git commit -m "feat: externalize prompts to YAML (Phase 3.5-1)"
git push origin v2/refactor-structure

# PR 생성 후 main에 머지
```

---

## 📋 Step 3: 평가 파이프라인 구축 (Phase 4)

> 🎯 목표: Golden QA Set + 자동 평가 스크립트

### 3-1. Golden QA Set 작성 (최소 20개부터 시작)

```bash
# 새 브랜치
git checkout main && git pull
git checkout -b v2/eval-pipeline
```

```json
// eval/golden_qa.json
[
  {
    "id": "TC-001",
    "category": "faq",
    "user_query": "환불 정책이 어떻게 되나요?",
    "expected_tool": null,
    "reference_answer": "구매 후 7일 이내 미사용 시 전액 환불 가능합니다.",
    "eval_criteria": ["faithfulness", "relevance"]
  },
  {
    "id": "TC-002",
    "category": "tool_calling",
    "user_query": "주문번호 ORD-12345 상태 알려줘",
    "expected_tool": "search_order_status",
    "reference_answer": null,
    "eval_criteria": ["tool_accuracy"]
  }
]
```

카테고리별 최소 분포: FAQ 8개, Tool Calling 6개, Edge Case 3개, Adversarial 3개

### 3-2. 평가 실행 스크립트 뼈대

```python
# eval/run_eval.py
import json
import asyncio
from pathlib import Path

async def run_evaluation():
    # 1. Golden Set 로드
    golden_set = json.loads(Path("eval/golden_qa.json").read_text())

    # 2. 각 테스트 케이스에 대해 에이전트 호출
    results = []
    for tc in golden_set:
        response = await call_agent(tc["user_query"])
        score = await judge_response(tc, response)
        results.append({"id": tc["id"], "score": score})

    # 3. 리포트 출력
    print_report(results)

if __name__ == "__main__":
    asyncio.run(run_evaluation())
```

세부 구현은 이후 단계에서 채워나갑니다. 먼저 이 뼈대를 만들어두세요.

---

## 📋 Step 4: Observability 강화 (Phase 5)

> 🎯 목표: structlog 도입 + 기존 dashboard 연동 강화

### 4-1. structlog 설정

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

### 4-2. 기존 로깅 API에 구조화된 필드 추가

현재 `/api/logs` 엔드포인트가 있으니, 여기에 latency, token_usage, intent, hallucination_check 필드를 추가합니다.

---

## 📋 Step 5~6: 이후 작업

Step 1~4가 완료되면 아래 순서로 진행합니다.

- **Prompt CI/CD** — GitHub Actions workflow 작성 (`prompts/` 변경 감지 → eval 실행)
- **Hallucination Self-Correction** — 검증 프롬프트 구현
- **Streamlit 대시보드** — 기존 TypeScript 대시보드와 별도로, 운영 지표용 Python 대시보드 추가
- **Docker & Cloud Deploy** — Dockerfile 작성, Cloud Run 배포

---

## 🔑 핵심 원칙

### 커밋 컨벤션

```
feat: 새로운 기능 추가
refactor: 코드 구조 변경 (기능 변화 없음)
fix: 버그 수정
docs: 문서 변경
test: 테스트 추가/수정
ci: CI/CD 설정 변경
```

예시:
```
refactor: separate RAG pipeline into app/agent/rag.py
feat: add YAML prompt loader (Phase 3.5)
test: add golden QA evaluation script skeleton
ci: add prompt quality gate workflow
```

### PR 전략

Phase별로 브랜치를 따서 PR을 만들면, 면접관이 레포를 볼 때 "이 사람이 어떤 단위로 사고하고 작업하는지"가 드러납니다.

```
v2/refactor-structure  →  main  (Step 1)
v2/prompt-external     →  main  (Step 2)
v2/eval-pipeline       →  main  (Step 3)
v2/observability       →  main  (Step 4)
v2/prompt-cicd         →  main  (Step 5)
v2/cloud-deploy        →  main  (Step 6)
```

### 막힐 때

이 가이드의 해당 Step을 복사해서 저에게 보여주고, 현재 코드 상태와 함께 질문하면 가장 정확한 도움을 드릴 수 있습니다.

예: *"Step 1-2의 리팩토링 중인데, agent/rag.py를 분리하고 나니 main.py에서 임포트 에러가 납니다. 현재 코드는 이렇습니다: ..."*