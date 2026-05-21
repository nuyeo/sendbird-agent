"""Golden QA Set 기반 에이전트 평가 스크립트.

품질(LLM-as-Judge 점수)뿐 아니라 케이스별 latency, OpenAI 토큰 사용량, 비용을
함께 캡처해 Phase D(토큰 비용 최적화) before/after 비교용 베이스라인을 산출한다.
집계 요약은 `eval/baseline-summary.json`으로 저장된다.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from langchain_community.callbacks import get_openai_callback
from langchain_openai import ChatOpenAI

_BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BASE_DIR))
load_dotenv()

# Windows에서 psycopg async는 SelectorEventLoop를 요구하므로 정책을 강제한다.
# 도구(search_order_status, cancel_order)가 async로 DB를 호출하기 때문에 필요.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# OpenAI 모델별 단가 (USD per 1M tokens). 가격 변동 시 여기만 갱신.
# 출처: https://openai.com/api/pricing (2024-12 기준)
_PRICING_PER_MILLION_USD: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.150, "output": 0.600},
    "gpt-4o": {"input": 2.500, "output": 10.000},
    "gpt-3.5-turbo": {"input": 0.500, "output": 1.500},
}

_judge_llm: ChatOpenAI | None = None


def _compute_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """OpenAI 호출 1회의 USD 비용을 계산합니다.

    Args:
        model: 모델 이름 (settings.llm_model 기준).
        prompt_tokens: 입력 토큰 수.
        completion_tokens: 출력 토큰 수.

    Returns:
        USD 비용. 단가표에 없는 모델이면 0.0.
    """
    pricing = _PRICING_PER_MILLION_USD.get(model)
    if pricing is None:
        return 0.0
    return (prompt_tokens * pricing["input"] + completion_tokens * pricing["output"]) / 1_000_000


def _percentile(values: list[float], p: float) -> float:
    """선형 보간 기반 백분위수를 계산합니다.

    Args:
        values: 수치 리스트.
        p: 0.0 ~ 1.0 사이의 백분위 (예: p95는 0.95).

    Returns:
        백분위 값. 빈 리스트면 0.0.
    """
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return float(sorted_vals[f])
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


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


async def _init_agent() -> None:
    """평가용 에이전트를 초기화합니다."""
    from app.agent.rag import agent_executor_base, initialize_rag

    if agent_executor_base is None:
        await initialize_rag()


async def _invoke_once(user_query: str, session_id: str | None) -> dict:
    """한 번의 invoke를 수행하고 결과/도구 호출/지연/비용을 반환합니다.

    session_id가 None이면 대화 히스토리 없는 base executor로 호출하고,
    값이 있으면 RunnableWithMessageHistory로 감싼 executor로 호출해 같은
    session_id로 호출이 누적되도록 한다 (멀티턴 평가용).
    """
    from app.agent.rag import agent_executor, agent_executor_base
    from app.config import settings

    if agent_executor_base is None or agent_executor is None:
        return {
            "output": "에이전트 초기화 실패",
            "tools_called": [],
            "latency_ms": 0,
            "token_usage": None,
            "cost_usd": 0.0,
        }

    # return_intermediate_steps는 base executor의 속성. 래핑된 executor도
    # 호출 시 동일 base를 사용하므로 base에서 토글하면 양쪽 경로 모두 반영된다.
    original_flag = agent_executor_base.return_intermediate_steps
    try:
        agent_executor_base.return_intermediate_steps = True
        start = time.perf_counter()
        with get_openai_callback() as cb:
            if session_id is None:
                result = await agent_executor_base.ainvoke({"input": user_query})
            else:
                result = await agent_executor.ainvoke(
                    {"input": user_query},
                    config={"configurable": {"session_id": session_id}},
                )
        latency_ms = round((time.perf_counter() - start) * 1000)
    finally:
        agent_executor_base.return_intermediate_steps = original_flag

    tools_called = []
    for step in result.get("intermediate_steps", []):
        if isinstance(step, (list, tuple)) and len(step) >= 1:
            action = step[0]
            if hasattr(action, "tool"):
                tools_called.append(action.tool)

    token_usage: dict[str, int] | None = None
    cost_usd = 0.0
    if cb.total_tokens > 0:
        token_usage = {
            "prompt_tokens": cb.prompt_tokens,
            "completion_tokens": cb.completion_tokens,
            "total_tokens": cb.total_tokens,
        }
        cost_usd = _compute_cost_usd(settings.llm_model, cb.prompt_tokens, cb.completion_tokens)

    return {
        "output": result.get("output", ""),
        "tools_called": tools_called,
        "latency_ms": latency_ms,
        "token_usage": token_usage,
        "cost_usd": cost_usd,
    }


async def _call_agent(user_query: str) -> dict:
    """단일턴 호출 (기존 시그니처 유지)."""
    return await _invoke_once(user_query, session_id=None)


async def _call_agent_multiturn(turns: list[str], case_id: str) -> dict:
    """멀티턴 호출. 같은 session_id로 순차 호출하고 최종 턴 결과를 점수화 대상으로 반환합니다.

    누적 token/cost는 전 턴 합산, latency는 마지막 턴 기준으로 반환한다. tools_called는
    모든 턴의 합집합이 아닌 마지막 턴 호출만 — 최종 응답이 어떤 도구로 만들어졌는지가
    멀티턴 평가의 핵심이기 때문이다. 단, expected_tool이 이전 턴 정보를 활용해 도구를
    호출하지 않고 답변하는 시나리오(TC-022 등)에서는 tool_accuracy를 부여하지 않는
    eval_criteria 구성으로 보완한다.
    """
    import uuid

    session_id = f"eval-{case_id}-{uuid.uuid4().hex[:8]}"
    last_result: dict | None = None
    cumulative_prompt = 0
    cumulative_completion = 0
    cumulative_total = 0
    cumulative_cost = 0.0

    for i, turn in enumerate(turns):
        print(f"  └ turn {i + 1}/{len(turns)}: {turn[:50]}")
        last_result = await _invoke_once(turn, session_id=session_id)
        tu = last_result.get("token_usage")
        if tu:
            cumulative_prompt += tu["prompt_tokens"]
            cumulative_completion += tu["completion_tokens"]
            cumulative_total += tu["total_tokens"]
        cumulative_cost += last_result.get("cost_usd", 0.0)

    if last_result is None:
        return {
            "output": "",
            "tools_called": [],
            "latency_ms": 0,
            "token_usage": None,
            "cost_usd": 0.0,
        }

    last_result["token_usage"] = (
        {
            "prompt_tokens": cumulative_prompt,
            "completion_tokens": cumulative_completion,
            "total_tokens": cumulative_total,
        }
        if cumulative_total > 0
        else None
    )
    last_result["cost_usd"] = cumulative_cost
    return last_result


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


async def _evaluate_test_case(tc: dict) -> dict:
    """단일 또는 멀티턴 테스트 케이스를 평가합니다.

    멀티턴 케이스(`turns` 필드 보유)는 같은 session_id로 순차 호출 후 마지막 턴을
    점수화 대상으로 삼는다. 단일턴 케이스는 기존 동작 그대로.
    """
    is_multiturn = "turns" in tc and isinstance(tc.get("turns"), list)
    if is_multiturn:
        display_query = " | ".join(tc["turns"])
    else:
        display_query = tc.get("user_query", "")

    multiturn_tag = " [multiturn]" if is_multiturn else ""
    print(f"\n{'=' * 60}")
    print(f"[{tc['id']}] ({tc['category']}){multiturn_tag} {display_query[:60]}")
    print(f"{'=' * 60}")

    if is_multiturn:
        result = await _call_agent_multiturn(tc["turns"], tc["id"])
        scoring_query = tc["turns"][-1]
    else:
        result = await _call_agent(tc["user_query"])
        scoring_query = tc["user_query"]

    actual_output = result["output"]
    tools_called = result["tools_called"]
    latency_ms = result["latency_ms"]
    token_usage = result["token_usage"]
    cost_usd = result["cost_usd"]

    print(f"  도구 호출: {tools_called}")
    print(f"  응답: {actual_output[:100]}...")
    print(f"  지연: {latency_ms}ms, 토큰: {token_usage}, 비용: ${cost_usd:.6f}")

    scores: dict[str, float] = {}

    # Tool accuracy 평가
    if "tool_accuracy" in tc["eval_criteria"]:
        scores["tool_accuracy"] = _judge_tool_accuracy(tc["expected_tool"], tools_called)

    # LLM-as-Judge 평가
    llm_criteria = [c for c in tc["eval_criteria"] if c != "tool_accuracy"]
    if llm_criteria and tc.get("reference_answer"):
        llm_scores = _judge_with_llm(
            scoring_query,
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
        "user_query": display_query,
        "actual_output": actual_output,
        "tools_called": tools_called,
        "scores": scores,
        "avg_score": avg_score,
        "latency_ms": latency_ms,
        "token_usage": token_usage,
        "cost_usd": cost_usd,
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


def _compute_baseline_summary(results: list[dict]) -> dict:
    """품질/지연/비용을 한 번에 집계한 베이스라인 요약을 반환합니다.

    Phase D before/after 비교용. 결과는 baseline-summary.json으로 저장된다.

    Args:
        results: _evaluate_test_case 반환값 리스트.

    Returns:
        품질/지연/비용 섹션을 포함하는 요약 딕셔너리.
    """
    from app.config import settings

    quality_by_category: dict[str, list[float]] = defaultdict(list)
    all_quality: list[float] = []
    latencies: list[float] = []
    prompt_tokens_list: list[int] = []
    completion_tokens_list: list[int] = []
    total_tokens_list: list[int] = []
    costs: list[float] = []

    for r in results:
        quality_by_category[r["category"]].append(r["avg_score"])
        all_quality.append(r["avg_score"])
        if r.get("latency_ms") is not None:
            latencies.append(r["latency_ms"])
        tu = r.get("token_usage")
        if tu:
            prompt_tokens_list.append(tu["prompt_tokens"])
            completion_tokens_list.append(tu["completion_tokens"])
            total_tokens_list.append(tu["total_tokens"])
        if r.get("cost_usd") is not None:
            costs.append(r["cost_usd"])

    avg_cost = sum(costs) / len(costs) if costs else 0.0

    return {
        "model": settings.llm_model,
        "n_cases": len(results),
        "quality": {
            "by_category": {c: round(sum(s) / len(s), 3) for c, s in quality_by_category.items()},
            "overall": round(sum(all_quality) / len(all_quality), 3) if all_quality else 0.0,
        },
        "latency_ms": {
            "avg": round(sum(latencies) / len(latencies)) if latencies else 0,
            "p50": round(_percentile(latencies, 0.5)),
            "p95": round(_percentile(latencies, 0.95)),
            "min": int(min(latencies)) if latencies else 0,
            "max": int(max(latencies)) if latencies else 0,
        },
        "cost": {
            "avg_prompt_tokens": (
                round(sum(prompt_tokens_list) / len(prompt_tokens_list))
                if prompt_tokens_list
                else 0
            ),
            "avg_completion_tokens": (
                round(sum(completion_tokens_list) / len(completion_tokens_list))
                if completion_tokens_list
                else 0
            ),
            "avg_total_tokens": (
                round(sum(total_tokens_list) / len(total_tokens_list)) if total_tokens_list else 0
            ),
            "avg_cost_usd": round(avg_cost, 6),
            "projected_cost_per_1k_messages_usd": round(avg_cost * 1000, 4),
            "total_cost_usd": round(sum(costs), 6),
        },
    }


def _print_baseline_summary(summary: dict) -> None:
    """베이스라인 요약을 사람이 읽기 쉽게 출력합니다."""
    print("\n" + "=" * 60)
    print("  베이스라인 요약 (Phase D before)")
    print("=" * 60)
    print(f"  모델: {summary['model']}  케이스 수: {summary['n_cases']}")

    q = summary["quality"]
    print("\n  [품질] LLM-as-Judge 점수 (0.0~1.0)")
    for cat, score in sorted(q["by_category"].items()):
        print(f"    {cat:15s}: {score:.3f}")
    print(f"    {'overall':15s}: {q['overall']:.3f}")

    lat = summary["latency_ms"]
    print("\n  [지연] 단일 invoke 기준 (ms)")
    print(f"    avg={lat['avg']}  p50={lat['p50']}  p95={lat['p95']}")
    print(f"    min={lat['min']}  max={lat['max']}")

    cost = summary["cost"]
    print("\n  [비용]")
    print(
        f"    avg tokens: prompt={cost['avg_prompt_tokens']}, "
        f"completion={cost['avg_completion_tokens']}, total={cost['avg_total_tokens']}"
    )
    print(f"    avg cost/case:        ${cost['avg_cost_usd']:.6f}")
    print(f"    projected /1k msgs:   ${cost['projected_cost_per_1k_messages_usd']:.4f}")
    print(f"    total cost this run:  ${cost['total_cost_usd']:.6f}")
    print("=" * 60)


async def run_evaluation() -> dict:
    """전체 평가를 실행하고 요약을 반환합니다."""
    golden_set = _load_golden_set()
    print(f"Golden QA Set 로드 완료: {len(golden_set)}개 테스트 케이스")

    await _init_agent()

    results = []
    for tc in golden_set:
        result = await _evaluate_test_case(tc)
        results.append(result)

    summary = _print_report(results)

    # 결과를 JSON 파일로 저장 (check_threshold.py 호환을 위해 케이스 리스트 그대로)
    output_path = _BASE_DIR / "eval" / "results.json"
    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n상세 결과 저장: {output_path}")

    # 베이스라인 요약(품질+지연+비용)을 별도 파일에 저장
    baseline = _compute_baseline_summary(results)
    _print_baseline_summary(baseline)
    summary_path = _BASE_DIR / "eval" / "baseline-summary.json"
    summary_path.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"베이스라인 요약 저장: {summary_path}")

    return summary


if __name__ == "__main__":
    summary = asyncio.run(run_evaluation())
    sys.exit(0 if summary.get("overall", 0) >= 0.7 else 1)
