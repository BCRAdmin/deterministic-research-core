"""Safe RFC-0011 supplemental observation to H3/H2 integration."""

from __future__ import annotations

import re
import unicodedata
from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from research_agent.compiler_foundation.canonical import sha256_json

from .contracts import DocumentObservationIR, SupplementalCompileInputIR
from .concept_registry import concept_record
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
            "row_role_required": None,
            "scale_required": False,
        },
        "rpo": {
            "semantic_metric_id": "rpo",
            "reported_labels": ["remaining performance obligation", "total rpo"],
            "allowed_units": ["USD"],
            "allowed_period_types": ["INSTANT"],
            "allowed_duration_roles": [],
            "allowed_archetype_profiles": ["saas", "generic"],
            "required_basis": [],
            "row_role_required": "TOTAL_MEASURE",
            "scale_required": True,
        },
        "reported_ffo": {
            "semantic_metric_id": "reported_ffo",
            "reported_labels": [
                "funds from operations",
                "ffo attributable to common stockholders",
            ],
            "allowed_units": ["USD"],
            "allowed_period_types": ["DURATION"],
            "allowed_duration_roles": ["STANDALONE_QUARTER", "YEAR_TO_DATE", "ANNUAL"],
            "allowed_archetype_profiles": ["reit"],
            "required_basis": [],
            "row_role_required": "TOTAL_MEASURE",
            "scale_required": True,
        },
        "reported_core_ffo": {
            "semantic_metric_id": "reported_core_ffo",
            "reported_labels": ["core ffo"],
            "allowed_units": ["USD"],
            "allowed_period_types": ["DURATION"],
            "allowed_duration_roles": ["STANDALONE_QUARTER", "YEAR_TO_DATE", "ANNUAL"],
            "allowed_archetype_profiles": ["reit"],
            "required_basis": [],
            "row_role_required": "TOTAL_MEASURE",
            "scale_required": True,
        },
        "reported_affo": {
            "semantic_metric_id": "reported_affo",
            "reported_labels": ["affo", "adjusted funds from operations (affo)"],
            "allowed_units": ["USD"],
            "allowed_period_types": ["DURATION"],
            "allowed_duration_roles": ["STANDALONE_QUARTER", "YEAR_TO_DATE", "ANNUAL"],
            "allowed_archetype_profiles": ["reit"],
            "required_basis": [],
            "row_role_required": "TOTAL_MEASURE",
            "scale_required": True,
        },
    },
    "ticker_specific_profiles": False,
    "unit_conversions_allowed": False,
}
SUPPLEMENTAL_SEMANTIC_REGISTRY_SHA256 = sha256_json(SUPPLEMENTAL_SEMANTIC_REGISTRY)


def _month_number(value: str) -> int:
    for pattern in ("%B", "%b"):
        try:
            return datetime.strptime(value, pattern).month
        except ValueError:
            continue
    raise ValueError(f"unsupported month name: {value}")


