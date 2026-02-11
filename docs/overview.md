# Project Overview

## 프로젝트 소개

Sendbird Chat API와 LangChain을 활용한 지능형 CS 에이전트.
기업 문서를 참조(RAG)하여 답변하고, 실제 비즈니스 로직(Tool Calling)을 수행할 수 있는 챗봇 시스템입니다.

## 기술 스택

- **Backend**: Python 3.11, FastAPI, uvicorn
- **AI/LLM**: LangChain, OpenAI (GPT-3.5/4), ChromaDB
- **Frontend**: Next.js 16, React 19, Tailwind CSS 4
- **Communication**: Sendbird Chat SDK / API
- **CI/CD**: GitHub Actions
- **Infrastructure**: Ngrok (Tunneling), Docker (Planned)

## 아키텍처

```
User → Sendbird → Webhook(POST) → FastAPI Agent Server
                                        ↓
                                   ChromaDB (RAG)
                                        ↓
                                   OpenAI GPT → 응답 생성
                                        ↓
                                   Sendbird → User
```

## 주요 디렉토리 (현재 v1)

| 경로 | 설명 |
|------|------|
| `app/` | 핵심 비즈니스 로직 (RAG, Tool Calling) |
| `app/rag.py` | RAG 에이전트 구현 (벡터 DB 초기화, LangChain 에이전트) |
| `app/tools.py` | Tool Calling 함수 (주문조회, 취소, 환불계산, 상담원 연결) |
| `main.py` | FastAPI 엔트리포인트, 웹훅 핸들러, REST API |
| `dashboard/` | Next.js 프론트엔드 대시보드 |
| `data/` | FAQ 데이터 및 ChromaDB 벡터 저장소 |
| `tests/` | 테스트 코드 |

## 현재 구현된 기능 (v1)

- Sendbird Webhook 기반 실시간 메시지 수신/응답
- ChromaDB 기반 RAG (FAQ 문서 검색)
- Tool Calling (주문 조회, 취소, 환불 계산, 상담원 연결)
- 사용자별 채팅 히스토리 관리
- 비동기 메시지 처리 (BackgroundTasks)
- 대시보드 (채팅 로그 조회, 피드백)

---

## v2 로드맵

기존 v1을 프로덕션급으로 고도화하는 것이 목표입니다.

| Phase | 내용 | 브랜치 | 문서 |
|-------|------|--------|------|
| Phase 0 | 환경 준비 및 현재 상태 확인 | - | [phase-0.md](phases/phase-0.md) |
| Phase 1 | 프로젝트 구조 리팩토링 | `v2/refactor-structure` | [phase-1.md](phases/phase-1.md) |
| Phase 2 | 프롬프트 외부화 (YAML) | `v2/prompt-external` | [phase-2.md](phases/phase-2.md) |
| Phase 3 | 평가 파이프라인 구축 | `v2/eval-pipeline` | [phase-3.md](phases/phase-3.md) |
| Phase 4 | Observability 강화 | `v2/observability` | [phase-4.md](phases/phase-4.md) |
| Phase 5 | CI/CD, Docker, 배포 | `v2/prompt-cicd`, `v2/cloud-deploy` | [phase-5.md](phases/phase-5.md) |

## 핵심 원칙

- 커밋 컨벤션, PR 전략 등은 [conventions.md](conventions.md) 참고
- 코드 스타일: Type Hint 필수, Ruff 포맷팅, Google Docstring
- 테스트: pytest + pytest-asyncio
