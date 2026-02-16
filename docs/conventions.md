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
feat: add YAML prompt loader
test: add golden QA evaluation script skeleton
ci: add prompt quality gate workflow
```

## 브랜치 전략

`{type}/{description}` 형식으로 브랜치를 생성하고, 작업 완료 후 main에 PR을 올립니다.

```
refactor/modular-architecture  →  main
feat/prompt-yaml-loader        →  main
feat/eval-pipeline             →  main
feat/observability             →  main
ci/prompt-quality-gate         →  main
feat/cloud-deploy              →  main
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
