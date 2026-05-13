"""부하 테스트용 JWT 토큰을 일괄 발급해 tokens.json으로 저장합니다.

k6 스크립트가 동시 사용자별로 토큰을 회전해 사용할 수 있게 N개의
(user_id, access_token) 쌍을 미리 생성한다. 발급은 HTTP `/api/auth/dev-token`
엔드포인트를 거치지 않고 동일 코드베이스의 `issue_token`을 직접 호출하므로
DEBUG 환경변수나 rate limit 영향을 받지 않는다.

JWT_SECRET_KEY는 서버 컨테이너와 동일한 .env에서 로드되어야 한다.

Usage:
    python tests/load/seed_tokens.py --count 100 --prefix loadtest
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_BASE_DIR))

from app.api.auth import issue_token  # noqa: E402


def main() -> None:
    """N개 토큰을 발급하고 tokens.json에 저장합니다."""
    parser = argparse.ArgumentParser(description="부하 테스트용 JWT 토큰 일괄 발급")
    parser.add_argument("--count", type=int, default=100, help="발급할 토큰 수 (기본 100)")
    parser.add_argument(
        "--prefix", default="loadtest", help="user_id 접두사 (기본 'loadtest')"
    )
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parent / "tokens.json"),
        help="저장 경로 (기본 tests/load/tokens.json)",
    )
    args = parser.parse_args()

    tokens: list[dict[str, str]] = []
    for i in range(args.count):
        user_id = f"{args.prefix}-{i:04d}"
        access_token, _ = issue_token(user_id)
        tokens.append({"user_id": user_id, "token": access_token})

    output_path = Path(args.output)
    output_path.write_text(json.dumps(tokens, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(tokens)}개 토큰 발급 완료 → {output_path}")


if __name__ == "__main__":
    main()
