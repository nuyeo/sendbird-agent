"""토큰 비용 최적화 before/after 비교 스크립트.

baseline-summary.json(최초 측정값)과 현재 실행 결과를 비교해
품질 회귀 및 비용 절감 효과를 측정합니다.

사용법:
    python eval/cost_eval.py

출력:
    eval/cost-eval-result.json  — 비교 결과
    eval/baseline-summary.json  — 원본 베이스라인 (덮어쓰지 않고 복원됨)
    eval/after-summary.json     — 이번 실행 결과 (참조용)
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

_BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BASE_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

# Windows psycopg async 호환
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# 품질 회귀 허용 임계값: 최적화 후 점수가 이 값 이상 하락하면 실패 처리
_QUALITY_REGRESSION_THRESHOLD = 0.05

_BASELINE_PATH = _BASE_DIR / "eval" / "baseline-summary.json"
_AFTER_PATH = _BASE_DIR / "eval" / "after-summary.json"
_RESULT_PATH = _BASE_DIR / "eval" / "cost-eval-result.json"


def _load_baseline() -> dict[str, Any]:
    """baseline-summary.json을 로드합니다.

    Returns:
        베이스라인 딕셔너리.

    Raises:
        FileNotFoundError: 베이스라인 파일이 없을 때.
    """
    if not _BASELINE_PATH.exists():
        raise FileNotFoundError("baseline-summary.json 이 없습니다. 먼저 run_eval.py를 실행하세요.")
    return json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))


def _delta(before: float | int, after: float | int) -> str:
    """변화량을 "+N%" 또는 "-N%" 형식으로 반환합니다."""
    if before == 0:
        return "N/A"
    pct = (after - before) / before * 100
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}%"


def _safe_get(d: dict[str, Any], *keys: str, default: Any = 0) -> Any:
    """중첩 딕셔너리에서 안전하게 값을 조회합니다.

    Args:
        d: 대상 딕셔너리.
        *keys: 순서대로 적용할 키 목록.
        default: 키가 없거나 타입 불일치 시 반환할 기본값.

    Returns:
        조회된 값 또는 default.
    """
    current: Any = d
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
    return current


def _compare(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """before/after 요약을 비교해 변화량을 계산합니다.

    Args:
        before: 이전 baseline-summary 딕셔너리.
        after: 현재 run_eval 결과 딕셔너리.

    Returns:
        비교 결과 딕셔너리.

    Raises:
        ValueError: 필수 섹션(quality/latency_ms/cost)이 누락된 경우.
    """
    for section in ("quality", "latency_ms", "cost"):
        if section not in before or section not in after:
            raise ValueError(
                f"비교에 필요한 섹션 '{section}'이 누락됐습니다. "
                "baseline-summary.json과 after-summary.json의 형식을 확인하세요."
            )

    before_quality = _safe_get(before, "quality", "overall", default=0.0)
    after_quality = _safe_get(after, "quality", "overall", default=0.0)

    return {
        "model": after.get("model"),
        "n_cases": after.get("n_cases"),
        "quality": {
            "before_overall": before_quality,
            "after_overall": after_quality,
            "delta": _delta(before_quality, after_quality),
            "regression_ok": after_quality >= before_quality - _QUALITY_REGRESSION_THRESHOLD,
        },
        "latency_ms": {
            "before_avg": _safe_get(before, "latency_ms", "avg"),
            "after_avg": _safe_get(after, "latency_ms", "avg"),
            "delta": _delta(
                _safe_get(before, "latency_ms", "avg"),
                _safe_get(after, "latency_ms", "avg"),
            ),
            "before_p95": _safe_get(before, "latency_ms", "p95"),
            "after_p95": _safe_get(after, "latency_ms", "p95"),
        },
        "cost": {
            "before_avg_total_tokens": _safe_get(before, "cost", "avg_total_tokens"),
            "after_avg_total_tokens": _safe_get(after, "cost", "avg_total_tokens"),
            "token_delta": _delta(
                _safe_get(before, "cost", "avg_total_tokens"),
                _safe_get(after, "cost", "avg_total_tokens"),
            ),
            "before_avg_cost_usd": _safe_get(before, "cost", "avg_cost_usd"),
            "after_avg_cost_usd": _safe_get(after, "cost", "avg_cost_usd"),
            "cost_delta": _delta(
                _safe_get(before, "cost", "avg_cost_usd"),
                _safe_get(after, "cost", "avg_cost_usd"),
            ),
            "before_proj_per_1k": _safe_get(before, "cost", "projected_cost_per_1k_messages_usd"),
            "after_proj_per_1k": _safe_get(after, "cost", "projected_cost_per_1k_messages_usd"),
        },
    }


def _print_comparison(comparison: dict[str, Any]) -> None:
    """비교 결과를 사람이 읽기 쉽게 출력합니다."""
    print("\n" + "=" * 60)
    print("  비용 최적화 before/after 비교")
    print("=" * 60)

    q = comparison["quality"]
    regression_icon = "✓" if q["regression_ok"] else "✗"
    regression_msg = "통과" if q["regression_ok"] else "실패 — 품질 저하 확인 필요"
    print(f"\n  [품질] 회귀 허용치: -{_QUALITY_REGRESSION_THRESHOLD * 100:.0f}% 이내")
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

    run_evaluation()은 baseline-summary.json을 덮어쓰므로, 실행 전에 원본을 메모리에
    보존하고 실행 후 복원합니다. 새 결과는 after-summary.json에 별도 저장됩니다.

    Returns:
        품질 회귀가 없으면 0, 있으면 1.
    """
    # ── 1. 원본 베이스라인 로드 (run_evaluation 실행 전에 보존) ─────────────
    baseline = _load_baseline()
    print(
        f"베이스라인 로드 완료 (모델: {baseline.get('model')}, 케이스: {baseline.get('n_cases')})"
    )

    # ── 2. 현재 에이전트로 평가 실행 ────────────────────────────────────────
    from eval.run_eval import run_evaluation  # noqa: E402

    print("\n현재 에이전트로 평가 실행 중...")
    await run_evaluation()

    # run_evaluation()이 baseline-summary.json을 덮어씀 → 새 결과를 읽어 저장
    after = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
    _AFTER_PATH.write_text(json.dumps(after, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"현재 실행 결과 저장: {_AFTER_PATH}")

    # ── 3. 원본 베이스라인 복원 (다음 실행에서도 같은 기준선 사용) ───────────
    _BASELINE_PATH.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
    print("원본 베이스라인 복원 완료")

    # ── 4. 비교 및 출력 ──────────────────────────────────────────────────────
    comparison = _compare(baseline, after)
    _print_comparison(comparison)

    _RESULT_PATH.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n비교 결과 저장: {_RESULT_PATH}")

    return 0 if comparison["quality"]["regression_ok"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
