#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from research_agent.ops.quellwert_productization_hardening import (
    ProductizationAuditPaths,
    build_productization_audit,
    write_productization_audit,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the local Quellwert productization hardening audit.")
    parser.add_argument(
        "--closure-root",
        default="outputs/quellwert_room16_operating/closure_sprint_2026-05-28",
    )
    parser.add_argument(
        "--launch-pack-root",
        default="outputs/quellwert_room16_operating/launch_pack_2026-05-27",
    )
    parser.add_argument(
        "--output-root",
        default="outputs/quellwert_room16_operating/productization_hardening_2026-05-28",
    )
    parser.add_argument("--json-only", action="store_true")
    args = parser.parse_args(argv)

    paths = ProductizationAuditPaths(
        closure_root=Path(args.closure_root),
        launch_pack_root=Path(args.launch_pack_root),
        output_root=Path(args.output_root),
    )
    audit = build_productization_audit(paths)
    json_path, md_path = write_productization_audit(audit, output_root=paths.output_root)

    result = {
        "status": audit["status"],
        "json_path": str(json_path),
        "md_path": str(md_path),
        "external_launch_go": audit["external_launch_go"],
        "p0_open_gated_count": len(audit.get("p0_open_gated") or []),
        "p1_open_gated_count": len(audit.get("p1_open_gated") or []),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.json_only:
        return 0
    return 0 if audit["status"] != "local_hardening_failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
