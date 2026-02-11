# Phase 0: 환경 준비

## 목표

리팩토링을 시작하기 전에 환경을 세팅하고, 현재 코드가 정상 동작하는 baseline을 확인한다.

## 요구사항

- [ ] 레포 클론 및 v2 리팩토링 브랜치 생성
- [ ] Python 3.11 가상환경 세팅
- [ ] 기존 의존성 설치 및 서버 정상 실행 확인
- [ ] 기존 테스트 통과 확인

## 상세

### 브랜치 생성

```bash
git checkout -b v2/refactor-structure
```

### Python 환경

```bash
pyenv install 3.11.9
pyenv local 3.11.9
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Baseline 확인

리팩토링 중 문제가 생기면 돌아올 기준점입니다.

```bash
uvicorn main:app --reload --port 8001
pytest tests/
```

## 완료 기준

- 서버가 `http://localhost:8001`에서 정상 응답
- `pytest tests/` 전체 통과
