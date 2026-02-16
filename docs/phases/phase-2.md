# Phase 2: 프롬프트 외부화

## 목표

코드에 하드코딩된 프롬프트를 YAML 파일로 분리하여, 코드 변경 없이 프롬프트를 수정·버전 관리할 수 있게 한다.

## 배경/맥락

현재 시스템 프롬프트가 `app/agent/rag.py`에 하드코딩되어 있어, 프롬프트 수정 시 코드 배포가 필요하다. YAML로 외부화하면 프롬프트 버전 관리, A/B 테스트, CI/CD 연동이 가능해진다.

## 비즈니스 성과

- **프롬프트 이터레이션 속도 향상**: PM/기획자도 YAML만 수정하여 프롬프트 튜닝 가능
- **버전 관리**: 프롬프트 변경 히스토리를 git에서 추적, 이전 버전 롤백 가능
- **평가 파이프라인 전제 조건**: 이후 프롬프트별 성능 비교를 위해 필수

## 요구사항

- [x] 기존 코드에서 하드코딩된 프롬프트 추출
- [x] `prompts/cs_agent_v1.yaml` 생성
- [x] `app/prompt/loader.py` 구현 (YAML 프롬프트 로더 + Pydantic 검증)
- [x] `app/agent/rag.py`에서 로더를 사용하도록 전환
- [x] 프롬프트 로더 단위 테스트 추가

### 검토 후 변경된 사항

- ~~YAML에 `model`, `temperature` 포함~~: `app/config.py`와 중복. YAML에는 프롬프트 관련 내용만 포함
- ~~`guardrails`를 별도 필드로 분리~~: 별도 처리 로직 없이 분리하면 의미 없음. system_prompt 안에 통합
- `load_prompt`의 경로 해석: 프로젝트 루트 기준 절대 경로로 해석

## YAML 구조

```yaml
# prompts/cs_agent_v1.yaml
version: "1.0.0"
description: "CS 에이전트 시스템 프롬프트 (baseline)"

system_prompt: |
  (기존 코드에서 추출한 시스템 프롬프트)
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
    system_prompt: str

def load_prompt(name: str) -> PromptConfig:
    base_dir = Path(__file__).resolve().parent.parent.parent
    path = base_dir / "prompts" / f"{name}.yaml"
    with open(path) as f:
        data = yaml.safe_load(f)
    return PromptConfig(**data)
```

## 관련 파일

- `app/agent/rag.py` — `load_prompt("cs_agent_v1")`으로 프롬프트 로드
- `app/prompt/loader.py` — 신규 생성
- `prompts/cs_agent_v1.yaml` — 신규 생성

## 완료 기준

- 코드 내에 하드코딩된 프롬프트가 없음
- `prompts/` 디렉토리의 YAML 파일만 수정해도 프롬프트 변경 가능
- 프롬프트 로더 단위 테스트 통과
- 기존 기능 정상 동작 (서버 실행, 기존 테스트 통과)
- `ruff check` 통과
