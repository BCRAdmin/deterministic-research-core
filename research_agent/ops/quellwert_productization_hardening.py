from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from research_agent.publishing import (
    scan_publication_policy,
    validate_artifact_state,
    validate_outcome_readiness,
    validate_publishable_source_registry,
)
from research_agent.research_core.ingestion.source_registry import load_source_registry


DEFAULT_CLOSURE_ROOT = Path("outputs/quellwert_room16_operating/closure_sprint_2026-05-28")
DEFAULT_LAUNCH_PACK_ROOT = Path("outputs/quellwert_room16_operating/launch_pack_2026-05-27")
DEFAULT_OUTPUT_ROOT = Path("outputs/quellwert_room16_operating/productization_hardening_2026-05-28")


P1_PRODUCTION_CONTROLS = [
    "branch_deploy_protection",
    "codeowners_required_reviewers",
    "environment_gates",
    "secret_hardening",
    "sast_sca_dast",
    "sbom",
    "attestations_provenance",
]

P1_OBSERVABILITY_CONTROLS = [
    "publish_events",
    "policy_violation_events",
    "freshness_lag_metric",
    "source_coverage_metric",
    "error_tracking",
    "slo_recovery_time",
]

P1_ROLLBACK_CONTROLS = [
    "unpublish_drill",
    "route_block_drill",
    "catalog_block_drill",
    "api_block_drill",
    "preview_production_separation_drill",
]


@dataclass(frozen=True)
class ProductizationAuditPaths:
    closure_root: Path = DEFAULT_CLOSURE_ROOT
    launch_pack_root: Path = DEFAULT_LAUNCH_PACK_ROOT
    output_root: Path = DEFAULT_OUTPUT_ROOT


def build_productization_audit(paths: ProductizationAuditPaths | None = None) -> dict[str, Any]:
    paths = paths or ProductizationAuditPaths()
    closure_root = paths.closure_root
    launch_pack_root = paths.launch_pack_root

    manual_decisions = _read_json(closure_root / "MANUAL_REVIEW_DECISIONS_2026-05-28.json")
    googl_review = _read_json(closure_root / "GOOGL_SOURCE_REVIEW_2026-05-28.json")
    readiness = _read_json(closure_root / "10D_OUTCOME_RUNNER_READINESS.json")
    public_gate_matrix = _read_json(launch_pack_root / "QUELLWERT_PUBLIC_GATE_MATRIX.json", default={})

    artifact_results = [
        validate_artifact_state(decision, artifact_id=f"{decision.get('ticker')}-{index}").to_dict()
        for index, decision in enumerate(manual_decisions.get("decisions") or [], 1)
    ]

    policy_docs = [
        launch_pack_root / "FOUNDING_CIRCLE_OFFER_DRAFT.md",
        launch_pack_root / "PUBLIC_SAMPLE_ANALYSIS_REVIEW.md",
    ]
    policy_results = [
        {
            "path": str(path),
            **scan_publication_policy(_read_text(path), artifact_state="public_brief").to_dict(),
        }
        for path in policy_docs
        if path.exists()
    ]

    source_registry_path = Path(str(googl_review.get("local_bundle") or "")) / "source_registry.json"
    if source_registry_path.exists():
        source_result = validate_publishable_source_registry(
            load_source_registry(source_registry_path),
            required_claims=[
                "revenue",
                "google_cloud_revenue",
                "google_cloud_growth",
                "operating_margin",
                "capex",
                "free_cash_flow",
            ],
            as_of_date=str(googl_review.get("as_of") or ""),
            max_source_age_days=30,
            require_owner=True,
        ).to_dict()
    else:
        source_result = {
            "registry_id": "GOOGL",
            "status": "blocked",
            "block_count": 1,
            "warn_count": 0,
            "findings": [
                {
                    "code": "SOURCE_REGISTRY_FILE_MISSING",
                    "severity": "block",
                    "message": "GOOGL local bundle source_registry.json was not found.",
                    "claim": None,
                    "source_id": None,
                    "found": str(source_registry_path),
                }
            ],
        }

    outcome_result = validate_outcome_readiness(readiness).to_dict()
    p1_controls = _evaluate_p1_controls(public_gate_matrix)
    p0_open = _p0_open_items(readiness=readiness, source_result=source_result)
    p1_open = _p1_open_items(p1_controls)

    status = "local_hardening_pass_external_blocked"
    if any(result["status"] == "blocked" for result in artifact_results):
        status = "local_hardening_failed"
    if any(result["status"] == "blocked" for result in policy_results):
        status = "local_hardening_failed"
    if outcome_result["status"] == "blocked":
        status = "local_hardening_failed"

    return {
        "artifact_id": "quellwert_productization_hardening_audit_2026_05_28",
        "generated_at": _utc_now(),
        "status": status,
        "state_truth": "local_ready_operator_gated_not_external_ready",
        "no_external_actions": True,
        "external_launch_go": False,
        "audit_scope": [
            "artifact_state_machine",
            "policy_as_code",
            "source_registry_claim_mapping",
            "10d_outcome_readiness",
            "manual_review_visibility_gates",
            "production_observability_rollback_control_inventory",
        ],
        "p0_closed_local": [
            "Manual-review packets are classified as internal_review/research_seed and remain blocked from public/member routing.",
            "Policy-as-code scanner is executable for public/member candidate copy.",
            "GOOGL claim-to-source registry can be checked locally against required claims.",
            "10D outcome readiness keeps the expected pending_price_data stop without synthetic prices, forward-fill or replacement dates.",
        ],
        "p0_open_gated": p0_open,
        "p1_open_gated": p1_open,
        "artifact_state_results": artifact_results,
        "policy_results": policy_results,
        "source_registry_result": source_result,
        "outcome_readiness_result": outcome_result,
        "p1_control_results": p1_controls,
        "operator_legal_data_gates_remaining": [
            "true 10D outcome on 2026-06-01 with real closes",
            "operator review of 10D artifacts",
            "legal/compliance confirmation of publication boundary and non-advice posture",
            "external URL/domain decision",
            "production controls, observability and rollback drills before any external surface",
        ],
    }


