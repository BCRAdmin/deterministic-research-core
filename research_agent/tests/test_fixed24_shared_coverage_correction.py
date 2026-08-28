from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from research_agent.alpha_shared.archetype_profiles import load_archetype_profile
from research_agent.alpha_shared.contracts import (
    DiscoveredSourceCandidateIR,
    DiscoveredSourceSetIR,
    DocumentObservationIR,
)
from research_agent.alpha_shared.document_normalizer import discover_observations, normalize_document
from research_agent.alpha_shared.internal_report import build_internal_alpha_report
from research_agent.alpha_shared.metric_semantics import (
    METRIC_SEMANTICS_REGISTRY,
    metric_semantics,
)
from research_agent.alpha_shared.observation_registry import label_profiles
from research_agent.alpha_shared.raw_inventory import build_source_snapshot_fact_inventory
from research_agent.alpha_shared.source_authority import (
    SupplementalSourceAuthority,
    is_earnings_filed_exhibit_name,
    is_sec_index_page,
    is_strict_filed_exhibit_name,
)
from research_agent.alpha_shared.supplemental_semantics import (
    SUPPLEMENTAL_SEMANTIC_REGISTRY,
    build_supplemental_semantics,
    classify_reit_row_role,
)
from research_agent.tests.test_rfc0011_r2_correction import _canonical_base, _supplemental
from research_agent.tests.test_rfc0011_shared_hardening import _policy


def _observation(
    label: str,
    row: str,
    *,
    value: str = "150,016",
    unit: str | None = "USD",
    period: str | None = "Three Months Ended June 30, 2026",
    context: str = "The reconciliation is stated in thousands.",
    trusted: bool = True,
) -> DocumentObservationIR:
    return DocumentObservationIR.create(
        source_document_sha256="a" * 64,
        locator_type="table_cell",
        locator=f"table:1:row:2:column:2:{label}:{value}",
        row_index_or_null=2,
        column_index_or_null=2,
        header_path=(period,) if period else ("unbound",),
        reported_label=label,
        raw_value_text=value,
        parsed_numeric_value_or_null=value,
        reported_unit_text_or_null=unit,
        reported_period_text_or_null=period,
        reported_basis_text_or_null="issuer_reported_total",
        context_text=f"{context} || ROW: {row}",
        numeric_role="MEASURE_VALUE",
        trusted_numeric=trusted,
    )


def _semantics(observation: DocumentObservationIR, profile: str = "reit"):
    return build_supplemental_semantics(
        supplemental=_supplemental(observation),
        as_of_date="2026-08-28",
        filed_date="2026-07-22",
        archetype_profile_id=profile,
    )


def _candidate(
    *,
    name: str,
    family: str,
    form: str,
    filed: str,
    report: str,
    accession: str,
) -> DiscoveredSourceCandidateIR:
    return DiscoveredSourceCandidateIR.create(
        source_family_id=family,
        issuer_cik="1234",
        accession_number=accession,
        filing_date=filed,
        report_date=report,
        form=form,
        document_name=name,
        locator=f"https://www.sec.gov/Archives/edgar/data/1234/{accession.replace('-', '')}/{name}",
        parent_discovery_receipt_sha256="b" * 64,
    )


def test_cov_sem_001_006_explicit_registry_has_no_name_guess_fallback():
    assert METRIC_SEMANTICS_REGISTRY["unknown_metric_policy"] == "UNSUPPORTED_NO_GUESS"
    assert metric_semantics("unknown_share_margin_rate") is None
    assert "if \"share\" in metric_id" not in inspect.getsource(load_archetype_profile)
    assert metric_semantics("revenue").required_core is True
    assert metric_semantics("latest_market_price").required_core is False


def test_cov_sem_002_and_eps_001_003_diluted_eps_is_duration_per_share_only():
    semantics = metric_semantics("diluted_eps")
    assert semantics is not None
    assert semantics.period_type == "DURATION"
    assert set(semantics.allowed_units) == {"USD/shares", "USD / shares"}
    for profile in ("bank", "energy"):
        definition = next(
            item for item in load_archetype_profile(profile).metric_definitions
            if item.metric_id == "diluted_eps"
        )
        assert definition.period_type == "DURATION"
        assert "USD" not in definition.allowed_units


def test_cov_sem_003_004_cash_repurchase_and_share_count_units_are_distinct():
    assert metric_semantics("common_stock_repurchases").allowed_units == ("USD",)
    assert metric_semantics("share_repurchases").allowed_units == ("USD",)
    assert metric_semantics("shares_outstanding").allowed_units == ("shares",)


