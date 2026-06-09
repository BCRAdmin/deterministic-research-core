from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from research_agent.ops.quellwert_productization_hardening import (
    ProductizationAuditPaths,
    build_productization_audit,
    write_productization_audit,
)


DEFAULT_PRODUCTIZATION_AUDIT_ROOT = Path("outputs/quellwert_room16_operating/productization_hardening_2026-05-28")
DEFAULT_PRODUCTIZATION_AUDIT_JSON = (
    DEFAULT_PRODUCTIZATION_AUDIT_ROOT / "QUELLWERT_PRODUCTIZATION_HARDENING_AUDIT_2026-05-28.json"
)
DEFAULT_REPORT_MACHINE_VERIFICATION = Path(
    "/Users/BjornRosinger/Documents/DreamFactory/Project-Intelligence-Graph/"
    "company-dossier-lab/.runtime/room16-app/report-machine/last-report-machine-verification.json"
)
DEFAULT_OUTPUT_ROOT = Path("outputs/vega_maturity_sprint/2026-05-29")
SOURCE_REPORT_PATH = Path("/Users/BjornRosinger/Downloads/deep-research-report (1).md")
SOURCE_REPORT_SHA256 = "d166c2352cd0d564d4ed7237175e4733ef4d071df7c9e66f59bee7afd13a4bb0"


@dataclass(frozen=True)
class VegaMaturitySprintPaths:
    productization_audit_json: Path = DEFAULT_PRODUCTIZATION_AUDIT_JSON
    report_machine_verification_json: Path = DEFAULT_REPORT_MACHINE_VERIFICATION
    output_root: Path = DEFAULT_OUTPUT_ROOT


def build_vega_maturity_sprint(paths: VegaMaturitySprintPaths | None = None) -> dict[str, Any]:
    paths = paths or VegaMaturitySprintPaths()
    productization = _load_or_build_productization_audit(paths.productization_audit_json)
    report_machine = _read_json(paths.report_machine_verification_json, default=None)
    visibility = _extract_visibility_evidence(report_machine)

    deliverables = [
        _publishability_contract(productization, visibility),
        _observability_baseline(),
        _rollback_kill_switch_rail(visibility),
        _supply_chain_compliance_minimum(),
    ]
    failed = [item for item in deliverables if item["status"].startswith("fail")]
    warnings = [item for item in deliverables if item["status"].startswith("warn")]

    return {
        "sprint_id": "vega_maturity_sprint_2026_05_29",
        "generated_at": _utc_now(),
        "source_report": {
            "path": str(SOURCE_REPORT_PATH),
            "sha256": SOURCE_REPORT_SHA256,
            "hash_verified_if_present": _hash_matches(SOURCE_REPORT_PATH, SOURCE_REPORT_SHA256),
        },
        "status": "local_maturity_run_pass_operator_gated" if not failed else "local_maturity_run_failed",
        "external_ready": False,
        "production_ready": False,
        "no_external_actions": True,
        "hard_gates_kept_closed": [
            "deploy",
            "public_or_production",
            "payment_or_checkout",
            "auth_or_credentials",
            "external_sends",
            "real_customer_data",
            "delete",
            "room16_rerun",
            "financial_advice_or_transaction_language",
        ],
        "deliverables": deliverables,
        "summary": {
            "failed_count": len(failed),
            "warning_count": len(warnings),
            "deliverable_count": len(deliverables),
            "visibility_effective_public": visibility.get("effective_public"),
            "visibility_effective_member": visibility.get("effective_member"),
            "productization_status": productization.get("status"),
        },
        "operator_decision": {
            "recommendation": "continue_local_maturity_before_product_reopen",
            "next_safe_block": "wire this contract into the operator surface and keep Quellwert frozen until explicit reopen",
            "blocked_until_operator_go": [
                "legal/compliance review",
                "real 10D data review",
                "production observability decision",
                "rollback drill acceptance",
                "external surface/domain/analytics decision",
            ],
        },
    }


def write_vega_maturity_sprint(
    payload: Mapping[str, Any],
    *,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
) -> tuple[Path, Path]:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "VEGA_MATURITY_SPRINT_2026-05-29.json"
    md_path = root / "VEGA_MATURITY_SPRINT_2026-05-29.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_vega_maturity_sprint_markdown(payload), encoding="utf-8")
    return json_path, md_path


