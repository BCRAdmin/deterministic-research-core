from __future__ import annotations

import difflib


def unified_report_diff(original_markdown: str, final_markdown: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            original_markdown.splitlines(),
            final_markdown.splitlines(),
            fromfile="original_report.md",
            tofile="final_report.md",
            lineterm="",
        )
    )
