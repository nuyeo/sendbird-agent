# docs/

LLM이 개발 시 참고할 프로젝트 기획 및 구현 문서 모음입니다.

## 문서 구조

| 경로 | 설명 |
|------|------|
| `overview.md` | 프로젝트 비전, 아키텍처, v2 로드맵 |
| `conventions.md` | 커밋 컨벤션, PR 전략, 코드 스타일 |
| `phases/` | 구현 단계(Phase)별 기획 문서 |
| `specs/` | 기능별 상세 스펙 문서 |

## 사용 방법

1. 새로운 개발 세션을 시작할 때 `overview.md`를 먼저 읽어 전체 맥락을 파악합니다.
2. 현재 작업할 phase 문서(`phases/phase-N.md`)를 읽고 요구사항을 확인합니다.
3. 코드 작성 시 `conventions.md`의 규칙을 따릅니다.
4. 필요 시 `specs/` 하위의 상세 스펙을 참고합니다.

## Phase 목록

| Phase | 내용 | 상태 |
|-------|------|------|
| [Phase 0](phases/phase-0.md) | 환경 준비 | 미착수 |
| [Phase 1](phases/phase-1.md) | 프로젝트 구조 리팩토링 | 미착수 |
| [Phase 2](phases/phase-2.md) | 프롬프트 외부화 (YAML) | 미착수 |
| [Phase 3](phases/phase-3.md) | 평가 파이프라인 구축 | 미착수 |
| [Phase 4](phases/phase-4.md) | Observability 강화 | 미착수 |
| [Phase 5](phases/phase-5.md) | CI/CD, Docker, 배포 | 미착수 |
