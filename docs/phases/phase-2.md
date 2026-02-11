# Phase 2: 프롬프트 외부화

## 목표

코드에 하드코딩된 프롬프트를 YAML 파일로 분리하여, 코드 변경 없이 프롬프트를 수정·버전 관리할 수 있게 한다.

## 배경/맥락

현재 시스템 프롬프트가 Python 코드 안에 하드코딩되어 있어, 프롬프트 수정 시 코드 배포가 필요하다. YAML로 외부화하면 프롬프트 버전 관리, A/B 테스트, CI/CD 연동이 가능해진다.

## 요구사항

- [ ] 기존 코드에서 하드코딩된 프롬프트 모두 탐색
- [ ] `prompts/cs_agent_v1.yaml` 생성 (기존 프롬프트 추출)
- [ ] `app/prompt/loader.py` 구현 (YAML 프롬프트 로더)
- [ ] 기존 코드에서 로더를 사용하도록 전환
- [ ] 가드레일 규칙 YAML에 포함

## 기술적 결정사항

- 프롬프트 포맷: YAML (가독성 + 멀티라인 지원)
- 스키마 검증: Pydantic 모델

## 프롬프트 탐색 방법

```bash
grep -rn "system" app/ --include="*.py" | grep -i "prompt\|message\|template"
```

## YAML 구조

```yaml
# prompts/cs_agent_v1.yaml
version: "1.0.0"
description: "기존 v1에서 추출한 프롬프트 (baseline)"
model: "gpt-4o-mini"
temperature: 0.3

system_prompt: |
  (기존 코드에서 추출한 시스템 프롬프트)

guardrails:
  - "답변에 확신이 없으면 '확인 후 안내드리겠습니다'로 응답"
  - "경쟁사 비교 질문에는 답변하지 않음"
```

## 로더 참고 구현

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

## 전환 예시

```python
# Before (하드코딩)
system_message = SystemMessage(content="당신은 CS 에이전트입니다...")

# After (YAML 로드)
from app.prompt.loader import load_prompt
prompt_config = load_prompt("cs_agent_v1")
system_message = SystemMessage(content=prompt_config.system_prompt)
```

## 관련 파일

- `app/agent/rag.py` — 시스템 프롬프트가 하드코딩된 곳
- `app/prompt/loader.py` — 신규 생성
- `prompts/cs_agent_v1.yaml` — 신규 생성

## 완료 기준

- 코드 내에 하드코딩된 프롬프트가 없음
- `prompts/` 디렉토리의 YAML 파일만 수정해도 프롬프트 변경 가능
- 기존 기능 정상 동작