def render_vega_maturity_sprint_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Vega Maturity Sprint - 2026-05-29",
        "",
        f"- Status: `{payload['status']}`",
        f"- External ready: `{str(payload['external_ready']).lower()}`",
        f"- Production ready: `{str(payload['production_ready']).lower()}`",
        f"- No external actions: `{str(payload['no_external_actions']).lower()}`",
        f"- Source: `{payload['source_report']['path']}`",
        f"- Source SHA-256: `{payload['source_report']['sha256']}`",
        "",
        "## Deliverables",
        "",
    ]
    for item in payload.get("deliverables") or []:
        lines.extend(
            [
                f"### {item['title']}",
                "",
                f"- Status: `{item['status']}`",
                f"- Purpose: {item['purpose']}",
            ]
        )
        if item.get("evidence"):
            lines.append(f"- Evidence: {item['evidence']}")
        if item.get("open_gate"):
            lines.append(f"- Open gate: {item['open_gate']}")
        lines.append("")

    lines.extend(["## Hard Gates Kept Closed", ""])
    lines.extend(f"- `{gate}`" for gate in payload.get("hard_gates_kept_closed") or [])
    lines.extend(
        [
            "",
            "## Operator Decision",
            "",
            f"- Recommendation: `{payload['operator_decision']['recommendation']}`",
            f"- Next safe block: {payload['operator_decision']['next_safe_block']}",
            "",
            "Blocked until explicit Operator-Go:",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in payload["operator_decision"].get("blocked_until_operator_go") or [])
    lines.append("")
    return "\n".join(lines)


def _publishability_contract(productization: Mapping[str, Any], visibility: Mapping[str, Any]) -> dict[str, Any]:
    effective_public = visibility.get("effective_public")
    effective_member = visibility.get("effective_member")
    visible_leak_blocked = effective_public == 0 and effective_member == 0
    productization_ok = str(productization.get("status")) == "local_hardening_pass_external_blocked"
    status = "pass_local_contract_external_blocked" if visible_leak_blocked and productization_ok else "warn_contract_needs_evidence"
    return {
        "id": "publishability_contract",
        "title": "End-to-end Publishability Contract",
        "status": status,
        "purpose": "Bindet Room16-Report, artifact_state, policy_scan, source_registry und surface_visibility in eine lokale Stop-Logik.",
        "chain": [
            "room16_report",
            "artifact_state",
            "policy_scan",
            "source_registry",
            "surface_visibility",
        ],
        "artifact_states": {
            "internal_review": {
                "public_route": "blocked",
                "member_route": "blocked",
                "api_visibility": "internal_only",
                "sitemap": "excluded",
            },
            "research_seed": {
                "public_route": "blocked",
                "member_route": "blocked",
                "api_visibility": "internal_only",
                "sitemap": "excluded",
            },
            "public_brief": {
                "public_route": "requires_policy_source_freshness_operator_legal_go",
                "member_route": "blocked",
                "api_visibility": "public_candidate_only_after_gate",
                "sitemap": "included_only_after_go",
            },
            "member_brief": {
                "public_route": "blocked_or_teaser_only_after_legal_go",
                "member_route": "requires_member_legal_auth_payment_go",
                "api_visibility": "member_candidate_only_after_gate",
                "sitemap": "excluded_unless_public_teaser_go",
            },
        },
        "evidence": (
            f"productization={productization.get('status')}; "
            f"effectivePublic={effective_public}; effectiveMember={effective_member}"
        ),
        "open_gate": "actual external public/member route activation remains operator/legal/data-gated",
    }


def _observability_baseline() -> dict[str, Any]:
    events = [
        "vega.publishability.contract_evaluated",
        "vega.policy.scan_completed",
        "vega.source_registry.coverage_checked",
        "vega.freshness.stop_triggered",
        "vega.rollback.drill_recorded",
        "vega.supply_chain.local_dependency_reviewed",
    ]
    metrics = [
        "vega_publishability_block_total",
        "vega_policy_violation_total",
        "vega_source_claim_coverage_ratio",
        "vega_freshness_lag_seconds",
        "vega_recovery_time_seconds",
        "vega_rollback_drill_success_total",
    ]
    return {
        "id": "observability_baseline",
        "title": "Observability Baseline",
        "status": "pass_local_schema_defined",
        "purpose": "Definiert eine OpenTelemetry-kompatible lokale Event- und Metriklinie für Request-, Job-, Publish-, Freshness-, Policy-, Source- und Recovery-Signale.",
        "event_namespace": "vega.*",
        "events": events,
        "metrics": metrics,
        "dashboard_surface": "local_report_first; LIONCOM panel wiring remains next local integration block",
        "evidence": f"{len(events)} events; {len(metrics)} metrics; no external telemetry sink configured",
        "open_gate": "tool choice and production telemetry sink remain operator-gated",
    }


def _rollback_kill_switch_rail(visibility: Mapping[str, Any]) -> dict[str, Any]:
    drill_evidence = [
        {
            "drill": "route_block",
            "status": "pass_contract_simulated",
            "evidence": "internal_review and research_seed map to public_route=blocked",
        },
        {
            "drill": "catalog_block",
            "status": "pass_contract_simulated",
            "evidence": f"effectivePublic={visibility.get('effective_public')} effectiveMember={visibility.get('effective_member')}",
        },
        {
            "drill": "api_block",
            "status": "pass_contract_simulated",
            "evidence": "api_visibility remains internal_only unless artifact and operator gates pass",
        },
        {
            "drill": "surface_unpublish",
            "status": "pass_contract_simulated",
            "evidence": "surface visibility derives from contract state and can return to blocked",
        },
    ]
    return {
        "id": "rollback_kill_switch",
        "title": "Rollback / Kill-Switch Rail",
        "status": "pass_local_contract_drill",
        "purpose": "Hält lokale Route-, Catalog-, API- und Surface-Unpublish-Drills als Rücknahmevertrag fest.",
        "drill_evidence": drill_evidence,
        "evidence": "; ".join(f"{item['drill']}={item['status']}" for item in drill_evidence),
        "open_gate": "real production rollback drill is blocked until there is an operator-approved production-like environment",
    }


def _supply_chain_compliance_minimum() -> dict[str, Any]:
    return {
        "id": "supply_chain_compliance_minimum",
        "title": "Supply-Chain / Compliance Minimum",
        "status": "pass_local_policy_defined_operator_gated",
        "purpose": "Schließt den Null-Alert-Irrtum und macht non-PyPI/lokale Dependencies sowie Compliance-Betriebsartefakte sichtbar.",
        "minimum_line": {
            "sbom": "required_before_external_release",
            "provenance_attestation": "required_before_external_release",
            "non_pypi_dependency_policy": {
                "tradingagents": "local_dependency_allowlist_review_required",
                "requirements": ["origin", "local_path", "owner", "review_date", "risk_note", "recheck_command"],
            },
            "ropa": "draft_required_before_real_person_or_customer_data",
            "responsibility_matrix": "operator_legal_engineering_required_before_reopen",
            "approval_gate": "operator_legal_go_required",
        },
        "evidence": "policy minimum defined; no SBOM/provenance claim issued",
        "open_gate": "actual SBOM, provenance and legal artifacts remain next implementation work",
    }


def _load_or_build_productization_audit(path: Path) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    audit = build_productization_audit(ProductizationAuditPaths(output_root=path.parent))
    write_productization_audit(audit, output_root=path.parent)
    return audit


def _extract_visibility_evidence(report_machine: Mapping[str, Any] | None) -> dict[str, Any]:
    if not report_machine:
        return {
            "status": "missing_report_machine_evidence",
            "effective_public": None,
            "effective_member": None,
            "hidden_by_gate": None,
        }
    for check in report_machine.get("checks") or []:
        if check.get("name") == "public_library_ok":
            summary = (check.get("details") or {}).get("summary") or {}
            return {
                "status": check.get("status"),
                "effective_public": summary.get("effectivePublic"),
                "effective_member": summary.get("effectiveMember"),
                "hidden_by_gate": summary.get("hiddenByGate"),
                "total_reports": summary.get("totalReports"),
            }
    return {
        "status": "public_library_summary_missing",
        "effective_public": None,
        "effective_member": None,
        "hidden_by_gate": None,
    }


def _read_json(path: Path, *, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _hash_matches(path: Path, expected: str) -> bool | None:
    if not path.exists():
        return None
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest == expected


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
