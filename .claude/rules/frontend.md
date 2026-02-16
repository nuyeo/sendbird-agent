---
paths:
  - "dashboard/**"
---

# 프론트엔드 규칙 (Dashboard)

## 기술 스택
- Next.js 16 (App Router)
- React 19
- Tailwind CSS 4
- TypeScript strict mode

## 실행
```bash
cd dashboard && npm run dev
```

## 규칙
- TypeScript strict mode를 준수합니다.
- 컴포넌트는 함수형으로 작성합니다.
- `any` 타입 사용을 지양합니다.
- Tailwind CSS 유틸리티 클래스를 사용합니다.
- ESLint 설정(`eslint-config-next`)을 따릅니다.