def test_cov_sem_005_and_rpo_001_002_rpo_is_explicit_instant_and_distinct():
    rpo = metric_semantics("rpo")
    liability = metric_semantics("current_contract_liability")
    assert rpo is not None and rpo.period_type == "INSTANT"
    assert liability is not None and rpo.semantic_definition != liability.semantic_definition
    labels = SUPPLEMENTAL_SEMANTIC_REGISTRY["profiles"]
    assert "current remaining performance obligation" not in labels["rpo"]["reported_labels"]


def test_cov_sup_001_004_safe_supplemental_enters_report_with_full_lineage(tmp_path: Path):
    observation = _observation("core ffo", "Core FFO | $ | 150,016")
    candidates, resolutions = _semantics(observation)
    inventory = build_source_snapshot_fact_inventory(_canonical_base(tmp_path))
    report = build_internal_alpha_report(
        inventory,
        load_archetype_profile("reit"),
        supplemental_candidate_receipts=candidates,
        supplemental_resolution_receipts=resolutions,
    ).report
    metric = next(item for item in report.core_metrics if item.metric_id == "reported_core_ffo")
    assert metric.value == "150016000"
    assert len(metric.evidence_ids) >= 5
    assert report.source_coverage["supplemental_surfaced_metric_count"] == 1
    assert report.source_coverage["covered_core_metric_count"] == 1


def test_cov_sup_005_untrusted_supplemental_never_contributes():
    observation = _observation(
        "core ffo", "Core FFO | $ | 150,016", trusted=False
    )
    candidates, resolutions = _semantics(observation)
    assert candidates[0]["status"] == "REJECTED"
    assert "UNTRUSTED_NUMERIC" in candidates[0]["reason_codes"]
    assert next(item for item in resolutions if item["metric_id"] == "reported_core_ffo")[
        "status"
    ] == "UNSUPPORTED"


@pytest.mark.parametrize(
    ("field", "updates", "reason"),
    [
        ("unit", {"unit": None}, "UNIT_BINDING_MISSING"),
        ("period", {"period": None}, "PERIOD_BINDING_MISSING"),
        ("scale", {"context": "No scale is stated."}, "SCALE_BINDING_MISSING"),
    ],
)
def test_cov_sup_006_missing_structural_binding_is_blocked(field, updates, reason):
    del field
    candidates, _ = _semantics(
        _observation("core ffo", "Core FFO | $ | 150,016", **updates)
    )
    assert reason in candidates[0]["reason_codes"]


@pytest.mark.parametrize(
    ("test_id", "label", "row", "value", "expected_role"),
    [
        (
            "COV-FFO-002",
            "funds from operations",
            "Diluted shares for earnings per share and funds from operations per share | 53,783",
            "53,783",
            "SHARES_COUNT",
        ),
        (
            "COV-FFO-003",
            "core ffo",
            "Less: Core FFO attributable to noncontrolling interests | (5,631)",
            "5,631",
            "COMPONENT",
        ),
        (
            "COV-FFO-004",
            "core ffo",
            "Less: Core FFO attributable to participating securities | (668)",
            "668",
            "COMPONENT",
        ),
        (
            "COV-FFO-005",
            "funds from operations",
            "Funds from operations per diluted share | $ | 2.36",
            "2.36",
            "PER_SHARE",
        ),
        (
            "COV-FFO-006",
            "core ffo",
            "Add: Core FFO reconciliation component | 10",
            "10",
            "COMPONENT",
        ),
        (
            "COV-FFO-007",
            "core ffo",
            "Weighted-average shares used for Core FFO per share | 10",
            "10",
            "SHARES_COUNT",
        ),
    ],
)
def test_cov_ffo_001_007_only_total_measure_is_eligible(
    test_id, label, row, value, expected_role
):
    del test_id
    observation = _observation(label, row, value=value)
    assert classify_reit_row_role(observation) == expected_role
    candidates, _ = _semantics(observation)
    assert candidates[0]["status"] == "REJECTED"
    assert f"ROW_ROLE_{expected_role}_INELIGIBLE" in candidates[0]["reason_codes"]


def test_cov_ffo_008_009_scale_requires_explicit_captured_evidence():
    good, _ = _semantics(_observation("core ffo", "Core FFO | $ | 150,016"))
    bad, _ = _semantics(
        _observation(
            "core ffo",
            "Core FFO | $ | 150,016",
            context="The magnitude is large but no scale is stated.",
        )
    )
    assert good[0]["candidate"]["numeric_value"] == "150016000"
    assert bad[0]["status"] == "REJECTED"
    assert "SCALE_BINDING_MISSING" in bad[0]["reason_codes"]


