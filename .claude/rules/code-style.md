---
paths:
  - "**/*.py"
---

# Python 코드 스타일 규칙

## Type Hints
- 모든 함수의 매개변수와 반환값에 type hint를 작성합니다.
- `from __future__ import annotations`를 사용합니다.
- Optional 대신 `X | None` 문법을 사용합니다.

## 포맷팅
- Ruff를 사용합니다 (line-length: 100).
- 코드 작성 후 `ruff check --fix .` 및 `ruff format .`을 실행합니다.

## Docstring
- Google Docstring 스타일을 따릅니다.
- 모든 public 함수와 클래스에 docstring을 작성합니다.
- docstring과 주석은 한국어로 작성합니다.

```python
def process_message(message: str, user_id: str) -> dict[str, Any]:
    """사용자 메시지를 처리하고 응답을 생성합니다.

    Args:
        message: 사용자가 보낸 메시지.
        user_id: 사용자 고유 식별자.

    Returns:
        처리 결과를 담은 딕셔너리.
    """
```

## 임포트 순서
1. 표준 라이브러리
2. 서드파티 패키지
3. 로컬 모듈

## 네이밍
- 클래스: PascalCase
- 함수/변수: snake_case
- 상수: UPPER_SNAKE_CASE
- private: _leading_underscore