def _period_bounds(text: str) -> tuple[str | None, str] | None:
    iso = re.fullmatch(r"(\d{4}-\d{2}-\d{2})/(\d{4}-\d{2}-\d{2})", text.strip())
    if iso:
        date.fromisoformat(iso.group(1))
        date.fromisoformat(iso.group(2))
        return iso.group(1), iso.group(2)
    instant = re.fullmatch(r"As of ([A-Za-z]+) (\d{1,2}),? (\d{4})", text.strip(), re.I)
    if instant:
        month = _month_number(instant.group(1))
        end = date(int(instant.group(3)), month, int(instant.group(2)))
        return None, end.isoformat()
    match = re.fullmatch(
        r"(Three|Six|Nine|Twelve) Months Ended ([A-Za-z]+) (\d{1,2}),? (\d{4})",
        text.strip(),
        re.I,
    )
    if not match:
        return None
    months = {"three": 3, "six": 6, "nine": 9, "twelve": 12}[match.group(1).casefold()]
    month = _month_number(match.group(2))
    year = int(match.group(4))
    end = date(year, month, min(int(match.group(3)), monthrange(year, month)[1]))
    start_month_index = year * 12 + month - months
    start = date(start_month_index // 12, start_month_index % 12 + 1, 1)
    return start.isoformat(), end.isoformat()


def classify_reit_row_role(observation: DocumentObservationIR) -> str:
    """Classify an observed table row before any FFO-family eligibility decision."""

    row = observation.context_text.rsplit("|| ROW:", 1)[-1].strip()
    lowered = row.casefold()
    row_label = row.split("|", 1)[0].strip()
    if re.search(r"\b(?:diluted|weighted[- ]average) shares\b", lowered):
        return "SHARES_COUNT"
    if re.search(r"\bper\s+(?:diluted\s+)?share\b", lowered):
        return "PER_SHARE"
    if re.search(
        r"(?:^|\|)\s*(?:less|plus|add)\s*:|noncontrolling interest|participating securit|"
        r"reconciliation adjustment|acquisition expense|severance|write-off|extinguishment",
        lowered,
    ):
        return "COMPONENT"
    if "%" in row or re.search(r"\b(?:rate|percentage|margin)\b", lowered):
        return "PERCENTAGE_OR_RATE"
    if observation.parsed_numeric_value_or_null is None:
        return "DEFINITION_TEXT"
    normalized_label = unicodedata.normalize("NFKC", row_label)
    normalized_label = normalized_label.translate(
        str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})
    )
    normalized_label = re.sub(
        r"\(\s*['\"]?\s*ffo\s*['\"]?\s*\)",
        "(FFO)",
        normalized_label,
        flags=re.IGNORECASE,
    )
    normalized_label = re.sub(r"(?:\s*[*†‡]+|\s*\(\d+\))+$", "", normalized_label)
    normalized_label = re.sub(r"\s+", " ", normalized_label).strip()
    if re.fullmatch(
        r"(?:affo|adjusted funds from operations\s*\(affo\)|core ffo|"
        r"funds from operations\s*\(ffo\)(?: attributable to common stockholders)?|"
        r"ffo attributable to common stockholders|"
        r"remaining performance obligations?|total rpo)",
        normalized_label,
        re.IGNORECASE,
    ):
        return "TOTAL_MEASURE"
    return "OTHER"


def _explicit_scale(observation: DocumentObservationIR) -> tuple[int | None, str | None]:
    context = observation.context_text
    if re.search(r"\bin thousands\b", context, re.I):
        return 1_000, "captured_context:in_thousands"
    if re.search(r"\bin millions\b", context, re.I):
        return 1_000_000, "captured_context:in_millions"
    if re.search(r"\bin billions\b", context, re.I):
        return 1_000_000_000, "captured_context:in_billions"
    if re.search(r"\b(?:amounts in|actual) dollars\b", context, re.I):
        return 1, "captured_context:actual_dollars"
    return None, None


