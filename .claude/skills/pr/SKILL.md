---
description: "프로젝트 컨벤션에 맞는 PR을 생성합니다."
dynamic_context:
  - type: command
    command: "git log --oneline main..HEAD"
  - type: command
    command: "git branch --show-current"
---

# /pr - Pull Request 생성

## 사용법
```
/pr $ARGUMENTS
```

## 지시사항

1. 현재 브랜치와 main 브랜치 간의 변경사항을 분석합니다:
   - `git diff main...HEAD`로 코드 변경사항 확인
   - `git log --oneline main..HEAD`로 커밋 히스토리 확인

2. 변경사항이 커밋되지 않은 것이 있다면 사용자에게 알립니다.

3. PR을 생성합니다. 아래 형식을 따릅니다:

   **제목**: 커밋 컨벤션 prefix를 사용한 간결한 제목
   - 예: `refactor: separate RAG pipeline into app/agent/rag.py`
   - 예: `feat: add YAML prompt loader (Phase 2)`

   **본문**:
   ```
   ## Summary
   - 변경사항 요약 (1-3개 bullet point)

   ## Changes
   - 구체적인 변경 파일 및 내용

   ## Phase
   - 관련 Phase 번호 및 문서 참조 (해당하는 경우)

   ## Test plan
   - [ ] 테스트 계획 체크리스트
   ```

4. `$ARGUMENTS`가 있으면 PR 내용에 반영합니다.

5. `gh pr create`로 PR을 생성하고, PR URL을 사용자에게 알려줍니다.
