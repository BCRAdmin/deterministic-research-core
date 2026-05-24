#!/usr/bin/env python3
"""Build the local Agent OS readiness pack.

This script writes review artifacts only. It does not install external skills,
read secret values, change runtime config, or create automations.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research_agent.ops.automation_cards import (
    default_job_cards,
    render_job_cards_markdown,
    validate_job_card,
)
from research_agent.ops.coding_guardrails import (
    default_coding_guardrails,
    render_coding_guardrails_markdown,
    validate_coding_guardrails,
)
from research_agent.ops.deliverable_swarm import (
    default_deliverable_lanes,
    default_delivery_contracts,
    render_deliverable_swarm_markdown,
    validate_deliverable_swarm,
)
from research_agent.ops.guardrails import render_findings_markdown, scan_paths
from research_agent.ops.memory_inbox import (
    build_search_index,
    collect_memory_candidates,
    render_candidates_markdown,
    search_index,
)
from research_agent.ops.operator_inbox import (
    build_operator_inbox_items,
    render_operator_inbox_markdown,
    validate_operator_inbox,
)
from research_agent.ops.past_blocks_closure import (
    DEFAULT_LIONCOM_ROOT,
    build_past_blocks_closure_report,
    render_past_blocks_closure_markdown,
)
from research_agent.ops.portfolio_surface_audit import (
    audit_portfolio_surfaces,
    render_portfolio_surface_canvas,
    render_portfolio_surface_markdown,
)
from research_agent.ops.readiness import (
    DEFAULT_HERMES_HOME,
    DEFAULT_OPENCLAW_HOME,
    DEFAULT_VAULT,
    build_capability_matrix,
    build_openclaw_migration_dry_run,
    render_readiness_markdown,
)
from research_agent.ops.review_workbenches import (
    build_guardrail_policy_gate_matrix,
    build_memory_promotion_workbench,
    render_guardrail_policy_gate_matrix,
    render_memory_promotion_workbench,
)
from research_agent.ops.skill_registry import build_skill_registry, render_registry_markdown
from research_agent.ops.terminal_backends import (
    default_backend_specs,
    render_terminal_backends_markdown,
    validate_backend_specs,
)
from research_agent.ops.vault_semantic_audit import (
    audit_vault_semantic_ownership,
    render_vault_semantic_audit_markdown,
)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


GERMAN_VISIBLE_TEXT_REPLACEMENTS = {
    "Faehigkeit": "Fähigkeit",
    "Faehigkeiten": "Fähigkeiten",
    "Naechste": "Nächste",
    "naechste": "nächste",
    "Pruefung": "Prüfung",
    "Prueffrage": "Prüffrage",
    "pruefen": "prüfen",
    "prueft": "prüft",
    "Gepruefte": "Geprüfte",
    "ausfuehren": "ausführen",
    "Ausfuehrung": "Ausführung",
    "fuehren": "führen",
    "gefuehrt": "geführt",
    "Fuehrung": "Führung",
    "fuehrend": "führend",
    "Flaeche": "Fläche",
    "flaeche": "fläche",
    "Oberflaeche": "Oberfläche",
    "oberflaeche": "oberfläche",
    "Stärtflaechen": "Startflächen",
    "Startflaechen": "Startflächen",
    "Entitaet": "Entität",
    "Entitaeten": "Entitäten",
    "Saetze": "Sätze",
    "frueher": "früher",
    "muessen": "müssen",
    "Aenderungen": "Änderungen",
    "Aenderung": "Änderung",
    "aendern": "ändern",
    "Vorgaenger": "Vorgänger",
    "spaetere": "spätere",
    "Gruene": "Grüne",
    "gruen": "grün",
    "Gruens": "Grüns",
    "traegt": "trägt",
    "groesseren": "größeren",
    "groesserem": "größerem",
    "groessere": "größere",
    "kleinstes pruefbares": "kleinstes prüfbares",
    "Quellenpruefung": "Quellenprüfung",
    "Uebernahme": "Übernahme",
    "Uebernahmeregel": "Übernahmeregel",
    "Ueber": "Über",
    "ueber": "über",
    "Fuer": "Für",
    "fuer": "für",
    "oeffentliche": "öffentliche",
    "Veroeffentlichung": "Veröffentlichung",
    "Veroeffentlichungen": "Veröffentlichungen",
    "woechentlich": "wöchentlich",
    "beduerftig": "bedürftig",
    "Luecken": "Lücken",
    "Vertraege": "Verträge",
    "Vorschlaege": "Vorschläge",
    "Eintraege": "Einträge",
    "Gueltig": "Gültig",
    "gueltig": "gültig",
    "Prioritaet": "Priorität",
    "duerfen": "dürfen",
    "Rueckstandsarbeit": "Rückstandsarbeit",
    "zusaetzliche": "zusätzliche",
}

VISIBLE_GERMAN_ASCII_PATTERNS = tuple(GERMAN_VISIBLE_TEXT_REPLACEMENTS)


def normalize_visible_german_markdown(content: str) -> str:
    """Normalize visible German prose while preserving code spans and fences."""

    normalized_lines: list[str] = []
    in_fence = False
    for line in content.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            normalized_lines.append(line)
            continue
        if in_fence:
            normalized_lines.append(line)
            continue
        parts = line.split("`")
        for index in range(0, len(parts), 2):
            segment = parts[index]
            for old, new in GERMAN_VISIBLE_TEXT_REPLACEMENTS.items():
                segment = segment.replace(old, new)
            parts[index] = segment
        normalized_lines.append("`".join(parts))
    return "".join(normalized_lines)


def find_visible_german_markdown_findings(paths: list[Path]) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for path in paths:
        in_fence = False
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            visible = "".join(line.split("`")[0::2])
            for pattern in VISIBLE_GERMAN_ASCII_PATTERNS:
                if pattern in visible:
                    findings.append(
                        {
                            "file": str(path),
                            "line": line_no,
                            "pattern": pattern,
                            "text": visible.strip()[:180],
                        }
                    )
    return findings


def write_text(path: Path, content: str) -> None:
    if path.suffix == ".md":
        content = normalize_visible_german_markdown(content)
    path.write_text(content, encoding="utf-8")


def run_all(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    out = Path(args.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    vault = Path(args.vault).resolve()
    lioncom_root = Path(args.lioncom_root).expanduser().resolve()
    openclaw_home = Path(args.openclaw_home).expanduser().resolve()
    hermes_home = Path(args.hermes_home).expanduser().resolve()

    guardrail_targets = args.guardrail_target or [
        "docs",
        "scripts",
    ]
    guardrail_findings = scan_paths(root, guardrail_targets, scan_type="all")
    write_json(out / "GUARDRAIL_SCAN.json", {"findings": [f.to_dict() for f in guardrail_findings]})
    write_text(out / "GUARDRAIL_SCAN.md", render_findings_markdown("Guardrail Scan", guardrail_findings))

    coding_guardrails = default_coding_guardrails()
    coding_guardrails_validation = validate_coding_guardrails(coding_guardrails)
    write_json(
        out / "AGENT_CODING_GUARDRAILS.json",
        {
            "contract": coding_guardrails.to_dict(),
            "validation": coding_guardrails_validation.to_dict(),
        },
    )
    write_text(
        out / "AGENT_CODING_GUARDRAILS.md",
        render_coding_guardrails_markdown(coding_guardrails, coding_guardrails_validation),
    )

    skill_records = build_skill_registry(root)
    write_json(out / "SKILL_REGISTRY.json", {"records": [r.to_dict() for r in skill_records]})
    write_text(out / "SKILL_REGISTRY.md", render_registry_markdown(skill_records))

    memory_candidates = collect_memory_candidates(root)
    write_json(
        out / "MEMORY_INBOX_CANDIDATES.json",
        {"candidates": [c.to_dict() for c in memory_candidates]},
    )
    write_text(out / "MEMORY_INBOX_CANDIDATES.md", render_candidates_markdown(memory_candidates))
    memory_promotion_batches = build_memory_promotion_workbench(memory_candidates)
    write_json(
        out / "MEMORY_PROMOTION_WORKBENCH.json",
        {"batches": [batch.to_dict() for batch in memory_promotion_batches]},
    )
    write_text(
        out / "MEMORY_PROMOTION_WORKBENCH.md",
        render_memory_promotion_workbench(memory_promotion_batches),
    )

    guardrail_policy_gates = build_guardrail_policy_gate_matrix(guardrail_findings)
    write_json(
        out / "GUARDRAIL_POLICY_GATE_MATRIX.json",
        {"gates": [gate.to_dict() for gate in guardrail_policy_gates]},
    )
    write_text(
        out / "GUARDRAIL_POLICY_GATE_MATRIX.md",
        render_guardrail_policy_gate_matrix(guardrail_policy_gates),
    )

    indexed_rows = build_search_index(root, out / "SESSION_SEARCH.sqlite")
    search_hits = search_index(out / "SESSION_SEARCH.sqlite", args.search_query, limit=10)
    write_json(
        out / "SESSION_SEARCH_SAMPLE.json",
        {
            "query": args.search_query,
            "indexed_rows": indexed_rows,
            "hits": [h.to_dict() for h in search_hits],
        },
    )

    deliverable_lanes = default_deliverable_lanes(root)
    delivery_contracts = default_delivery_contracts(root)
    deliverable_validation = validate_deliverable_swarm(
        deliverable_lanes,
        delivery_contracts,
        root,
    )
    write_json(
        out / "DELIVERABLE_SWARM_CONTRACT.json",
        {
            "lanes": [lane.to_dict() for lane in deliverable_lanes],
            "delivery_contracts": [contract.to_dict() for contract in delivery_contracts],
            "validation": deliverable_validation.to_dict(),
        },
    )
    write_text(
        out / "DELIVERABLE_SWARM_CONTRACT.md",
        render_deliverable_swarm_markdown(
            deliverable_lanes,
            delivery_contracts,
            deliverable_validation,
        ),
    )

    vault_semantic_audit = audit_vault_semantic_ownership(vault)
    write_json(out / "VAULT_SEMANTIC_OWNERSHIP_AUDIT.json", vault_semantic_audit.to_dict())
    write_text(
        out / "VAULT_SEMANTIC_OWNERSHIP_AUDIT.md",
        render_vault_semantic_audit_markdown(vault_semantic_audit),
    )

    job_cards = default_job_cards(root)
    validations = [validate_job_card(card, root) for card in job_cards]
    write_json(
        out / "AUTOMATION_JOB_CARDS.json",
        {
            "cards": [card.to_dict() for card in job_cards],
            "validations": [validation.to_dict() for validation in validations],
        },
    )
    write_text(out / "AUTOMATION_JOB_CARDS.md", render_job_cards_markdown(job_cards, validations))

    backend_specs = default_backend_specs(root)
    backend_validations = validate_backend_specs(backend_specs, root)
    write_json(
        out / "TERMINAL_BACKENDS.json",
        {
            "backends": [spec.to_dict() for spec in backend_specs],
            "validations": [validation.to_dict() for validation in backend_validations],
        },
    )
    write_text(
        out / "TERMINAL_BACKENDS.md",
        render_terminal_backends_markdown(backend_specs, backend_validations),
    )

    portfolio_audit = audit_portfolio_surfaces(vault)
    write_json(out / "PORTFOLIO_PRODUCT_SURFACE_AUDIT.json", portfolio_audit.to_dict())
    write_text(out / "PORTFOLIO_PRODUCT_SURFACE_AUDIT.md", render_portfolio_surface_markdown(portfolio_audit))
    write_text(out / "PORTFOLIO_PRODUCT_SURFACE_MAP.canvas", render_portfolio_surface_canvas(portfolio_audit))

    past_blocks_closure = build_past_blocks_closure_report(root, vault, lioncom_root)
    write_json(out / "PAST_BLOCKS_CLOSURE.json", past_blocks_closure.to_dict())
    write_text(out / "PAST_BLOCKS_CLOSURE.md", render_past_blocks_closure_markdown(past_blocks_closure))

    inbox_items = build_operator_inbox_items(
        root,
        guardrail_count=len(guardrail_findings),
        memory_candidate_count=len(memory_candidates),
        skill_record_count=len(skill_records),
        automation_cards_valid=all(validation.valid for validation in validations),
        deliverable_contract_valid=deliverable_validation.valid,
        deliverable_lane_count=len(deliverable_lanes),
        coding_guardrails_valid=coding_guardrails_validation.valid,
        coding_guardrail_count=len(coding_guardrails.items),
        vault_semantic_audit_valid=vault_semantic_audit.valid,
        vault_semantic_findings=len(vault_semantic_audit.findings),
    )
    inbox_validation = validate_operator_inbox(inbox_items)
    write_json(
        out / "OPERATOR_INBOX.json",
        {
            "items": [item.to_dict() for item in inbox_items],
            "validation": inbox_validation.to_dict(),
        },
    )
    write_text(out / "OPERATOR_INBOX.md", render_operator_inbox_markdown(inbox_items, inbox_validation))

    capability_checks = build_capability_matrix(root, vault, openclaw_home, hermes_home)
    migration_items = build_openclaw_migration_dry_run(openclaw_home)
    write_json(
        out / "AGENT_OS_READINESS_REPORT.json",
        {
            "capabilities": [check.to_dict() for check in capability_checks],
            "openclaw_migration_dry_run": [item.to_dict() for item in migration_items],
        },
    )
    write_text(out / "AGENT_OS_READINESS_REPORT.md", render_readiness_markdown(capability_checks, migration_items))

    markdown_language_findings = find_visible_german_markdown_findings(
        sorted(out.glob("*.md"))
    )

    summary = {
        "status": "completed",
        "output_dir": str(out),
        "guardrail_findings": len(guardrail_findings),
        "coding_guardrails": len(coding_guardrails.items),
        "coding_guardrails_valid": coding_guardrails_validation.valid,
        "skill_records": len(skill_records),
        "memory_candidates": len(memory_candidates),
        "memory_promotion_batches": len(memory_promotion_batches),
        "guardrail_policy_gates": len(guardrail_policy_gates),
        "session_search_indexed_rows": indexed_rows,
        "automation_cards": len(job_cards),
        "automation_cards_valid": all(validation.valid for validation in validations),
        "deliverable_lanes": len(deliverable_lanes),
        "delivery_contracts": len(delivery_contracts),
        "deliverable_contract_valid": deliverable_validation.valid,
        "portfolio_surface_projects": len(portfolio_audit.results),
        "portfolio_surface_valid": portfolio_audit.valid,
        "portfolio_surface_findings": len(portfolio_audit.findings),
        "past_blocks_closure_valid": past_blocks_closure.valid,
        "remaining_past_blocks": len(past_blocks_closure.remaining_past_blocks),
        "vault_semantic_valid": vault_semantic_audit.valid,
        "vault_semantic_findings": len(vault_semantic_audit.findings),
        "vault_semantic_viewpoints": len(vault_semantic_audit.viewpoints),
        "terminal_backends": len(backend_specs),
        "terminal_backends_valid": all(validation.valid for validation in backend_validations),
        "operator_inbox_items": len(inbox_items),
        "operator_inbox_valid": inbox_validation.valid,
        "generated_markdown_language_findings": len(markdown_language_findings),
        "generated_markdown_language_valid": not markdown_language_findings,
    }
    if markdown_language_findings:
        write_json(out / "GENERATED_MARKDOWN_LANGUAGE_FINDINGS.json", {"findings": markdown_language_findings})
    else:
        stale_findings = out / "GENERATED_MARKDOWN_LANGUAGE_FINDINGS.json"
        if stale_findings.exists():
            stale_findings.write_text('{"findings": []}\n', encoding="utf-8")
    write_json(out / "RUN_SUMMARY.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    ready = (
        all(validation.valid for validation in validations)
        and coding_guardrails_validation.valid
        and deliverable_validation.valid
        and all(validation.valid for validation in backend_validations)
        and portfolio_audit.valid
        and past_blocks_closure.valid
        and vault_semantic_audit.valid
        and inbox_validation.valid
        and not markdown_language_findings
    )
    return 0 if ready else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Build safe local Agent OS readiness artifacts.")
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--output-dir", default="outputs/agent_os_readiness", help="Output directory.")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT), help="Human Overview vault path.")
    parser.add_argument("--lioncom-root", default=str(DEFAULT_LIONCOM_ROOT), help="LIONCOM repository root.")
    parser.add_argument("--openclaw-home", default=str(DEFAULT_OPENCLAW_HOME), help="OpenClaw home path.")
    parser.add_argument("--hermes-home", default=str(DEFAULT_HERMES_HOME), help="Hermes home path.")
    parser.add_argument("--search-query", default="Hermes OR OpenClaw OR Vivi", help="Sample session search query.")
    parser.add_argument("--guardrail-target", action="append", help="Target path for guardrail scanning.")
    args = parser.parse_args()
    return run_all(args)


if __name__ == "__main__":
    raise SystemExit(main())
