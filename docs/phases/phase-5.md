# Phase 5: CI/CD, Docker, 배포

## 목표

Prompt CI/CD 파이프라인, Hallucination Self-Correction, Docker 컨테이너화, 클라우드 배포를 완료한다.

## 배경/맥락

Phase 1~4에서 구축한 모듈 구조, 프롬프트 외부화, 평가 파이프라인, Observability를 기반으로 프로덕션 배포를 준비한다.

## 요구사항

### Prompt CI/CD
- [ ] GitHub Actions workflow 작성 (`prompts/` 변경 감지 → eval 자동 실행)
- [ ] 평가 점수가 임계치 미달 시 PR 블록

### Hallucination Self-Correction
- [ ] `app/evaluation/hallucination.py` — 검증 프롬프트 구현
- [ ] RAG 응답에 대한 자동 검증 파이프라인

### 운영 대시보드
- [ ] Streamlit 기반 운영 지표 대시보드 (기존 Next.js 대시보드와 별도)

### Docker & 배포
- [ ] `Dockerfile` 작성
- [ ] `docker-compose.yaml` 작성
- [ ] Cloud Run 배포 설정

## 기술적 결정사항

- CI/CD: GitHub Actions (기존 워크플로우 확장)
- 컨테이너: Docker + docker-compose
- 클라우드: Google Cloud Run (예정)
- 운영 대시보드: Streamlit (Python)

## 관련 파일

- `.github/workflows/` — CI/CD 워크플로우 추가
- `app/evaluation/hallucination.py` — 신규 생성
- `Dockerfile` — 신규 생성
- `docker-compose.yaml` — 신규 생성

## 완료 기준

- `prompts/` 파일 변경 시 자동으로 eval 실행되는 CI 파이프라인
- Docker로 로컬 실행 가능 (`docker-compose up`)
- 클라우드 배포 완료
