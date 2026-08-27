"""Safe RFC-0011 supplemental observation to H3/H2 integration."""

from __future__ import annotations

import re
from calendar import monthrange
from datetime import date, datetime
from typing import Any

from research_agent.compiler_foundation.canonical import sha256_json

from .contracts import DocumentObservationIR, SupplementalCompileInputIR
from .metric_resolver import MetricCandidate, resolve_metric
from .period_freshness import PeriodCandidate, classify_period

SUPPLEMENTAL_SEMANTIC_REGISTRY = {
    "contract_id": "room16.rfc0011.supplemental_semantic_registry",
    "contract_version": 1,
    "profiles": {
        "production_volume": {
            "semantic_metric_id": "production_volume",
            "reported_labels": ["oil-equivalent production"],
            "allowed_units": ["KBOE_PER_DAY"],
            "allowed_duration_roles": ["STANDALONE_QUARTER", "YEAR_TO_DATE"],
            "allowed_archetype_profiles": ["energy", "generic"],
            "required_basis": ["consolidated"],
        }
    },
    "ticker_specific_profiles": False,
    "unit_conversions_allowed": False,
}
SUPPLEMENTAL_SEMANTIC_REGISTRY_SHA256 = sha256_json(SUPPLEMENTAL_SEMANTIC_REGISTRY)


def _period_bounds(text: str) -> tuple[str, str] | None:
    iso = re.fullmatch(r"(\d{4}-\d{2}-\d{2})/(\d{4}-\d{2}-\d{2})", text.strip())
    if iso:
        date.fromisoformat(iso.group(1))
        date.fromisoformat(iso.group(2))
        return iso.group(1), iso.group(2)
    match = re.fullmatch(r"(Three|Six) Months Ended ([A-Za-z]+) (\d{1,2}), (\d{4})", text.strip())
    if not match:
        return None
    months = 3 if match.group(1) == "Three" else 6
    month = datetime.strptime(match.group(2), "%B").month
    year = int(match.group(4))
    end = date(year, month, min(int(match.group(3)), monthrange(year, month)[1]))
    start_month_index = year * 12 + month - months
    start = date(start_month_index // 12, start_month_index % 12 + 1, 1)
    return start.isoformat(), end.isoformat()


def build_supplemental_semantics(
    *,
    supplemental: SupplementalCompileInputIR,
    as_of_date: str,
    filed_date: str,
    archetype_profile_id: str,
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    """Build candidates, execute H3, then resolve H2 with explicit rejects."""

    profiles = SUPPLEMENTAL_SEMANTIC_REGISTRY["profiles"]
    candidate_receipts: list[dict[str, Any]] = []
    accepted: dict[str, list[MetricCandidate]] = {}
    for observation in supplemental.observations:
        reasons: list[str] = []
        normalized_label = observation.reported_label.casefold()
        matching_profiles = [
            (profile_id, value)
            for profile_id, value in profiles.items()
            if normalized_label in {str(item).casefold() for item in value["reported_labels"]}
        ]
        profile_id, profile = matching_profiles[0] if len(matching_profiles) == 1 else ("", None)
        if not observation.trusted_numeric:
            reasons.append("UNTRUSTED_NUMERIC")
        if not isinstance(profile, dict):
            reasons.append("SEMANTIC_PROFILE_MISSING")
        else:
            if observation.reported_label.casefold() not in {
                str(item).casefold() for item in profile["reported_labels"]
            }:
                reasons.append("REPORTED_LABEL_MISMATCH")
            if archetype_profile_id not in profile["allowed_archetype_profiles"]:
                reasons.append("ARCHETYPE_PROFILE_INCOMPATIBLE")
        unit = observation.reported_unit_text_or_null
        if not unit:
            reasons.append("UNIT_BINDING_MISSING")
        elif isinstance(profile, dict) and unit not in profile["allowed_units"]:
            reasons.append("UNIT_BINDING_UNSUPPORTED")
        period = (
            _period_bounds(observation.reported_period_text_or_null)
            if observation.reported_period_text_or_null
            else None
        )
        if period is None:
            reasons.append("PERIOD_BINDING_MISSING")
        basis = observation.reported_basis_text_or_null
        if (
            isinstance(profile, dict)
            and profile.get("required_basis")
            and basis not in set(profile["required_basis"])
        ):
            reasons.append("BASIS_BINDING_MISSING")
        h3: dict[str, Any] | None = None
        candidate: MetricCandidate | None = None
        if not reasons and isinstance(profile, dict) and period is not None and unit is not None:
            h3_model = classify_period(
                PeriodCandidate(
                    candidate_id=observation.observation_id,
                    period_start=period[0],
                    period_end=period[1],
                    filed_date=filed_date,
                    as_of_date=as_of_date,
                    form="SUPPLEMENTAL",
                    cadence_profile_id=profile_id,
                    current_period_end=period[1],
                )
            )
            h3 = h3_model.model_dump(mode="json")
            h3["receipt_sha256"] = sha256_json(h3)
            if h3["duration_role"] not in profile["allowed_duration_roles"]:
                reasons.append("DURATION_ROLE_UNSUPPORTED")
            else:
                candidate = MetricCandidate(
                    candidate_id=observation.observation_id,
                    concept_or_label=observation.reported_label.casefold(),
                    source_kind="rfc0011_supplemental_evidence",
                    period_type=h3["period_type"],
                    period_role=h3["comparative_role"],
                    freshness_status=h3["freshness_status"],
                    unit=unit,
                    evidence_ids=(
                        observation.observation_sha256,
                        observation.source_document_sha256,
                        sha256_json({"locator": observation.locator}),
                    ),
                    numeric_value=observation.parsed_numeric_value_or_null,
                    semantic_metric_id=str(profile["semantic_metric_id"]),
                    semantic_role="EXACT_DIRECT",
                    aggregation_role="DIRECT_TOTAL",
                    archetype_profile_id=archetype_profile_id,
                    period_receipt_sha256=h3["receipt_sha256"],
                    inventory_sha256=supplemental.observation_set_sha256,
                    trusted_numeric=True,
                )
                accepted.setdefault(str(profile["semantic_metric_id"]), []).append(candidate)
        status = "CANDIDATE" if candidate is not None and not reasons else "REJECTED"
        candidate_receipts.append(
            {
                "observation_id": observation.observation_id,
                "status": status,
                "reason_codes": sorted(set(reasons)),
                "h3_receipt": h3,
                "candidate": candidate.model_dump(mode="json") if candidate else None,
                "source_document_sha256": observation.source_document_sha256,
                "evidence_locator": observation.locator,
            }
        )
    resolutions = []
    for metric_id in sorted(profiles):
        receipt = resolve_metric(metric_id, tuple(accepted.get(metric_id, ()))).model_dump(
            mode="json"
        )
        resolutions.append(
            {
                **receipt,
                "supplemental_candidate_count": len(accepted.get(metric_id, ())),
                "observation_set_sha256": supplemental.observation_set_sha256,
            }
        )
    return tuple(candidate_receipts), tuple(resolutions)
