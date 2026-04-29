# Sendbird AI Agent

Sendbird Chat API + LangChain 기반 지능형 CS 에이전트 (RAG + Tool Calling)

## 프로젝트 문서

@docs/overview.md
@docs/conventions.md

## 핵심 명령어

```bash
# 서버 실행
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

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

## 프로덕션 스케일업 플랜

현재 v2를 프로덕션 규모로 확장하는 아키텍처 계획입니다.

상세 내용: `docs/plan.md`

- Phase A: 데이터 영속성 & Docker (Redis/PostgreSQL) → `feat/persistence-layer`
- Phase B: Sendbird 제거 & WebSocket 채팅 UI → `feat/custom-chat-ui`
- Phase C: 신뢰성 & 운영 강화 → `feat/reliability`
- Phase D: 토큰 비용 최적화 → `feat/token-cost-optimization`
- Phase E: 클라우드 배포 → `ci/cloud-deploy`

## 브랜치 전략

**main 브랜치에 직접 커밋하지 마세요.** 새로운 기능이나 변경사항은 반드시 알맞은 브랜치를 생성/checkout하여 작업하고, 작업이 완료되면 PR을 올립니다.

브랜치 네이밍: `{type}/{description}` — 커밋 컨벤션 prefix와 동일한 type을 사용합니다.

Phase별 브랜치:
```
refactor/modular-architecture  →  main
feat/prompt-yaml-loader        →  main
feat/eval-pipeline             →  main
feat/observability             →  main
ci/prompt-quality-gate         →  main
feat/cloud-deploy              →  main
```

일반 작업 브랜치 네이밍: `{type}/{description}` (예: `feat/add-login`, `fix/webhook-error`)

## 코드 스타일 핵심 규칙

- Python: Type Hint 필수, Ruff 포맷팅 (line-length: 100), Google Docstring
- 주석/docstring은 한국어 사용
- 커밋: `feat:`, `refactor:`, `fix:`, `docs:`, `test:`, `ci:` prefix 사용

## 개발 프로세스

각 Phase 또는 기능 개발 시작 전에 반드시 아래 절차를 따릅니다:

1. **요구사항 검증**: 문서에 적힌 내용이 현재 코드 상태와 일치하는지 확인
2. **의문 제기**: 각 요구사항에 대해 "왜 이게 필요한가?" 질문. YAGNI 원칙 적용
3. **비즈니스 성과 검토**: 이 작업이 가져올 구체적인 가치 정리
4. **문서 개선**: 검토 결과를 문서에 반영한 후 작업 시작
5. **브랜치 생성 → 작업 → PR**: main 직접 커밋 금지

## 커밋/PR 규칙

- 커밋/PR 제목에 phase 번호를 직접 기입하지 마세요 (내부 개발 편의용 넘버링이므로 레포에 노출 금지)
- 브랜치명에 `v2/` 같은 내부 버전 prefix를 사용하지 마세요. `{type}/{description}` 형식을 사용합니다.

## 주의사항

- `.env` 파일은 절대 커밋하지 마세요 (.gitignore에 포함됨)
- API 키나 시크릿을 코드에 하드코딩하지 마세요
- `requirements.txt` 변경 시 가상환경에서 테스트 후 커밋
- 미래 Phase의 코드/디렉토리를 현재 Phase에서 미리 만들지 마세요
- 현재 사용하지 않는 의존성을 미리 추가하지 마세요
