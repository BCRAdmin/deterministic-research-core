from __future__ import annotations

import pytest

from research_agent.alpha_shared.document_normalizer import (
    discover_observations,
    normalize_document,
)
from research_agent.alpha_shared.observation_registry import label_profiles
from research_agent.alpha_shared.reit_total_row_grammar import (
    is_plain_reported_ffo_total_label,
)
from research_agent.alpha_shared.supplemental_semantics import (
    build_supplemental_semantics,
    classify_reit_row_role,
)
from research_agent.tests.test_rfc0011_r2_correction import _supplemental


def _observation(label: str, value: str, *, scale: str = "thousands"):
    document = normalize_document(
        f"""
        <p>($ in {scale}, except per share data)</p>
        <table>
          <tr><th></th><th>Three Months Ended</th></tr>
          <tr><th></th><th>June 30,</th></tr>
          <tr><th></th><th>2026</th></tr>
          <tr><td>{label}</td><td>$ {value}</td></tr>
        </table>
        """.encode(),
        document_id="fixture",
        accession_number="0000000000-26-000001",
        report_date="2026-06-30",
        filing_date="2026-07-29",
        document_name="exhibit991.htm",
        media_type="text/html",
    )
    return discover_observations(document, label_profiles())


@pytest.mark.parametrize(
    ("label", "value", "scale", "expected"),
    (
        ("Nareit FFO attributable to AMT common stockholders", "1,249.3", "millions", "1249300000.0"),
        (
            "FFO attributable to the Company's common shareholders and third-party OP unitholders",
            "142,993",
            "thousands",
            "142993000",
        ),
    ),
)
def test_trg_001_005_production_path_resolves_exact_plain_ffo_total(
    label: str, value: str, scale: str, expected: str
):
    observations = _observation(label, value, scale=scale)
    assert len(observations) == 1
    observation = observations[0]
    assert observation.reported_label == "funds from operations"
    assert observation.reported_period_text_or_null == "Three Months Ended June 30, 2026"
    assert classify_reit_row_role(observation) == "TOTAL_MEASURE"
    receipts, resolutions = build_supplemental_semantics(
        supplemental=_supplemental(observation),
        as_of_date="2026-08-28",
        filed_date="2026-07-29",
        archetype_profile_id="reit",
    )
    assert receipts[0]["status"] == "CANDIDATE"
    assert receipts[0]["candidate"]["numeric_value"] == expected
    resolved = next(item for item in resolutions if item["metric_id"] == "reported_ffo")
    assert resolved["status"] == "RESOLVED"


@pytest.mark.parametrize(
    "label",
    (
        "FFO, as adjusted, attributable to common shareholders",
        "Adjusted FFO attributable to common shareholders",
        "Core FFO attributable to common shareholders",
        "Normalized FFO attributable to common shareholders",
        "FFO excluding gains attributable to common shareholders",
        "FFO before adjustments attributable to common shareholders",
        "FFO after adjustments attributable to common shareholders",
        "FFO per share",
        "AFFO attributable to common shareholders",
    ),
)
def test_trg_n01_n10_adjusted_or_other_family_never_becomes_plain_ffo(label: str):
    assert is_plain_reported_ffo_total_label(label) is False


@pytest.mark.parametrize(
    "label",
    (
        "FFO per diluted share and unit",
        "Weighted-average diluted shares",
        "Less: noncontrolling interest in Core FFO",
        "Add: participating securities Core FFO",
        "FFO payout ratio",
    ),
)
def test_trg_negative_decision_order_precedes_total_grammar(label: str):
    observations = _observation(label, "10")
    if not observations:
        assert is_plain_reported_ffo_total_label(label) is False
        return
    assert all(classify_reit_row_role(item) != "TOTAL_MEASURE" for item in observations)

