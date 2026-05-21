"""Readiness and migration dry-run surfaces for the local agent stack."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


DEFAULT_OPENCLAW_HOME = Path.home() / ".openclaw"
DEFAULT_HERMES_HOME = Path.home() / ".hermes"
DEFAULT_VAULT = Path("/Users/BjornRosinger/Documents/Obsidian/Test Vaul Privat/Human Overview")


@dataclass(frozen=True)
class CapabilityCheck:
    capability: str
    status: str
    evidence: str
    next_action: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class MigrationItem:
    source: str
    target: str
    status: str
    secret_sensitive: bool
    action: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _exists(path: Path) -> str:
    return "present" if path.exists() else "missing"


def build_capability_matrix(
    root: Path,
    vault: Path = DEFAULT_VAULT,
    openclaw_home: Path = DEFAULT_OPENCLAW_HOME,
    hermes_home: Path = DEFAULT_HERMES_HOME,
) -> list[CapabilityCheck]:
    root = root.resolve()
    checks = [
        CapabilityCheck(
            "openclaw_runtime_status",
            "reference_only_until_preflight",
            f"{vault / 'Canonical/Systems/System - OpenClaw.md'} = {_exists(vault / 'Canonical/Systems/System - OpenClaw.md')}; {openclaw_home} = {_exists(openclaw_home)}",
            "Vor aktiver OpenClaw-Nutzung expliziten Pfad-/Config-/Service-/Smoke-Preflight ausfuehren.",
        ),
        CapabilityCheck(
            "hermes_pattern_benchmark",
            "captured",
            str(vault / "DreamFactory System/Agent Stack/Hermes Agent Benchmark - 2026-05-21.md"),
            "Nur als Musterquelle nutzen; keine externe Runtime installieren.",
        ),
        CapabilityCheck(
            "openswarm_deliverable_benchmark",
            "captured",
            str(
                vault
                / "DreamFactory System/Agent Stack/OpenSwarm Benchmark - 2026-05-21.md"
            ),
            "OpenSwarm als Deliverable-Lane-Muster nutzen, nicht als Runtime-Paket.",
        ),
        CapabilityCheck(
            "external_skill_intake",
            "active",
            str(root / "docs/skills/EXTERNAL_SKILL_INTAKE_SOP.md"),
            "Alle externen Skills hinter Quellenpruefung, Risikoklasse und Operator-Gate halten.",
        ),
        CapabilityCheck(
            "skill_registry_v1",
            "implemented_local_artifact",
            str(root / "outputs/agent_os_readiness/SKILL_REGISTRY.md"),
            "Ueber scripts/ops/agent_os_readiness.py aktualisieren.",
        ),
        CapabilityCheck(
            "memory_inbox_and_search",
            "implemented_local_artifact",
            str(root / "outputs/agent_os_readiness/MEMORY_INBOX_CANDIDATES.md"),
            "Kandidaten manuell in Obsidian-Routen promoten; Index ist nur lokale Suche.",
        ),
        CapabilityCheck(
            "automation_job_cards",
            "implemented_proposal_artifact",
            str(root / "outputs/agent_os_readiness/AUTOMATION_JOB_CARDS.md"),
            "Echte App-Automationen nur nach Operator-Review erstellen.",
        ),
        CapabilityCheck(
            "deliverable_swarm_contract",
            "implemented_local_artifact",
            str(root / "outputs/agent_os_readiness/DELIVERABLE_SWARM_CONTRACT.md"),
            "Vor neuen Runtime-Rechten als sichtbaren Lane-/Output-Vertrag nutzen.",
        ),
        CapabilityCheck(
            "guardrails_as_code",
            "implemented_local_scan",
            str(root / "outputs/agent_os_readiness/GUARDRAIL_SCAN.md"),
            "Block-/High-Funde vor Runtime-Erweiterung als Gates behandeln.",
        ),
        CapabilityCheck(
            "multi_channel_gateway",
            "local_operator_inbox_contract_implemented",
            str(root / "outputs/agent_os_readiness/OPERATOR_INBOX.md"),
            "Zuerst lokale Inbox nutzen, bevor ein externes Chat-Gateway erwogen wird.",
        ),
        CapabilityCheck(
            "terminal_backend_abstraction",
            "local_and_docker_contracts_implemented",
            str(root / "outputs/agent_os_readiness/TERMINAL_BACKENDS.md"),
            "Docker nicht starten und Ausfuehrungsrechte nicht ohne Operator-Gate erweitern.",
        ),
        CapabilityCheck(
            "hermes_home_presence",
            "observed_only",
            f"{hermes_home} = {_exists(hermes_home)}",
            "Hermes-Secrets nicht ohne explizites Operator-Gate lesen oder importieren.",
        ),
    ]
    return checks


def build_openclaw_migration_dry_run(
    openclaw_home: Path = DEFAULT_OPENCLAW_HOME,
    staging_label: str = "lioncom_agent_os_staging",
) -> list[MigrationItem]:
    """Return a no-write migration map. Secret values are never read."""

    known_items: Sequence[tuple[str, str, bool]] = (
        ("SOUL.md", "persona/SOUL.md", False),
        ("AGENTS.md", "workspace/AGENTS.md", False),
        ("MEMORY.md", "memory/imported_MEMORY.md", False),
        ("USER.md", "memory/imported_USER.md", False),
        ("skills", "skills/openclaw-imports", False),
        ("openclaw.json", "config/openclaw.imported.json", True),
        (".env", "secrets/.env.redacted_manifest_only", True),
        ("allowlist.json", "security/command_allowlist.imported.json", False),
    )
    items: list[MigrationItem] = []
    for source_name, target_name, secret_sensitive in known_items:
        source = openclaw_home / source_name
        exists = source.exists()
        if secret_sensitive and exists:
            action = "manifest_only_requires_explicit_secret_gate"
        elif exists:
            action = "eligible_for_reviewed_import"
        else:
            action = "no_source_found"
        items.append(
            MigrationItem(
                source=str(source),
                target=f"{staging_label}/{target_name}",
                status="present" if exists else "missing",
                secret_sensitive=secret_sensitive,
                action=action,
            )
        )
    return items


def render_readiness_markdown(
    checks: Sequence[CapabilityCheck],
    migration_items: Sequence[MigrationItem],
) -> str:
    lines = [
        "# Agent-OS-Readiness-Bericht",
        "",
        "Dieser Bericht sammelt sichere Hermes-/OpenClaw-inspirierte Verbesserungen, ohne externes Runtime-Verhalten zu aktivieren.",
        "",
        "## Faehigkeitsmatrix",
        "",
        "| Faehigkeit | Status | Evidenz | Naechste Aktion |",
        "| --- | --- | --- | --- |",
    ]
    for check in checks:
        lines.append(
            f"| `{check.capability}` | `{check.status}` | `{check.evidence}` | {check.next_action} |"
        )
    lines.extend(
        [
            "",
            "## OpenClaw-Migrations-Trockenlauf",
            "",
            "Dieser Trockenlauf kopiert keine Dateien. Secret-sensitive Quellen werden nur als Manifest gefuehrt.",
            "",
            "| Quelle | Ziel | Status | Secret-sensitiv | Aktion |",
            "| --- | --- | --- | ---: | --- |",
        ]
    )
    for item in migration_items:
        lines.append(
            f"| `{item.source}` | `{item.target}` | `{item.status}` | "
            f"{str(item.secret_sensitive).lower()} | `{item.action}` |"
        )
    return "\n".join(lines) + "\n"
