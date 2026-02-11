# 개발 컨벤션

## 커밋 컨벤션

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

## PR 전략

Phase별로 브랜치를 따서 PR을 만듭니다.

```
v2/refactor-structure  →  main  (Phase 1)
v2/prompt-external     →  main  (Phase 2)
v2/eval-pipeline       →  main  (Phase 3)
v2/observability       →  main  (Phase 4)
v2/prompt-cicd         →  main  (Phase 5)
v2/cloud-deploy        →  main  (Phase 5)
```

## 코드 스타일

- Type Hint 필수
- Ruff 포맷팅 (line-length: 100)
- Google Docstring 스타일
- 테스트: pytest + pytest-asyncio

## IDE 설정

### Cursor (1순위)
- `.cursorrules` 파일로 프로젝트 컨텍스트 제공
- VS Code 기반이라 기존 익스텐션 호환

### VS Code (2순위)
- Python (Microsoft), Pylance, Ruff, Even Better TOML, YAML (Red Hat)
