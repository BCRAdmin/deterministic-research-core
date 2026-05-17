from __future__ import annotations

import difflib


def unified_markdown_diff(original: str, repaired: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            original.splitlines(),
            repaired.splitlines(),
            fromfile="draft.md",
            tofile="repaired.md",
            lineterm="",
        )
    )

