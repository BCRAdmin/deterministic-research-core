#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
if VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research_agent.ops.vega_maturity_sprint import (
    VegaMaturitySprintPaths,
    build_vega_maturity_sprint,
    write_vega_maturity_sprint,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the local Vega maturity sprint run package.")
    parser.add_argument(
        "--productization-audit-json",
        default="outputs/quellwert_room16_operating/productization_hardening_2026-05-28/"
        "QUELLWERT_PRODUCTIZATION_HARDENING_AUDIT_2026-05-28.json",
    )
    parser.add_argument(
        "--report-machine-verification-json",
        default="/Users/BjornRosinger/Documents/DreamFactory/Project-Intelligence-Graph/"
        "company-dossier-lab/.runtime/room16-app/report-machine/last-report-machine-verification.json",
    )
    parser.add_argument("--output-root", default="outputs/vega_maturity_sprint/2026-05-29")
    args = parser.parse_args(argv)

    paths = VegaMaturitySprintPaths(
        productization_audit_json=Path(args.productization_audit_json),
        report_machine_verification_json=Path(args.report_machine_verification_json),
        output_root=Path(args.output_root),
    )
    payload = build_vega_maturity_sprint(paths)
    json_path, md_path = write_vega_maturity_sprint(payload, output_root=paths.output_root)

    print(
        json.dumps(
            {
                "status": payload["status"],
                "json_path": str(json_path),
                "md_path": str(md_path),
                "external_ready": payload["external_ready"],
                "production_ready": payload["production_ready"],
                "failed_count": payload["summary"]["failed_count"],
                "warning_count": payload["summary"]["warning_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if payload["status"] != "local_maturity_run_failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
