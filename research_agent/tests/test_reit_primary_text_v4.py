from __future__ import annotations

import hashlib
from copy import deepcopy
from pathlib import Path

import pytest

from research_agent.alpha_reit.primary_text_v4 import (
    canonical_sha256,
    classify_ffo_label,
    parse_primary_text_candidates_v4,
    select_reported_ffo_v4,
    validate_primary_text_candidate_v4,
)

GOOD = [
    "FFO",
    "Funds from Operations",
    "NAREIT FFO",
    "FFO, as defined by NAREIT",
    "NAREIT Funds from operations attributable to common stockholders",
    "Funds from operations attributable to common stockholders and unitholders",
    "FFO available to common stockholders and unit holders",
    "NAREIT FFO attributable to controlling interest",
]
BAD = [
    "NAREIT Funds from operations per diluted common share",
    "Funds from operations per common share - diluted",
    "FFO per unit",
    "Gains not included in FFO",
    "Discontinued operations FFO adjustments",
    "FFO Coverage - diluted",
    "FFO from Co-Investments",
    "Proportionate share of adjustments for FFO from partially owned entities",
    "% Change - Funds from Operations",
    "Weighted average shares outstanding - FFO calculation",
    "Funds From Operations and Adjusted Funds From Operations",
    "FFO guidance midpoint",
]


@pytest.mark.parametrize("label", GOOD)
def test_positive_measure_grammar_accepts_real_total_labels(label: str) -> None:
    assert classify_ffo_label(label)["status"] == "POTENTIAL_CORE"


@pytest.mark.parametrize("label", BAD)
def test_non_measure_and_per_share_labels_fail_closed(label: str) -> None:
    assert classify_ffo_label(label)["status"] == "REJECT"


@pytest.mark.parametrize(
    "label",
    [
        "AFFO",
        "Adjusted FFO attributable to common stockholders",
        "Core Funds From Operations Attributable to Common Stockholders",
        "Normalized FFO attributable to controlling interest",
    ],
)
def test_adjusted_families_are_visible_but_not_core(label: str) -> None:
    result = classify_ffo_label(label)
    assert result["status"] == "VISIBLE_NON_CORE"
    assert result["grade"] == "C"


def _write(tmp_path: Path, body: str) -> tuple[Path, str]:
    path = tmp_path / "filing.htm"
    payload = body.encode()
    path.write_bytes(payload)
    return path, hashlib.sha256(payload).hexdigest()


def _filing() -> dict[str, str]:
    return {
        "accession": "0000000000-26-000001",
        "document_name": "filing.htm",
        "document_role": "EARNINGS_OR_SUPPLEMENT_EXHIBIT",
        "filing_date": "2026-08-01",
        "form": "8-K",
        "report_date": "2026-06-30",
    }


def _simple_table() -> str:
    return """
    <html><body><p>Amounts in thousands</p><table>
      <tr><td></td><td>Three Months Ended June 30, 2026</td></tr>
      <tr><td>Net income</td><td>1</td></tr>
      <tr><td>Depreciation and amortization</td><td>2</td></tr>
      <tr><td>Funds from Operations</td><td>5</td></tr>
    </table></body></html>
    """


def test_column_binding_prefers_current_quarter_over_prior_and_ytd(tmp_path: Path) -> None:
    path, sha = _write(
        tmp_path,
        """
        <html><body><p>(dollars in thousands)</p><table>
          <tr><td></td><td colspan='2'>Three Months Ended June 30,</td><td colspan='2'>Six Months Ended June 30,</td></tr>
          <tr><td></td><td>2025</td><td>2026</td><td>2025</td><td>2026</td></tr>
          <tr><td>Net income</td><td>1</td><td>2</td><td>3</td><td>4</td></tr>
          <tr><td>Depreciation and amortization</td><td>10</td><td>20</td><td>30</td><td>40</td></tr>
          <tr><td>FFO attributable to common stockholders</td><td>100</td><td>200</td><td>300</td><td>400</td></tr>
        </table></body></html>
        """,
    )
    parsed = parse_primary_text_candidates_v4(
        path,
        ticker="TEST",
        cik="1",
        filing=_filing(),
        source_artifact_sha256=sha,
        source_snapshot_sha256="a" * 64,
    )
    selected = select_reported_ffo_v4(parsed["candidates"], as_of="2026-09-04")
    assert selected["selected_projection"]["numeric_value"] == "200000"
    assert selected["selected_projection"]["period_basis"] == "STANDALONE_QUARTER"


