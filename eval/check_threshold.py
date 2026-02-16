"""평가 결과의 품질 임계치를 검사하는 스크립트."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent.parent

# 카테고리별 최소 임계치
THRESHOLDS: dict[str, float] = {
    "faq": 0.7,
    "tool_calling": 0.7,
    "edge_case": 0.6,
    "adversarial": 0.6,
    "overall": 0.7,
}


def check_threshold(results_path: Path | None = None) -> bool:
    """평가 결과가 임계치를 충족하는지 검사합니다.

    Args:
        results_path: 결과 JSON 파일 경로. None이면 기본 경로 사용.

    Returns:
        모든 임계치를 충족하면 True.
    """
    if results_path is None:
        results_path = _BASE_DIR / "eval" / "results.json"

    if not results_path.exists():
        print(f"결과 파일이 없습니다: {results_path}")
        print("먼저 python eval/run_eval.py를 실행하세요.")
        return False

    results: list[dict] = json.loads(results_path.read_text(encoding="utf-8"))

    # 카테고리별 평균 계산
    from collections import defaultdict

    category_scores: dict[str, list[float]] = defaultdict(list)
    all_scores: list[float] = []

    for r in results:
        category_scores[r["category"]].append(r["avg_score"])
        all_scores.append(r["avg_score"])

    category_avgs: dict[str, float] = {}
    for category, scores in category_scores.items():
        category_avgs[category] = sum(scores) / len(scores) if scores else 0.0

    overall = sum(all_scores) / len(all_scores) if all_scores else 0.0
    category_avgs["overall"] = overall

    # 임계치 검사
    all_passed = True
    print("=" * 50)
    print("  품질 임계치 검사 결과")
    print("=" * 50)

    for category, threshold in THRESHOLDS.items():
        actual = category_avgs.get(category, 0.0)
        passed = actual >= threshold
        status = "PASS" if passed else "FAIL"
        print(f"  {category:15s}: {actual:.2f} / {threshold:.2f} [{status}]")
        if not passed:
            all_passed = False

    print("=" * 50)
    final_status = "PASS" if all_passed else "FAIL"
    print(f"  최종 결과: [{final_status}]")
    print("=" * 50)

    return all_passed


if __name__ == "__main__":
    passed = check_threshold()
    sys.exit(0 if passed else 1)
