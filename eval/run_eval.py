"""Golden QA Set 기반 에이전트 평가 스크립트."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

_BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BASE_DIR))
load_dotenv()

_judge_llm: ChatOpenAI | None = None


def _get_judge_llm() -> ChatOpenAI:
    """LLM-as-Judge 인스턴스를 캐싱하여 반환합니다."""
    global _judge_llm
    if _judge_llm is None:
        _judge_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
    return _judge_llm


def _load_golden_set() -> list[dict]:
    """Golden QA Set JSON 파일을 로드합니다."""
    path = _BASE_DIR / "eval" / "golden_qa.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _init_agent() -> None:
    """평가용 에이전트를 초기화합니다."""
    from app.agent.rag import agent_executor_base, initialize_rag

    if agent_executor_base is None:
        initialize_rag()


def _call_agent(user_query: str) -> dict:
    """에이전트를 호출하고 응답과 중간 단계를 반환합니다.

    Returns:
        {"output": str, "tools_called": list[str]} 형태의 딕셔너리.
    """
    from app.agent.rag import agent_executor_base

    if agent_executor_base is None:
        return {"output": "에이전트 초기화 실패", "tools_called": []}

    # return_intermediate_steps를 임시 활성화하여 tool 호출 정보를 얻음
    original_flag = agent_executor_base.return_intermediate_steps
    try:
        agent_executor_base.return_intermediate_steps = True
        result = agent_executor_base.invoke({"input": user_query})
    finally:
        agent_executor_base.return_intermediate_steps = original_flag

    # intermediate_steps에서 호출된 tool 이름 추출
    tools_called = []
    for step in result.get("intermediate_steps", []):
        if isinstance(step, (list, tuple)) and len(step) >= 1:
            action = step[0]
            if hasattr(action, "tool"):
                tools_called.append(action.tool)

    return {"output": result.get("output", ""), "tools_called": tools_called}


def _judge_tool_accuracy(expected_tool: str | None, tools_called: list[str]) -> float:
    """올바른 도구가 호출되었는지 평가합니다.

    Returns:
        1.0 (정확) 또는 0.0 (부정확).
    """
    if expected_tool is None:
        # 도구 호출이 없어야 하는 케이스: search_faq는 허용 (정보 조회는 자연스러운 동작)
        non_faq_tools = [t for t in tools_called if t != "search_faq"]
        return 1.0 if not non_faq_tools else 0.0
    return 1.0 if expected_tool in tools_called else 0.0


def _judge_with_llm(
    user_query: str,
    reference_answer: str,
    actual_answer: str,
    criteria: list[str],
) -> dict[str, float]:
    """LLM-as-Judge로 응답 품질을 평가합니다.

    Args:
        user_query: 사용자 질문.
        reference_answer: 기대 답변.
        actual_answer: 실제 에이전트 답변.
        criteria: 평가 기준 목록.

    Returns:
        기준별 점수 딕셔너리 (0.0 ~ 1.0).
    """
    judge_llm = _get_judge_llm()

    criteria_descriptions = {
        "faithfulness": "응답이 제공된 정보에 근거하며 허위 정보를 포함하지 않는 정도",
        "relevance": "응답이 사용자 질문에 적절하고 관련성 있는 정도",
    }

    eval_criteria = [c for c in criteria if c in criteria_descriptions]
    if not eval_criteria:
        return {}

    criteria_text = "\n".join(f"- {c}: {criteria_descriptions[c]}" for c in eval_criteria)

    prompt = f"""다음 고객 지원 대화에서 에이전트 응답의 품질을 평가해주세요.

[사용자 질문]
{user_query}

[기대 답변]
{reference_answer}

[실제 에이전트 답변]
{actual_answer}

[평가 기준]
{criteria_text}

각 기준에 대해 0.0 (매우 나쁨) ~ 1.0 (매우 좋음) 사이의 점수를 매겨주세요.
반드시 아래 JSON 형식으로만 응답하세요:
{{"scores": {{{", ".join(f'"{c}": <점수>' for c in eval_criteria)}}}}}"""

    response = judge_llm.invoke(prompt)
    try:
        parsed = json.loads(response.content)
        return {c: float(parsed["scores"].get(c, 0.0)) for c in eval_criteria}
    except (json.JSONDecodeError, KeyError, TypeError):
        return {c: 0.0 for c in eval_criteria}


def _evaluate_test_case(tc: dict) -> dict:
    """단일 테스트 케이스를 평가합니다."""
    print(f"\n{'=' * 60}")
    print(f"[{tc['id']}] ({tc['category']}) {tc['user_query'][:50]}")
    print(f"{'=' * 60}")

    result = _call_agent(tc["user_query"])
    actual_output = result["output"]
    tools_called = result["tools_called"]

    print(f"  도구 호출: {tools_called}")
    print(f"  응답: {actual_output[:100]}...")

    scores: dict[str, float] = {}

    # Tool accuracy 평가
    if "tool_accuracy" in tc["eval_criteria"]:
        scores["tool_accuracy"] = _judge_tool_accuracy(tc["expected_tool"], tools_called)

    # LLM-as-Judge 평가
    llm_criteria = [c for c in tc["eval_criteria"] if c != "tool_accuracy"]
    if llm_criteria and tc.get("reference_answer"):
        llm_scores = _judge_with_llm(
            tc["user_query"],
            tc["reference_answer"],
            actual_output,
            llm_criteria,
        )
        scores.update(llm_scores)

    avg_score = sum(scores.values()) / len(scores) if scores else 0.0
    print(f"  점수: {scores} (평균: {avg_score:.2f})")

    return {
        "id": tc["id"],
        "category": tc["category"],
        "user_query": tc["user_query"],
        "actual_output": actual_output,
        "tools_called": tools_called,
        "scores": scores,
        "avg_score": avg_score,
    }


def _print_report(results: list[dict]) -> dict:
    """카테고리별 점수 리포트를 출력하고 요약을 반환합니다."""
    print("\n")
    print("=" * 60)
    print("  평가 결과 리포트")
    print("=" * 60)

    # 카테고리별 집계
    category_scores: dict[str, list[float]] = defaultdict(list)
    all_scores: list[float] = []

    for r in results:
        category_scores[r["category"]].append(r["avg_score"])
        all_scores.append(r["avg_score"])

    summary = {}
    for category, scores in sorted(category_scores.items()):
        avg = sum(scores) / len(scores) if scores else 0.0
        summary[category] = avg
        print(f"\n  [{category.upper()}] 평균: {avg:.2f} ({len(scores)}개 케이스)")
        for r in results:
            if r["category"] == category:
                status = "PASS" if r["avg_score"] >= 0.7 else "FAIL"
                print(f"    {r['id']}: {r['avg_score']:.2f} [{status}]")

    overall = sum(all_scores) / len(all_scores) if all_scores else 0.0
    summary["overall"] = overall
    print(f"\n  전체 평균: {overall:.2f}")
    print("=" * 60)

    return summary


def run_evaluation() -> dict:
    """전체 평가를 실행하고 요약을 반환합니다."""
    golden_set = _load_golden_set()
    print(f"Golden QA Set 로드 완료: {len(golden_set)}개 테스트 케이스")

    _init_agent()

    results = []
    for tc in golden_set:
        result = _evaluate_test_case(tc)
        results.append(result)

    summary = _print_report(results)

    # 결과를 JSON 파일로 저장
    output_path = _BASE_DIR / "eval" / "results.json"
    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n상세 결과 저장: {output_path}")

    return summary


if __name__ == "__main__":
    summary = run_evaluation()
    sys.exit(0 if summary.get("overall", 0) >= 0.7 else 1)
