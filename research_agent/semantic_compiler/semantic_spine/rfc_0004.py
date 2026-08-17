"""Public RFC-0004 semantic contract integrity surface.

The accepted RFC-0003 PassKernel chain remains the execution mechanism.  This
module names the additive RFC-0004 entry point and contracts without creating
a second orchestrator.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from research_agent.compiler_foundation.contracts import PassExecutionRecord
from research_agent.compiler_foundation.kernel import PassKernel

from .rfc_0003 import (
    PASS_MANIFEST_PATH,
    POLICY_PARAMETER_DEFINITIONS,
    RFC0004_INVARIANTS,
    _items,
    load_initial_state,
    replay_rfc_0003_archive,
)
from .contracts import SourceInputIR
from .table_grammar import discover_tables, parse_payload


def replay_rfc_0004_archive(
    *, archive: Path, replay_records: tuple[PassExecutionRecord, ...] | None = None,
    kernel: PassKernel | None = None,
) -> dict[str, Any]:
    """Execute RFC-0004 through the one accepted Foundation PassKernel."""

    return replay_rfc_0003_archive(
        archive=archive, replay_records=replay_records, kernel=kernel,
    )


def iter_canonical_table_artifacts(archive: Path) -> Iterator[dict[str, Any]]:
    """Reproduce every content-addressed table artifact from a frozen input."""

    import base64

    state, _ = load_initial_state(archive)
    sources = _items(state, "source_inputs", SourceInputIR)
    raw = state.artifacts["raw_payloads"]
    for source in sources:
        _, candidates = parse_payload(source, base64.b64decode(raw[source.ir_sha256]))
        discovery = discover_tables(source, candidates)
        for table in discovery.tables:
            yield table.model_dump(mode="json")


__all__ = [
    "PASS_MANIFEST_PATH",
    "POLICY_PARAMETER_DEFINITIONS",
    "RFC0004_INVARIANTS",
    "iter_canonical_table_artifacts",
    "replay_rfc_0004_archive",
]
