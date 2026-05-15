"""토큰 비용 최적화 before/after 비교 스크립트.

baseline-summary.json(Phase D 이전 측정값)과 현재 실행 결과를 비교해
품질 회귀 및 비용 절감 효과를 측정합니다.

사용법:
    python eval/cost_eval.py

출력:
    eval/cost-eval-result.json  — 비교 결과
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BASE_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

# Windows psycopg async 호환
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _load_baseline() -> dict:
    """baseline-summary.json을 로드합니다.

    Returns:
        베이스라인 딕셔너리.

    Raises:
        FileNotFoundError: 베이스라인 파일이 없을 때.
    """
    path = _BASE_DIR / "eval" / "baseline-summary.json"
    if not path.exists():
        raise FileNotFoundError("baseline-summary.json 이 없습니다. 먼저 run_eval.py를 실행하세요.")
    return json.loads(path.read_text(encoding="utf-8"))


def _delta(before: float | int, after: float | int) -> str:
    """변화량을 "+N%" 또는 "-N%" 형식으로 반환합니다."""
    if before == 0:
        return "N/A"
    pct = (after - before) / before * 100
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}%"


def _compare(before: dict, after: dict) -> dict:
    """before/after 요약을 비교해 변화량을 계산합니다.

    Args:
        before: 이전 baseline-summary 딕셔너리.
        after: 현재 run_eval 결과 딕셔너리.

    Returns:
        비교 결과 딕셔너리.
    """
    result = {
        "model": after.get("model"),
        "n_cases": after.get("n_cases"),
        "quality": {
            "before_overall": before["quality"]["overall"],
            "after_overall": after["quality"]["overall"],
            "delta": _delta(before["quality"]["overall"], after["quality"]["overall"]),
            "regression_ok": (after["quality"]["overall"] >= before["quality"]["overall"] - 0.05),
        },
        "latency_ms": {
            "before_avg": before["latency_ms"]["avg"],
            "after_avg": after["latency_ms"]["avg"],
            "delta": _delta(before["latency_ms"]["avg"], after["latency_ms"]["avg"]),
            "before_p95": before["latency_ms"]["p95"],
            "after_p95": after["latency_ms"]["p95"],
        },
        "cost": {
            "before_avg_total_tokens": before["cost"]["avg_total_tokens"],
            "after_avg_total_tokens": after["cost"]["avg_total_tokens"],
            "token_delta": _delta(
                before["cost"]["avg_total_tokens"], after["cost"]["avg_total_tokens"]
            ),
            "before_avg_cost_usd": before["cost"]["avg_cost_usd"],
            "after_avg_cost_usd": after["cost"]["avg_cost_usd"],
            "cost_delta": _delta(before["cost"]["avg_cost_usd"], after["cost"]["avg_cost_usd"]),
            "before_proj_per_1k": before["cost"]["projected_cost_per_1k_messages_usd"],
            "after_proj_per_1k": after["cost"]["projected_cost_per_1k_messages_usd"],
        },
    }
    return result


def _print_comparison(comparison: dict) -> None:
    """비교 결과를 사람이 읽기 쉽게 출력합니다."""
    print("\n" + "=" * 60)
    print("  Phase D 비용 최적화 before/after 비교")
    print("=" * 60)

    q = comparison["quality"]
    regression_icon = "✓" if q["regression_ok"] else "✗"
    regression_msg = "통과" if q["regression_ok"] else "실패 — 품질 저하 확인 필요"
    print("\n  [품질] 회귀 허용치: -5% 이내")
    print(
        f"    before: {q['before_overall']:.3f}  →  after: {q['after_overall']:.3f}  ({q['delta']})"
    )
    print(f"    회귀 검사: {regression_icon} {regression_msg}")

    lat = comparison["latency_ms"]
    print("\n  [지연]")
    print(f"    avg: {lat['before_avg']}ms → {lat['after_avg']}ms  ({lat['delta']})")
    print(f"    p95: {lat['before_p95']}ms → {lat['after_p95']}ms")

    cost = comparison["cost"]
    print("\n  [토큰/비용]")
    print(
        f"    avg tokens: {cost['before_avg_total_tokens']} → {cost['after_avg_total_tokens']}"
        f"  ({cost['token_delta']})"
    )
    print(
        f"    avg cost:   ${cost['before_avg_cost_usd']:.6f} → ${cost['after_avg_cost_usd']:.6f}"
        f"  ({cost['cost_delta']})"
    )
    print(f"    /1k msgs:   ${cost['before_proj_per_1k']:.4f} → ${cost['after_proj_per_1k']:.4f}")
    print("=" * 60)


async def main() -> int:
    """비교 평가를 실행합니다.

    Returns:
        품질 회귀가 없으면 0, 있으면 1.
    """
    baseline = _load_baseline()
    print(f"베이스라인 로드 완료 (모델: {baseline['model']}, 케이스: {baseline['n_cases']})")

    # 현재 에이전트로 평가 실행
    from eval.run_eval import run_evaluation

    print("\n현재 에이전트로 평가 실행 중...")
    await run_evaluation()

    # 방금 저장된 결과를 다시 로드해 비교
    after_path = _BASE_DIR / "eval" / "baseline-summary.json"
    after = json.loads(after_path.read_text(encoding="utf-8"))

    comparison = _compare(baseline, after)
    _print_comparison(comparison)

    output_path = _BASE_DIR / "eval" / "cost-eval-result.json"
    output_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n비교 결과 저장: {output_path}")

    return 0 if comparison["quality"]["regression_ok"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
