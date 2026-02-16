---
paths:
  - "tests/**"
---

# 테스트 규칙

## 프레임워크
- pytest + pytest-asyncio를 사용합니다.
- 설정 파일: `pytest.ini`

## 파일 네이밍
- 테스트 파일: `test_*.py`
- 테스트 함수: `test_` prefix

## 비동기 테스트
```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result is not None
```

## 테스트 실행
```bash
# 전체 테스트
pytest

# 특정 파일
pytest tests/test_specific.py

# 특정 테스트
pytest tests/test_specific.py::test_function_name

# verbose 모드
pytest -v
```

## 규칙
- 외부 API 호출은 반드시 mock 처리합니다.
- 각 테스트는 독립적이어야 하며 다른 테스트에 의존하면 안 됩니다.
- fixture를 적극 활용합니다.
- `.env`의 실제 API 키를 테스트에서 사용하지 않습니다.
