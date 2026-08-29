from __future__ import annotations

from research_agent.alpha_shared.document_normalizer import (
    NormalizedTable,
    bind_temporal_header_fragment,
    discover_observations,
    normalize_document,
)
from research_agent.alpha_shared.observation_registry import label_profiles
from research_agent.alpha_shared.supplemental_semantics import build_supplemental_semantics
from research_agent.tests.test_rfc0011_r2_correction import _supplemental


CUBE_LABEL = (
    "FFO attributable to the Company's common shareholders and third-party OP unitholders"
)


def _cube_observations():
    document = normalize_document(
        f"""
        <p>Non-GAAP Measure - Computation of Funds From Operations</p>
        <p>(in thousands, except percentages and per share and unit data)</p>
        <table>
          <tr><th></th><th></th><th colspan="5">Three Months Ended</th><th></th>
              <th colspan="5">Six Months Ended</th><th></th></tr>
          <tr><th></th><th></th><th colspan="5">June 30,</th><th></th>
              <th colspan="5">June 30,</th><th></th></tr>
          <tr><th></th><th></th><th>2026</th><th></th><th></th><th></th><th>2025</th><th></th>
              <th>2026</th><th></th><th></th><th>2025</th><th></th><th></th></tr>
          <tr><td>{CUBE_LABEL}</td><td></td><td>$</td><td>142,993</td><td></td>
              <td>$</td><td>148,912</td><td></td><td>$</td><td>287,223</td><td></td>
              <td>$</td><td>297,061</td><td></td></tr>
        </table>
        """.encode(),
        document_id="cube-production-structure",
        accession_number="0001298675-26-000035",
        report_date="2026-07-30",
        filing_date="2026-07-31",
        document_name="cube-20260730xex99d1.htm",
        media_type="text/html",
    )
    return discover_observations(
        document, {"reported_ffo": label_profiles()["reported_ffo"]}
    )


def test_hdr_001_005_cube_q2_2026_resolves_through_production_semantics():
    target = next(item for item in _cube_observations() if item.column_index_or_null == 3)
    assert target.header_path == ("Three Months Ended", "June 30,", "2026")
    assert target.reported_period_text_or_null == "Three Months Ended June 30, 2026"
    assert target.numeric_role == "MEASURE_VALUE"
    assert target.trusted_numeric is True
    receipts, resolutions = build_supplemental_semantics(
        supplemental=_supplemental(target),
        as_of_date="2026-08-28",
        filed_date="2026-07-31",
        archetype_profile_id="reit",
    )
    receipt = receipts[0]
    assert receipt["status"] == "CANDIDATE"
    assert receipt["period_start_or_null"] == "2026-04-01"
    assert receipt["period_end_or_null"] == "2026-06-30"
    assert receipt["candidate"]["numeric_value"] == "142993000"
    resolved = next(item for item in resolutions if item["metric_id"] == "reported_ffo")
    assert resolved["status"] == "RESOLVED"


def test_hdr_007_008_measure_groups_bind_prior_year_and_six_month_independently():
    by_column = {
        item.column_index_or_null: item
        for item in _cube_observations()
        if item.column_index_or_null is not None
    }
    assert by_column[6].reported_period_text_or_null == "Three Months Ended June 30, 2025"
    assert by_column[9].reported_period_text_or_null == "Six Months Ended June 30, 2026"
    assert by_column[12].reported_period_text_or_null == "Six Months Ended June 30, 2025"
    assert all(item.trusted_numeric for item in by_column.values())


def test_hdr_n01_does_not_cross_another_numeric_measure_group():
    table = NormalizedTable(
        table_index=0,
        rows=(("", "2026", "", "", "", "", ""),),
        column_origins=((0, 1, 2, 3, 4, 5, 6),),
    )
    binding = bind_temporal_header_fragment(
        table=table,
        header_row_index=0,
        target_value_column=6,
        numeric_value_columns=frozenset({3, 6}),
        label_column=0,
    )
    assert binding is None


def test_hdr_n02_does_not_cross_nonempty_semantic_header():
    table = NormalizedTable(
        table_index=0,
        rows=(("", "2026", "Projected", ""),),
        column_origins=((0, 1, 2, 3),),
    )
    binding = bind_temporal_header_fragment(
        table=table,
        header_row_index=0,
        target_value_column=3,
        numeric_value_columns=frozenset({3}),
        label_column=0,
    )
    assert binding is None


def test_hdr_n03_n06_incomplete_or_right_side_year_remains_untrusted():
    document = normalize_document(
        f"""
        <table>
          <tr><th></th><th>Three Months Ended</th><th></th><th>2026</th></tr>
          <tr><th></th><th>June 30,</th><th></th><th></th></tr>
          <tr><td>{CUBE_LABEL}</td><td></td><td>$ 142,993</td><td></td></tr>
        </table>
        """.encode(),
        document_id="unbound-year",
        accession_number="0001298675-26-000035",
        report_date="2026-06-30",
        filing_date="2026-07-31",
        document_name="fixture.htm",
        media_type="text/html",
    )
    target = discover_observations(
        document, {"reported_ffo": label_profiles()["reported_ffo"]}
    )[0]
    assert target.reported_period_text_or_null == "Three Months Ended June 30,"
    assert target.trusted_numeric is False
    assert "$" not in target.header_path
