# Phase 3: 평가 파이프라인 구축

## 목표

Golden QA Set과 자동 평가 스크립트를 구축하여, 프롬프트나 코드 변경 시 품질을 정량적으로 측정할 수 있게 한다.

## 배경/맥락

프롬프트를 변경하거나 모델을 교체할 때, 기존 응답 품질이 유지되는지 확인할 방법이 없다. Golden QA Set 기반의 자동 평가를 통해 회귀를 방지한다.

## 요구사항

- [x] `eval/golden_qa.json` 작성 (최소 20개 테스트 케이스)
- [x] `eval/run_eval.py` 평가 실행 스크립트 구현
- [x] `eval/check_threshold.py` 품질 임계치 검사 스크립트

## 기술적 결정사항

- 평가 프레임워크: 자체 구현 (추후 ragas 연동 가능)
- 테스트 케이스 포맷: JSON
- 평가 방식:
  - **tool_accuracy**: AgentExecutor의 intermediate_steps에서 호출된 tool 이름 확인
  - **faithfulness/relevance**: LLM-as-Judge 패턴 (GPT가 reference_answer 대비 응답 품질 채점)
- tool_calling 케이스는 MOCK_DB(A101, B202, C303)에 맞춰 작성
- 에이전트 호출 시 RAG 초기화가 필요하므로 `initialize_rag()` 선행 호출

## Golden QA Set 구조

```json
[
  {
    "id": "TC-001",
    "category": "faq",
    "user_query": "환불 정책이 어떻게 되나요?",
    "expected_tool": null,
    "reference_answer": "구매 후 7일 이내 미사용 시 전액 환불 가능합니다.",
    "eval_criteria": ["faithfulness", "relevance"]
  },
  {
    "id": "TC-002",
    "category": "tool_calling",
    "user_query": "주문번호 ORD-12345 상태 알려줘",
    "expected_tool": "search_order_status",
    "reference_answer": null,
    "eval_criteria": ["tool_accuracy"]
  }
]
```

카테고리별 최소 분포:
- FAQ: 8개
- Tool Calling: 6개
- Edge Case: 3개
- Adversarial: 3개

## 평가 스크립트 참고 구현

```python
# eval/run_eval.py
import json
import asyncio
from pathlib import Path

async def run_evaluation():
    golden_set = json.loads(Path("eval/golden_qa.json").read_text())

    results = []
    for tc in golden_set:
        response = await call_agent(tc["user_query"])
        score = await judge_response(tc, response)
        results.append({"id": tc["id"], "score": score})

    print_report(results)

if __name__ == "__main__":
    asyncio.run(run_evaluation())
```

## 관련 파일

- `eval/golden_qa.json` — 신규 생성
- `eval/run_eval.py` — 신규 생성
- `eval/check_threshold.py` — 신규 생성

## 완료 기준

- Golden QA Set 20개 이상 작성
- `python eval/run_eval.py`로 평가 실행 가능
- 카테고리별 점수 리포트 출력
- `ruff check` 통과
