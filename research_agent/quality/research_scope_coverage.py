"""Separate material-source completeness from generated-claim evidence coverage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


SCOPE_COVERAGE_CONTRACT_ID = "room16.research_scope_coverage"
SCOPE_COVERAGE_CONTRACT_VERSION = 1
REQUIRED_SCOPE_IDS = {
    "issuer_identity",
    "financial_statements",
    "latest_reporting_period",
    "results_and_guidance",
    "material_events",
    "transactions_and_financing",
    "legal_and_contingencies",
    "risk_disclosures",
    "price_history",
    "catalyst_calendar",
}
COMPLETE_STATUSES = {"complete", "complete_no_candidates", "not_applicable"}


def build_research_scope_coverage(
    *,
    ticker: str,
    as_of_date: str,
    jurisdiction: str,
    scopes: list[dict[str, Any]],
) -> dict[str, Any]:
    by_id = {
        str(item.get("scope_id") or ""): item
        for item in scopes
        if isinstance(item, Mapping)
    }
    missing = sorted(REQUIRED_SCOPE_IDS - set(by_id))
    incomplete = sorted(
        scope_id
        for scope_id, item in by_id.items()
        if scope_id in REQUIRED_SCOPE_IDS
        and str(item.get("status") or "") not in COMPLETE_STATUSES
    )
    blocking = [f"missing:{scope_id}" for scope_id in missing] + [
        f"incomplete:{scope_id}" for scope_id in incomplete
    ]
    return {
        "contract_id": SCOPE_COVERAGE_CONTRACT_ID,
        "contract_version": SCOPE_COVERAGE_CONTRACT_VERSION,
        "ticker": ticker.strip().upper(),
        "as_of_date": as_of_date,
        "jurisdiction": jurisdiction.strip().upper(),
        "required_scope_ids": sorted(REQUIRED_SCOPE_IDS),
        "all_required_scopes_complete": not blocking,
        "blocking_scope_gaps": blocking,
        "scopes": scopes,
        "semantic_note": (
            "This contract measures whether required source domains were searched "
            "and dispositioned. Generated-claim evidence coverage is a separate metric."
        ),
    }


def save_research_scope_coverage(
    payload: Mapping[str, Any], path: str | Path
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return target


def verify_research_scope_coverage(payload: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if (
        payload.get("contract_id") != SCOPE_COVERAGE_CONTRACT_ID
        or payload.get("contract_version") != SCOPE_COVERAGE_CONTRACT_VERSION
    ):
        failures.append("scope_contract_identity")
    scopes = payload.get("scopes")
    scopes = scopes if isinstance(scopes, list) else []
    ids = [
        str(item.get("scope_id") or "")
        for item in scopes
        if isinstance(item, Mapping)
    ]
    if len(ids) != len(set(ids)) or "" in ids:
        failures.append("scope_ids_unique")
    missing = sorted(REQUIRED_SCOPE_IDS - set(ids))
    if missing:
        failures.append("required_scopes_present")
    incomplete = [
        str(item.get("scope_id") or "")
        for item in scopes
        if isinstance(item, Mapping)
        and str(item.get("scope_id") or "") in REQUIRED_SCOPE_IDS
        and str(item.get("status") or "") not in COMPLETE_STATUSES
    ]
    if incomplete:
        failures.append("required_scopes_complete")
    derived_gaps = [f"missing:{scope_id}" for scope_id in missing] + [
        f"incomplete:{scope_id}" for scope_id in sorted(incomplete)
    ]
    if payload.get("blocking_scope_gaps") != derived_gaps:
        failures.append("scope_gate_consistency")
    if payload.get("all_required_scopes_complete") is not (not derived_gaps):
        failures.append("scope_permission_consistency")
    return {
        "status": "pass" if not failures else "fail",
        "verified": not failures,
        "blocking_failures": failures,
        "blocking_scope_gaps": derived_gaps,
    }
