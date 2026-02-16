# Sendbird AI Agent

Sendbird Chat API + LangChain 기반 지능형 CS 에이전트 (RAG + Tool Calling)

## 프로젝트 문서

@docs/overview.md
@docs/conventions.md

## 핵심 명령어

```bash
# 서버 실행
uvicorn main:app --host 0.0.0.0 --port 8001 --reload

# 테스트
pytest

# 린트 & 포맷팅
ruff check .
ruff format .

# 대시보드 (별도 터미널)
cd dashboard && npm run dev
```

## v2 개발 현황

현재 v2 개발을 6개 Phase로 진행 중입니다.

- Phase 0: 환경 세팅 & baseline 확인 → `docs/phases/phase-0.md`
- Phase 1: 프로젝트 구조 리팩토링 → `docs/phases/phase-1.md`
- Phase 2: 프롬프트 외부화 (YAML) → `docs/phases/phase-2.md`
- Phase 3: 평가 파이프라인 → `docs/phases/phase-3.md`
- Phase 4: 관측성 강화 → `docs/phases/phase-4.md`
- Phase 5: CI/CD, Docker, 배포 → `docs/phases/phase-5.md`

전체 가이드: `docs/sendbird-agent-v2.md`

## 브랜치 전략

Phase별 브랜치에서 작업 후 main에 병합:

```
v2/refactor-structure  →  main  (Phase 1)
v2/prompt-external     →  main  (Phase 2)
v2/eval-pipeline       →  main  (Phase 3)
v2/observability       →  main  (Phase 4)
v2/prompt-cicd         →  main  (Phase 5)
v2/cloud-deploy        →  main  (Phase 5)
```

## 코드 스타일 핵심 규칙

- Python: Type Hint 필수, Ruff 포맷팅 (line-length: 100), Google Docstring
- 주석/docstring은 한국어 사용
- 커밋: `feat:`, `refactor:`, `fix:`, `docs:`, `test:`, `ci:` prefix 사용

## 주의사항

- `.env` 파일은 절대 커밋하지 마세요 (.gitignore에 포함됨)
- API 키나 시크릿을 코드에 하드코딩하지 마세요
- `requirements.txt` 변경 시 가상환경에서 테스트 후 커밋