def _scaled_numeric(value: str | None, factor: int | None) -> str | None:
    if value is None or factor is None:
        return value
    normalized = value.replace("$", "").replace(",", "").strip()
    negative = normalized.startswith("(") and normalized.endswith(")")
    normalized = normalized.strip("()")
    try:
        result = Decimal(normalized) * factor
    except InvalidOperation:
        return None
    if negative:
        result = -result
    return format(result, "f")


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
    period_cache: dict[str, tuple[str | None, str] | None] = {
        item.observation_id: (
            _period_bounds(item.reported_period_text_or_null)
            if item.reported_period_text_or_null
            else None
        )
        for item in supplemental.observations
    }
    current_end_by_profile: dict[str, str] = {}
    for item in supplemental.observations:
        normalized = item.reported_label.casefold()
        matches = [
            profile_id
            for profile_id, value in profiles.items()
            if normalized in {str(label).casefold() for label in value["reported_labels"]}
        ]
        period_value = period_cache[item.observation_id]
        if len(matches) == 1 and period_value is not None:
            current_end_by_profile[matches[0]] = max(
                current_end_by_profile.get(matches[0], period_value[1]), period_value[1]
            )
    for observation in supplemental.observations:
        reasons: list[str] = []
        normalized_label = observation.reported_label.casefold()
        matching_profiles = [
            (profile_id, value)
            for profile_id, value in profiles.items()
            if normalized_label in {str(item).casefold() for item in value["reported_labels"]}
        ]
        profile_id, profile = matching_profiles[0] if len(matching_profiles) == 1 else ("", None)
        row_role = classify_reit_row_role(observation)
        scale_factor, scale_evidence = _explicit_scale(observation)
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
        period = period_cache[observation.observation_id]
        if period is None:
            reasons.append("PERIOD_BINDING_MISSING")
        basis = observation.reported_basis_text_or_null
        if (
            isinstance(profile, dict)
            and profile.get("required_basis")
            and basis not in set(profile["required_basis"])
        ):
            reasons.append("BASIS_BINDING_MISSING")
        if isinstance(profile, dict) and profile.get("row_role_required"):
            if row_role != profile["row_role_required"]:
                reasons.append(f"ROW_ROLE_{row_role}_INELIGIBLE")
        if isinstance(profile, dict) and profile.get("scale_required") and scale_factor is None:
            reasons.append("SCALE_BINDING_MISSING")
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
                    current_period_end=current_end_by_profile.get(profile_id, period[1]),
                )
            )
            h3 = h3_model.model_dump(mode="json")
            h3["receipt_sha256"] = sha256_json(h3)
            if h3["period_type"] not in profile.get("allowed_period_types", ["DURATION"]):
                reasons.append("PERIOD_TYPE_UNSUPPORTED")
            elif (
                h3["period_type"] == "DURATION"
                and h3["duration_role"] not in profile["allowed_duration_roles"]
            ):
                reasons.append("DURATION_ROLE_UNSUPPORTED")
            else:
                concept_label = observation.reported_label.casefold()
                concept = concept_record(str(profile["semantic_metric_id"]), concept_label)
                candidate = MetricCandidate(
                    candidate_id=observation.observation_id,
                    concept_or_label=concept_label,
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
                    numeric_value=_scaled_numeric(
                        observation.parsed_numeric_value_or_null,
                        scale_factor if profile.get("scale_required") else 1,
                    ),
                    semantic_metric_id=str(profile["semantic_metric_id"]),
                    semantic_role=(
                        str(concept["semantic_role"]) if concept is not None else "EXACT_DIRECT"
                    ),
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
                "row_role": row_role,
                "reported_period_text": observation.reported_period_text_or_null,
                "period_start_or_null": period[0] if period else None,
                "period_end_or_null": period[1] if period else None,
                "reported_basis": basis,
                "reported_unit": unit,
                "scale_factor_or_null": scale_factor,
                "scale_evidence_or_null": scale_evidence,
                "parsed_numeric_value_or_null": observation.parsed_numeric_value_or_null,
            }
        )
    resolutions = []
    for metric_id in sorted(profiles):
        pool = accepted.get(metric_id, [])
        if pool:
            details = {
                str(item["observation_id"]): item
                for item in candidate_receipts
                if item["status"] == "CANDIDATE"
            }
            pool = sorted(
                pool,
                key=lambda item: (
                    item.period_role != "CURRENT_PRIMARY",
                    item.period_role != "CURRENT_YTD",
                    str(details[item.candidate_id]["period_end_or_null"] or ""),
                    item.candidate_id,
                ),
                reverse=False,
            )
            best_role = pool[0].period_role
            role_pool = [item for item in pool if item.period_role == best_role]
            pool = [
                max(
                    role_pool,
                    key=lambda item: (
                        str(details[item.candidate_id]["period_end_or_null"] or ""),
                        item.candidate_id,
                    ),
                )
            ]
        receipt = resolve_metric(metric_id, tuple(pool)).model_dump(mode="json")
        resolutions.append(
            {
                **receipt,
                "supplemental_candidate_count": len(accepted.get(metric_id, ())),
                "observation_set_sha256": supplemental.observation_set_sha256,
            }
        )
    return tuple(candidate_receipts), tuple(resolutions)