@pytest.mark.parametrize(
    ("test_id", "label", "row", "metric_id"),
    [
        ("COV-FFO-010", "funds from operations", "Funds From Operations (FFO) | $ | 150,016", "reported_ffo"),
        ("COV-FFO-011", "core ffo", "Core FFO | $ | 150,016", "reported_core_ffo"),
        ("COV-FFO-012", "affo", "AFFO | $ | 150,016", "reported_affo"),
    ],
)
def test_cov_ffo_010_012_legitimate_totals_resolve(test_id, label, row, metric_id):
    del test_id
    candidates, resolutions = _semantics(_observation(label, row))
    assert candidates[0]["row_role"] == "TOTAL_MEASURE"
    assert next(item for item in resolutions if item["metric_id"] == metric_id)["status"] == "RESOLVED"


def test_cov_sec_001_003_index_and_arbitrary_ex_names_are_excluded():
    assert is_sec_index_page("index.html")
    assert is_sec_index_page("00001234-index-headers.html")
    assert not is_strict_filed_exhibit_name("example-document.htm")
    assert is_strict_filed_exhibit_name("ex99-1.htm")
    assert is_strict_filed_exhibit_name("quarterly-earnings-release.htm")
    assert not is_earnings_filed_exhibit_name("acquisition-ex99-1.htm")


def test_cov_sec_004_005_selection_ranks_current_primary_then_same_period_ex99(tmp_path: Path):
    authority = SupplementalSourceAuthority(_policy(max_selected_documents=2), tmp_path)
    primary = _candidate(
        name="quarter.htm", family="sec_primary_document", form="10-Q",
        filed="2026-08-20", report="2026-06-30", accession="0000001234-26-000010",
    )
    exhibit = _candidate(
        name="ex99-1.htm", family="sec_filed_exhibit", form="8-K",
        filed="2026-08-20", report="2026-08-20", accession="0000001234-26-000009",
    )
    old = _candidate(
        name="old.htm", family="sec_primary_document", form="10-Q",
        filed="2026-05-01", report="2026-03-31", accession="0000001234-26-000001",
    )
    candidate_set = DiscoveredSourceSetIR.create(
        policy_sha256=authority.policy.policy_sha256,
        discovery_receipt_sha256s=("b" * 64,),
        candidates=(primary, exhibit, old),
    )
    assert [item.document_name for item in authority.select(candidate_set)] == [
        "quarter.htm",
        "ex99-1.htm",
    ]


def test_cov_sec_007_source_authority_has_no_issuer_filename_branch():
    source = inspect.getsource(SupplementalSourceAuthority)
    assert "ticker" not in source.casefold()
    assert "issuer_specific" not in source.casefold()


def test_cov_rpo_003_safe_total_rpo_resolves_and_crpo_is_not_inferred():
    total = _observation(
        "remaining performance obligation",
        "Remaining performance obligation | $ | 2,500",
        value="2,500",
        period="As of June 30, 2026",
        context="Amounts in millions.",
    )
    candidates, resolutions = _semantics(total, "saas")
    assert candidates[0]["candidate"]["numeric_value"] == "2500000000"
    assert next(item for item in resolutions if item["metric_id"] == "rpo")["status"] == "RESOLVED"
    current = _observation(
        "remaining performance obligation",
        "Current remaining performance obligation | $ | 1,000",
        period="As of June 30, 2026",
        context="Amounts in millions.",
    )
    rejected, _ = _semantics(current, "saas")
    assert rejected[0]["status"] == "REJECTED"
    assert "ROW_ROLE_OTHER_INELIGIBLE" in rejected[0]["reason_codes"]


def test_cov_discovery_normalizer_preserves_period_scale_and_total_role():
    html = b"""
    <p>The following reconciliation is stated in thousands.</p>
    <table><tr><th></th><th colspan='2'>Three Months Ended June 30,</th></tr>
    <tr><th></th><th colspan='2'>2026</th></tr>
    <tr><td>Core FFO</td><td>$</td><td>150,016</td></tr></table>
    """
    document = normalize_document(
        html,
        document_id="fixture",
        accession_number="1",
        report_date="2026-06-30",
        filing_date="2026-07-22",
        document_name="ex99-1.htm",
        media_type="text/html",
    )
    observations = discover_observations(document, label_profiles())
    observation = next(item for item in observations if item.reported_label == "core ffo")
    assert observation.reported_period_text_or_null == "Three Months Ended June 30, 2026"
    assert observation.reported_unit_text_or_null == "USD"
    assert classify_reit_row_role(observation) == "TOTAL_MEASURE"