def write_productization_audit(
    audit: Mapping[str, Any],
    *,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
) -> tuple[Path, Path]:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "QUELLWERT_PRODUCTIZATION_HARDENING_AUDIT_2026-05-28.json"
    md_path = root / "QUELLWERT_PRODUCTIZATION_HARDENING_AUDIT_2026-05-28.md"
    json_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_productization_audit_markdown(audit), encoding="utf-8")
    return json_path, md_path


def render_productization_audit_markdown(audit: Mapping[str, Any]) -> str:
    lines = [
        "# Quellwert Productization Hardening Audit - 2026-05-28",
        "",
        f"- Status: `{audit['status']}`",
        f"- State truth: `{audit['state_truth']}`",
        f"- External launch go: `{str(audit['external_launch_go']).lower()}`",
        f"- No external actions: `{str(audit['no_external_actions']).lower()}`",
        "",
        "## P0 Closed Locally",
        "",
    ]
    lines.extend(f"- {item}" for item in audit.get("p0_closed_local") or [])
    lines.extend(["", "## P0 Still Gated", ""])
    lines.extend(f"- {item}" for item in audit.get("p0_open_gated") or [])
    lines.extend(["", "## P1 Still Gated", ""])
    lines.extend(f"- {item}" for item in audit.get("p1_open_gated") or [])

    lines.extend(
        [
            "",
            "## Check Summary",
            "",
            "| Check | Status | Blocks | Warnings |",
            "|---|---|---:|---:|",
        ]
    )
    for item in audit.get("artifact_state_results") or []:
        lines.append(
            f"| Artifact state `{item['artifact_id']}` | `{item['status']}` | {item['block_count']} | {item['warn_count']} |"
        )
    for item in audit.get("policy_results") or []:
        lines.append(f"| Policy `{Path(item['path']).name}` | `{item['status']}` | {item['block_count']} | {item['warn_count']} |")
    source = audit.get("source_registry_result") or {}
    lines.append(f"| Source registry `{source.get('registry_id')}` | `{source.get('status')}` | {source.get('block_count')} | {source.get('warn_count')} |")
    outcome = audit.get("outcome_readiness_result") or {}
    lines.append(f"| 10D readiness | `{outcome.get('status')}` | {outcome.get('block_count')} | {outcome.get('warn_count')} |")

    lines.extend(["", "## Remaining Operator / Legal / Data Gates", ""])
    lines.extend(f"- {item}" for item in audit.get("operator_legal_data_gates_remaining") or [])
    lines.append("")
    return "\n".join(lines)


def _evaluate_p1_controls(public_gate_matrix: Mapping[str, Any]) -> dict[str, Any]:
    existing_evidence = {
        str(gate.get("gate") or ""): str(gate.get("status") or "")
        for gate in public_gate_matrix.get("gates") or []
        if isinstance(gate, Mapping)
    }
    return {
        "status": "operator_gated",
        "production_controls": _control_rows(P1_PRODUCTION_CONTROLS, existing_evidence),
        "observability_controls": _control_rows(P1_OBSERVABILITY_CONTROLS, existing_evidence),
        "rollback_controls": _control_rows(P1_ROLLBACK_CONTROLS, existing_evidence),
    }


def _control_rows(control_ids: Sequence[str], evidence: Mapping[str, str]) -> list[dict[str, str]]:
    rows = []
    for control_id in control_ids:
        rows.append(
            {
                "control": control_id,
                "status": "missing_local_drill_evidence",
                "existing_gate_status": evidence.get(control_id, "not_present"),
                "operator_gate_required": "true",
            }
        )
    return rows


def _p0_open_items(*, readiness: Mapping[str, Any], source_result: Mapping[str, Any]) -> list[str]:
    items = [
        "No external publishable public_brief/member_brief is authorized; only internal/local-preview gating is verified.",
        "Artifact-State-Machine is implemented locally, but production UI/API/sitemap wiring still needs a dedicated integration pass before launch.",
        "Policy-as-Code is implemented locally, but must be wired into every future publish/public/member route before any external surface.",
    ]
    if str(readiness.get("status")) == "pending_price_data":
        items.append("10D outcome remains pending_price_data until real 2026-06-01 ticker and benchmark closes exist.")
    if source_result.get("status") != "pass":
        items.append("Source Registry still needs owner/freshness/provenance completion before external publishability.")
    return items


def _p1_open_items(p1_controls: Mapping[str, Any]) -> list[str]:
    controls = []
    for group in ("production_controls", "observability_controls", "rollback_controls"):
        controls.extend(row["control"] for row in p1_controls.get(group) or [])
    return [
        "Production controls still need evidence: " + ", ".join(P1_PRODUCTION_CONTROLS) + ".",
        "Observability still needs evidence: " + ", ".join(P1_OBSERVABILITY_CONTROLS) + ".",
        "Rollback/Kill-Switch still needs drill evidence: " + ", ".join(P1_ROLLBACK_CONTROLS) + ".",
        f"Total P1 control evidence gaps: {len(controls)}.",
    ]


def _read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
