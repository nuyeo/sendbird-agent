---
description: "v2 phase 작업을 시작합니다. phase 번호를 인자로 받아 해당 문서를 읽고 작업을 계획합니다."
dynamic_context:
  - type: command
    command: "git branch --show-current"
---

# /phase - v2 Phase 작업 시작

## 사용법
```
/phase $ARGUMENTS
```

## 지시사항

1. `$ARGUMENTS`에서 phase 번호를 파싱합니다 (예: `1`, `phase-1`, `Phase 1` 등).

2. 해당 phase 문서를 읽습니다:
   - `docs/phases/phase-{번호}.md`
   - `docs/sendbird-agent-v2.md` (전체 맥락 참고)
   - `docs/conventions.md` (컨벤션 확인)

3. 현재 브랜치를 확인하고, phase에 맞는 브랜치를 생성합니다:
   - Phase 1: `v2/refactor-structure`
   - Phase 2: `v2/prompt-external`
   - Phase 3: `v2/eval-pipeline`
   - Phase 4: `v2/observability`
   - Phase 5: `v2/prompt-cicd` 또는 `v2/cloud-deploy`

4. phase 문서의 내용을 기반으로 작업 계획을 수립합니다:
   - 완료 기준 (Acceptance Criteria) 정리
   - 작업 순서 및 의존성 파악
   - 예상 변경 파일 목록

5. 작업 계획을 사용자에게 제시하고 승인을 받은 후 작업을 시작합니다.
