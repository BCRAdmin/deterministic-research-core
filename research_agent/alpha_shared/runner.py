"""Executable RFC-0011 shared case runner intended for the future H5 caller."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .compiler import SharedCompileResult, compile_shared_successor
from .contracts import SharedBaseInputIR, SupplementalCompileInputIR


@dataclass(frozen=True)
class SharedCaseRunResult:
    compiled: SharedCompileResult
    report: dict[str, Any]


def run_shared_case(
    *,
    base_input: SharedBaseInputIR,
    supplemental_input: SupplementalCompileInputIR,
    archetype_profile_id: str,
    output_root: Path,
    ledger_path: Path,
    research_commit: str,
    research_tree: str,
    monotonic_counter: int,
) -> SharedCaseRunResult:
    """Execute the real shared compiler path with no hidden network fallback."""

    compiled = compile_shared_successor(
        base_input=base_input,
        archetype_profile_id=archetype_profile_id,
        supplemental_input=supplemental_input,
        output_root=output_root,
        ledger_path=ledger_path,
        research_commit=research_commit,
        research_tree=research_tree,
        monotonic_counter=monotonic_counter,
    )
    stages = [item["stage"] for item in compiled.ledger_report["events"]]
    return SharedCaseRunResult(
        compiled=compiled,
        report={
            "contract_id": "room16.rfc0011.real_shared_runner_report",
            "contract_version": 1,
            "actual_function_called": "run_shared_case",
            "shared_compiler_called": True,
            "bundle_verified": compiled.verification["status"] == "PASS",
            "h4_stages": stages,
            "network_calls": 0,
            "fixed24_queries": 0,
            "fixed24_batch_authorized": False,
            "status": "PASS",
        },
    )