def test_per_share_section_context_blocks_terse_total_ffo_label(tmp_path: Path) -> None:
    path, sha = _write(
        tmp_path,
        """
        <html><body><p>($ in thousands, except per share amounts)</p><table>
          <tr><td></td><td>Three Months Ended June 30, 2026</td></tr>
          <tr><td>Per Diluted Share</td><td></td></tr>
          <tr><td>Total FFO</td><td>$3.32</td></tr>
        </table></body></html>
        """,
    )
    parsed = parse_primary_text_candidates_v4(
        path,
        ticker="TEST",
        cik="1",
        filing=_filing(),
        source_artifact_sha256=sha,
        source_snapshot_sha256="a" * 64,
    )
    assert not parsed["candidates"]
    assert any(row["reason"] == "PER_SHARE_TABLE_CONTEXT" for row in parsed["rejected_rows"])


def test_scale_is_local_to_table_section_not_document_global(tmp_path: Path) -> None:
    path, sha = _write(
        tmp_path,
        """
        <html><body>
          <p>Unrelated table (dollars in millions)</p>
          <table><tr><td>Other measure</td><td>9</td></tr></table>
          <p>FFO reconciliation (dollars in thousands)</p>
          <table>
            <tr><td></td><td>Three Months Ended June 30, 2026</td></tr>
            <tr><td>Net income</td><td>1</td></tr>
            <tr><td>Depreciation and amortization</td><td>2</td></tr>
            <tr><td>Funds from Operations</td><td>5</td></tr>
          </table>
        </body></html>
        """,
    )
    parsed = parse_primary_text_candidates_v4(
        path,
        ticker="TEST",
        cik="1",
        filing=_filing(),
        source_artifact_sha256=sha,
        source_snapshot_sha256="a" * 64,
    )
    selected = select_reported_ffo_v4(parsed["candidates"], as_of="2026-09-04")
    assert selected["selected_projection"]["numeric_value"] == "5000"


def test_missing_period_header_fails_closed(tmp_path: Path) -> None:
    path, sha = _write(
        tmp_path,
        """
        <html><body><p>(dollars in thousands)</p><table>
          <tr><td>Net income</td><td>1</td></tr>
          <tr><td>Depreciation and amortization</td><td>2</td></tr>
          <tr><td>Funds from Operations</td><td>5</td></tr>
        </table></body></html>
        """,
    )
    parsed = parse_primary_text_candidates_v4(
        path,
        ticker="TEST",
        cik="1",
        filing=_filing(),
        source_artifact_sha256=sha,
        source_snapshot_sha256="a" * 64,
    )
    assert not parsed["candidates"]
    assert any(row["reason"] == "UNSUPPORTED_PERIOD_BINDING" for row in parsed["rejected_rows"])


def test_candidate_tamper_is_detected(tmp_path: Path) -> None:
    path, sha = _write(tmp_path, _simple_table())
    parsed = parse_primary_text_candidates_v4(
        path,
        ticker="TEST",
        cik="1",
        filing=_filing(),
        source_artifact_sha256=sha,
        source_snapshot_sha256="a" * 64,
    )
    candidate = parsed["candidates"][0]
    assert validate_primary_text_candidate_v4(candidate) == candidate["candidate_sha256"]
    tampered = deepcopy(candidate)
    tampered["numeric_value"] = "999999"
    with pytest.raises(ValueError, match="CANDIDATE_HASH_MISMATCH"):
        validate_primary_text_candidate_v4(tampered)


