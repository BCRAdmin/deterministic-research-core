#!/usr/bin/env python3
"""Repo entrypoint for the local Vega multi-agent context-pack builder."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


SKILL_SCRIPT = Path.home() / ".codex/skills/vega-multi-agent-research/scripts/context_pack_builder.py"


def main() -> int:
    if not SKILL_SCRIPT.exists():
        print(f"missing skill script: {SKILL_SCRIPT}", file=sys.stderr)
        return 1
    sys.argv[0] = str(SKILL_SCRIPT)
    runpy.run_path(str(SKILL_SCRIPT), run_name="__main__")
    return 0


if __name__ == "__main__":
    sys.exit(main())
