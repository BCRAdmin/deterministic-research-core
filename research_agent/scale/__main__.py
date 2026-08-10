from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from pydantic import ValidationError

from research_agent.scale.scale_contract import (
    ScaleContractError,
    ScalePlanRequest,
    build_scale_plan,
    execute_scale_plan,
    load_scale_plan,
    save_scale_plan,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plan or execute a confirmed, sequential, zero-cost Room16 research run."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    plan_parser = commands.add_parser("plan", help="Build a non-executing plan from JSON input.")
    plan_parser.add_argument("--input", required=True, type=Path)
    execute_parser = commands.add_parser("execute", help="Execute an exact, confirmed plan.")
    execute_parser.add_argument("--plan", required=True, type=Path)
    execute_parser.add_argument("--confirm-plan-sha256", required=True)
    execute_parser.add_argument("--retry-failures", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "plan":
            request_payload = json.loads(args.input.expanduser().resolve().read_text(encoding="utf-8"))
            plan = build_scale_plan(ScalePlanRequest.model_validate(request_payload))
            path = save_scale_plan(plan)
            result = {"status": "planned_not_executed", "planPath": str(path), **plan}
        else:
            plan = load_scale_plan(args.plan)
            state = execute_scale_plan(
                plan,
                confirmation_sha256=args.confirm_plan_sha256,
                sec_user_agent=os.getenv("ROOM16_SEC_USER_AGENT", ""),
                retry_failures=args.retry_failures,
            )
            result = state
    except (OSError, json.JSONDecodeError, ValidationError, ScaleContractError, RuntimeError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
