from __future__ import annotations

import inspect

import pytest

from research_agent.alpha_shared.archetype_profiles import load_archetype_profile
from research_agent.alpha_shared.core_slots import (
    REIT_OPERATING_PERFORMANCE_GRADES,
    core_slot_registry,
    resolve_core_slots,
)
from research_agent.alpha_shared.internal_report import build_internal_alpha_report
from research_agent.alpha_shared.raw_inventory import build_source_snapshot_fact_inventory
from research_agent.alpha_shared.supplemental_semantics import classify_reit_row_role
from research_agent.alpha_reit import projection as frozen_reit_projection
from research_agent.tests.test_fixed24_shared_coverage_correction import (
    _canonical_base,
    _observation,
    _semantics,
)


def _reit_slots():
    return load_archetype_profile("reit").required_core_slots


def test_reit_v2_001_exactly_five_semantic_core_slots():
    slots = _reit_slots()
    assert tuple(item.slot_id for item in slots) == (
        "revenue",
        "net_income",
        "reit_operating_performance_measure",
        "operating_cash_flow",
        "total_debt",
    )
    assert all(item.maximum_counted == 1 for item in slots)


def test_reit_v2_002_003_ffo_family_counts_once_and_preserves_priority_identity():
    slots = _reit_slots()
    resolutions = resolve_core_slots(
        slots,
        {
            "reported_ffo": object(),
            "reported_core_ffo": object(),
            "reported_affo": object(),
        },
    )
    operating = next(
        item for item in resolutions if item.slot_id == "reit_operating_performance_measure"
    )
    assert operating.counted == 1
    assert operating.selected_metric_id_or_null == "reported_ffo"
    assert operating.eligible_resolved_metric_ids == (
        "reported_ffo",
        "reported_core_ffo",
        "reported_affo",
    )
    assert operating.selected_metric_identity_preserved is True


@pytest.mark.parametrize(
    ("metric_id", "grade", "standardized"),
    [
        ("reported_ffo", "NAREIT_OR_EXPLICIT_FFO", True),
        ("reported_core_ffo", "ISSUER_ADJUSTED_FFO", False),
        ("reported_affo", "ISSUER_DEFINED_NONSTANDARD", False),
    ],
)
def test_reit_v2_004_005_subtype_and_comparability_are_explicit(
    metric_id, grade, standardized
):
    operating = resolve_core_slots(_reit_slots(), {metric_id: object()})[2]
    assert operating.selected_metric_id_or_null == metric_id
    assert operating.comparability_grade_or_null == grade
    assert operating.cross_issuer_definition_standardized_or_null is standardized
    assert REIT_OPERATING_PERFORMANCE_GRADES[metric_id] == (grade, standardized)


@pytest.mark.parametrize("profile_id", ["saas", "bank", "energy"])
def test_reit_v2_006_008_other_archetype_required_semantics_unchanged(profile_id):
    profile = load_archetype_profile(profile_id)
    assert tuple(item.slot_id for item in profile.required_core_slots) == (
        profile.required_core_metrics
    )
    assert all(len(item.eligible_metric_ids) == 1 for item in profile.required_core_slots)


def test_reit_v2_009_010_core_ffo_is_not_relabelled_or_multicounted(tmp_path):
    candidates, resolutions = _semantics(
        _observation("core ffo", "Core FFO | $ | 150,016")
    )
    report = build_internal_alpha_report(
        build_source_snapshot_fact_inventory(_canonical_base(tmp_path)),
        load_archetype_profile("reit"),
        supplemental_candidate_receipts=candidates,
        supplemental_resolution_receipts=resolutions,
    ).report
    operating = next(
        item
        for item in report.core_slot_resolutions
        if item["slot_id"] == "reit_operating_performance_measure"
    )
    assert operating["selected_metric_id_or_null"] == "reported_core_ffo"
    assert operating["comparability_grade_or_null"] == "ISSUER_ADJUSTED_FFO"
    assert report.source_coverage["covered_core_slot_count"] == 1
    assert tuple(item.metric_id for item in report.core_metrics) == ("reported_core_ffo",)


def test_reit_safe_004_006_missing_bindings_and_adjusted_ffo_remain_blocked():
    missing_scale, _ = _semantics(
        _observation(
            "core ffo", "Core FFO | $ | 150,016", context="No scale is stated."
        )
    )
    missing_period, _ = _semantics(
        _observation("core ffo", "Core FFO | $ | 150,016", period=None)
    )
    adjusted = _observation("adjusted ffo", "Adjusted FFO | $ | 150,016")
    adjusted_candidates, _ = _semantics(adjusted)
    assert "SCALE_BINDING_MISSING" in missing_scale[0]["reason_codes"]
    assert "PERIOD_BINDING_MISSING" in missing_period[0]["reason_codes"]
    assert adjusted_candidates[0]["status"] == "REJECTED"
    assert classify_reit_row_role(adjusted) == "OTHER"


def test_reit_slot_registry_is_hash_bound_and_ticker_neutral():
    profiles = {
        profile_id: load_archetype_profile(profile_id).required_core_metrics
        for profile_id in ("saas", "reit", "bank", "energy")
    }
    registry = core_slot_registry(profiles)
    assert registry["ticker_specific_rules"] is False
    assert len(registry["registry_sha256"]) == 64
    assert "ticker" not in inspect.getsource(resolve_core_slots).casefold()


def test_frozen_alpha_reit_source_is_not_modified_by_shared_v2_policy():
    assert "reit_operating_performance_measure" not in inspect.getsource(
        frozen_reit_projection
    )
