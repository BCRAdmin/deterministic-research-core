#!/usr/bin/env python3
"""Run the Vega vault semantic ownership audit."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research_agent.ops.vault_semantic_audit import (
    DEFAULT_VAULT,
    audit_to_json,
    audit_vault_semantic_ownership,
    render_vault_semantic_audit_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit semantic ownership drift in the Vega vault.")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT), help="Human Overview vault path.")
    parser.add_argument("--output-dir", default="outputs/vault_semantic_audit", help="Output directory.")
    args = parser.parse_args()

    out = Path(args.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    audit = audit_vault_semantic_ownership(Path(args.vault))
    (out / "VAULT_SEMANTIC_OWNERSHIP_AUDIT.json").write_text(audit_to_json(audit), encoding="utf-8")
    (out / "VAULT_SEMANTIC_OWNERSHIP_AUDIT.md").write_text(
        render_vault_semantic_audit_markdown(audit),
        encoding="utf-8",
    )
    print(audit_to_json(audit), end="")
    return 0 if audit.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
