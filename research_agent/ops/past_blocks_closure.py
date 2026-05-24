"""Closure guard for historical Vega/LIONCOM backlog blocks."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Sequence


DEFAULT_VAULT = Path("/Users/BjornRosinger/Documents/Obsidian/Test Vaul Privat/Human Overview")
DEFAULT_LIONCOM_ROOT = Path("/Users/BjornRosinger/Documents/DreamFactory/LIONCOM")


@dataclass(frozen=True)
class PastBlockClosureCheck:
    check_id: str
    valid: bool
    detail: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class PastBlocksClosureReport:
    valid: bool
    remaining_past_blocks: tuple[str, ...]
    operator_gates: tuple[str, ...]
    monitoring_windows: tuple[str, ...]
    checks: tuple[PastBlockClosureCheck, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _check_file_contains(path: Path, tokens: Sequence[str], check_id: str) -> PastBlockClosureCheck:
    text = _read(path)
    missing = [token for token in tokens if token not in text]
    return PastBlockClosureCheck(
        check_id=check_id,
        valid=not missing,
        detail=str(path) if not missing else f"{path}: missing {', '.join(missing)}",
    )


def build_past_blocks_closure_report(
    root: Path,
    vault: Path = DEFAULT_VAULT,
    lioncom_root: Path = DEFAULT_LIONCOM_ROOT,
) -> PastBlocksClosureReport:
    root = root.resolve()
    vault = vault.resolve()
    lioncom_root = lioncom_root.resolve()

    review_queue = vault / "Review Queue.md"
    review_text = _read(review_queue)

    remaining: list[str] = []
    if "- Status: `still_open_low_noise`" in review_text or "- Status: `still_open`" in review_text:
        remaining.append("review_queue_still_open_status")
    if "- Status: `proposed_review_only`" in review_text:
        remaining.append("semantic_ownership_only_proposed")

    checks = [
        _check_file_contains(
            review_queue,
            (
                "implemented_claim_start_snapshot",
                "implemented_report_only_guard",
                "## No Remaining Past Blocks",
            ),
            "review_queue_closure_status",
        ),
        _check_file_contains(
            lioncom_root / "mission-control-board/lib/services/autonomyService.ts",
            (
                "buildModelRouteSnapshotAtClaimStart",
                "modelRouteSnapshotAtClaimStart",
                "PATHS.VIVI_MODEL_ROUTE_STATUS",
            ),
            "lioncom_claim_start_snapshot_service",
        ),
        _check_file_contains(
            lioncom_root / "scripts/run_local_duo_loop.sh",
            (
                "CLAIM_MODEL_ROUTE_SNAPSHOT_JSON",
                "Claim-Start Model Route Snapshot",
                "claimModelRouteSnapshotAtClaimStart",
            ),
            "lioncom_runner_snapshot_propagation",
        ),
        _check_file_contains(
            lioncom_root / "mission-control-board/docs/vivi-model-route-snapshot-closure-2026-05-21.md",
            ("implemented_claim_start_snapshot", "Existing pre-change claims are not retroactively rewritten"),
            "lioncom_snapshot_closure_doc",
        ),
        _check_file_contains(
            root / "outputs/agent_os_readiness/VAULT_SEMANTIC_OWNERSHIP_AUDIT.md",
            ("report-only", "python3 scripts/ops/vault_semantic_audit.py"),
            "agent_os_vault_semantic_audit_artifact",
        ),
        _check_file_contains(
            root / "outputs/agent_os_readiness/AUTOMATION_JOB_CARDS.md",
            ("Vault Semantic Ownership", "proposed_local_review_only"),
            "agent_os_report_only_automation_card",
        ),
        _check_file_contains(
            root / "outputs/agent_os_readiness/OPERATOR_INBOX.md",
            ("vault-semantic-ownership-review", "ready_for_review"),
            "agent_os_operator_inbox_semantic_review",
        ),
        _check_file_contains(
            root / "outputs/vault_semantic_audit/VAULT_SEMANTIC_OWNERSHIP_AUDIT.md",
            ("Workflow-Regel", "report-only"),
            "standalone_semantic_audit_output",
        ),
    ]

    operator_gates = (
        "GitHub Pro / Public repo decision",
        "LIONCOM main / baseline decision",
        "Public, production, monetization and financial gates",
    )
    monitoring_windows = (
        "Utility 14-Day GSC/Event Review",
        "Quellwert / Room16 outcome and publish gates",
        "Dependabot, CI and Node maintenance",
    )
    valid = not remaining and all(check.valid for check in checks)
    return PastBlocksClosureReport(
        valid=valid,
        remaining_past_blocks=tuple(remaining),
        operator_gates=operator_gates,
        monitoring_windows=monitoring_windows,
        checks=tuple(checks),
    )


def report_to_json(report: PastBlocksClosureReport) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def render_past_blocks_closure_markdown(report: PastBlocksClosureReport) -> str:
    lines = [
        "# Past Blocks Closure",
        "",
        f"Gültig: `{str(report.valid).lower()}`",
        f"Remaining Past Blocks: `{len(report.remaining_past_blocks)}`",
        "",
        "## Checks",
        "",
        "| Check | Gültig | Detail |",
        "| --- | ---: | --- |",
    ]
    for check in report.checks:
        lines.append(f"| `{check.check_id}` | {str(check.valid).lower()} | `{check.detail}` |")

    lines.extend(["", "## Operator Gates", ""])
    for gate in report.operator_gates:
        lines.append(f"- `{gate}`")

    lines.extend(["", "## Monitoring Windows", ""])
    for window in report.monitoring_windows:
        lines.append(f"- `{window}`")

    lines.extend(
        [
            "",
            "## Regel",
            "",
            "- Alte Past-Blocks dürfen nicht wieder als Still-Open-Dirt auftauchen, wenn sie technisch geschlossen sind.",
            "- Operator Gates bleiben sichtbar und werden nicht still erledigt.",
            "- Monitoring-Fenster bleiben Datenreife, nicht Rückstandsarbeit.",
        ]
    )
    return "\n".join(lines) + "\n"