def test_table_local_scale_overrides_conflicting_preceding_section(tmp_path: Path) -> None:
    path, sha = _write(
        tmp_path,
        """
        <html><body>
          <p>Unrelated amounts in millions</p>
          <table>
            <tr><td>Amounts in thousands</td><td></td></tr>
            <tr><td></td><td>Three Months Ended June 30, 2026</td></tr>
            <tr><td>Net income</td><td>1</td></tr>
            <tr><td>Depreciation and amortization</td><td>2</td></tr>
            <tr><td>Funds from Operations</td><td>5</td></tr>
          </table>
        </body></html>
        """,
    )
    parsed = parse_primary_text_candidates_v4(
        path,
        ticker="TEST",
        cik="1",
        filing=_filing(),
        source_artifact_sha256=sha,
        source_snapshot_sha256="a" * 64,
    )
    selected = select_reported_ffo_v4(parsed["candidates"], as_of="2026-09-04")
    assert selected["selected_projection"]["numeric_value"] == "5000"
    assert selected["selected_projection"]["scale"] == "THOUSANDS"


def test_explicit_actual_dollars_scale_is_supported(tmp_path: Path) -> None:
    path, sha = _write(
        tmp_path,
        """
        <html><body><table>
          <tr><td>Amounts in dollars</td><td></td></tr>
          <tr><td></td><td>Three Months Ended June 30, 2026</td></tr>
          <tr><td>Net income</td><td>1</td></tr>
          <tr><td>Depreciation and amortization</td><td>2</td></tr>
          <tr><td>Funds from Operations</td><td>5000000</td></tr>
        </table></body></html>
        """,
    )
    parsed = parse_primary_text_candidates_v4(
        path,
        ticker="TEST",
        cik="1",
        filing=_filing(),
        source_artifact_sha256=sha,
        source_snapshot_sha256="a" * 64,
    )
    selected = select_reported_ffo_v4(parsed["candidates"], as_of="2026-09-04")
    assert selected["selected_projection"]["numeric_value"] == "5000000"


def test_validly_resigned_parser_authority_mutation_is_rejected(tmp_path: Path) -> None:
    path, sha = _write(tmp_path, _simple_table())
    parsed = parse_primary_text_candidates_v4(
        path,
        ticker="TEST",
        cik="1",
        filing=_filing(),
        source_artifact_sha256=sha,
        source_snapshot_sha256="a" * 64,
    )
    candidate = deepcopy(parsed["candidates"][0])
    candidate["parser_contract_sha256"] = "f" * 64
    identity_body = {
        key: value
        for key, value in candidate.items()
        if key not in {"candidate_id", "candidate_identity_payload_sha256", "candidate_sha256"}
    }
    identity_sha = canonical_sha256(identity_body)
    candidate["candidate_identity_payload_sha256"] = identity_sha
    candidate["candidate_id"] = f"room16.reit.v4.primary.{identity_sha}"
    candidate["candidate_sha256"] = canonical_sha256(
        {key: value for key, value in candidate.items() if key != "candidate_sha256"}
    )
    with pytest.raises(ValueError, match="PARSER_AUTHORITY_MISMATCH"):
        validate_primary_text_candidate_v4(candidate)


def test_filing_after_as_of_is_rejected(tmp_path: Path) -> None:
    path, sha = _write(tmp_path, _simple_table())
    filing = _filing()
    filing["filing_date"] = "2026-09-05"
    parsed = parse_primary_text_candidates_v4(
        path,
        ticker="TEST",
        cik="1",
        filing=filing,
        source_artifact_sha256=sha,
        source_snapshot_sha256="a" * 64,
    )
    selected = select_reported_ffo_v4(parsed["candidates"], as_of="2026-09-04")
    assert selected["selected"] is None
    assert selected["receipt"]["rejected_candidates"][0]["reason"] == "FILED_AFTER_AS_OF"
