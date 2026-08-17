from __future__ import annotations

import argparse
import json
import sys

from pydantic import ValidationError

from research_agent.current.runner import (
    CurrentResearchError,
    request_from_environment,
    run_current_research,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a current, deterministic Room16 authority bundle."
    )
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--date", required=True, dest="as_of_date")
    parser.add_argument("--jurisdiction", default=None)
    parser.add_argument("--isin", default=None)
    parser.add_argument("--exchange", default=None)
    parser.add_argument("--wkn", default=None)
    parser.add_argument("--emit-compiler-artifact-bundle", action="store_true")
    args = parser.parse_args()
    try:
        request = request_from_environment(
            args.ticker,
            args.as_of_date,
            jurisdiction=args.jurisdiction,
            isin=args.isin,
            exchange=args.exchange,
            wkn=args.wkn,
            emit_compiler_artifact_bundle=args.emit_compiler_artifact_bundle,
        )
        result = run_current_research(request)
    except (ValidationError, CurrentResearchError, RuntimeError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "error": str(exc),
                    "ticker": args.ticker.strip().upper(),
                    "as_of_date": args.as_of_date,
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
