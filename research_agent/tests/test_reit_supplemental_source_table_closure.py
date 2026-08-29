from __future__ import annotations

import json
from pathlib import Path

from research_agent.alpha_shared.contracts import (
    DiscoveryRequestIR,
    DiscoveredSourceCandidateIR,
    DiscoveredSourceSetIR,
    DocumentObservationIR,
)
from research_agent.alpha_shared.document_normalizer import (
    discover_observations,
    normalize_document,
)
from research_agent.alpha_shared.observation_registry import label_profiles
from research_agent.alpha_shared.source_authority import (
    NetworkResponse,
    SupplementalSourceAuthority,
)
from research_agent.alpha_shared.supplemental_semantics import (
    build_supplemental_semantics,
    classify_reit_row_role,
)
from research_agent.tests.test_fixed24_shared_coverage_correction import _observation
from research_agent.tests.test_rfc0011_r2_correction import _supplemental
from research_agent.tests.test_rfc0011_shared_hardening import _policy


def _candidate(
    *, accession: str, form: str, filed: str, report: str, name: str, family: str
) -> DiscoveredSourceCandidateIR:
    return DiscoveredSourceCandidateIR.create(
        source_family_id=family,
        issuer_cik="1234",
        accession_number=accession,
        filing_date=filed,
        report_date=report,
        form=form,
        document_name=name,
        locator=(
            f"https://www.sec.gov/Archives/edgar/data/1234/{accession.replace('-', '')}/{name}"
        ),
        parent_discovery_receipt_sha256="b" * 64,
    )


def _intent_authority(tmp_path: Path):
    policy = _policy(as_of_date="2026-08-28", max_candidates=50)
    authority = SupplementalSourceAuthority(policy, tmp_path / "capture")
    payload = json.dumps(
        {
            "cik": "1234",
            "filings": {
                "recent": {
                    "accessionNumber": [
                        "0000001234-26-000010",
                        "0000001234-26-000009",
                        "0000001234-26-000008",
                        "0000001234-26-000007",
                    ],
                    "filingDate": ["2026-07-28", "2026-07-28", "2026-08-18", "2026-07-27"],
                    "reportDate": ["2026-06-30", "2026-07-28", "2026-08-13", "2026-07-27"],
                    "form": ["10-Q", "8-K", "8-K", "8-K"],
                    "items": ["", "2.02,9.01", "1.01,7.01,9.01", "8.01,9.01"],
                    "primaryDocument": [
                        "quarter.htm",
                        "results-8k.htm",
                        "disposition-press-release.htm",
                        "other-press-release.htm",
                    ],
                    "primaryDocDescription": ["10-Q", "8-K", "8-K", "8-K"],
                }
            },
        },
        sort_keys=True,
    ).encode()
    request = DiscoveryRequestIR.create(
        request_id="submissions",
        policy_sha256=policy.policy_sha256,
        source_family_id="sec_primary_document",
        locator="https://data.sec.gov/submissions/CIK0000001234.json",
    )
    receipt = authority.capture_discovery(
        request,
        lambda locator: NetworkResponse(
            payload=payload,
            final_locator=locator,
            media_type="application/json",
            fetched_at_utc="2026-08-29T00:00:00Z",
        ),
    )
    candidates = authority.derive_sec_submission_candidates(receipt)
    candidate_set = authority.candidate_set((receipt,), candidates)
    intents = authority.derive_sec_filing_intents(receipt)
    return authority, receipt, candidate_set, intents


def test_rst_intent_001_005_exact_item202_is_only_earnings_authority(tmp_path: Path):
    authority, receipt, _, intents = _intent_authority(tmp_path)
    by_accession = {item.accession_number: item for item in intents.intents}
    assert by_accession["0000001234-26-000009"].intent_roles == ("EARNINGS_RESULTS",)
    assert by_accession["0000001234-26-000008"].intent_roles == ()
    assert by_accession["0000001234-26-000007"].intent_roles == ()
    assert all(
        item.parent_submissions_receipt_sha256 == receipt.receipt_sha256 for item in intents.intents
    )
    assert (
        authority.derive_sec_filing_intents(receipt).intent_set_sha256 == intents.intent_set_sha256
    )


def test_rst_parent_and_select_item202_context_blocks_wrong_latest_8k(tmp_path: Path):
    authority, _, candidate_set, intents = _intent_authority(tmp_path)
    parents = authority.select_item202_index_parents(candidate_set, intents)
    assert [item.accession_number for item in parents] == ["0000001234-26-000009"]

    primary = next(item for item in candidate_set.candidates if item.form == "10-Q")
    parent_primary = next(
        item
        for item in candidate_set.candidates
        if item.accession_number == parents[0].accession_number
    )
    good_exhibit = _candidate(
        accession=parents[0].accession_number,
        form="8-K",
        filed="2026-07-28",
        report="2026-07-28",
        name="ex99-1.htm",
        family="sec_filed_exhibit",
    )
    wrong_exhibit = _candidate(
        accession="0000001234-26-000008",
        form="8-K",
        filed="2026-08-18",
        report="2026-08-13",
        name="ex991-dispositionpressrele.htm",
        family="sec_filed_exhibit",
    )
    combined = DiscoveredSourceSetIR.create(
        policy_sha256=authority.policy.policy_sha256,
        discovery_receipt_sha256s=("b" * 64,),
        candidates=(*candidate_set.candidates, good_exhibit, wrong_exhibit),
    )
    context = authority.selection_context(combined, intents, parents)
    tags = dict(context.candidate_tags)
    assert tags[primary.candidate_id] == "CURRENT_PRIMARY"
    assert tags[parent_primary.candidate_id] == "ITEM_2_02_PARENT_PRIMARY"
    assert tags[good_exhibit.candidate_id] == "ITEM_2_02_EXHIBIT"
    assert tags[wrong_exhibit.candidate_id] == "OTHER_FILED_EXHIBIT"
    assert [item.candidate_id for item in authority.select(combined, context)][:3] == [
        primary.candidate_id,
        good_exhibit.candidate_id,
        parent_primary.candidate_id,
    ]


def _normalization_observations(html: str):
    document = normalize_document(
        html.encode(),
        document_id="fixture",
        accession_number="1",
        report_date="2026-06-30",
        filing_date="2026-07-22",
        document_name="ex99-1.htm",
        media_type="text/html",
    )
    return discover_observations(document, label_profiles())


def test_rst_hdr_001_004_and_row_001_002_egp_structure_resolves():
    observations = _normalization_observations(
        """
        <p>(IN THOUSANDS, EXCEPT PER SHARE DATA)</p>
        <table>
        <tr><th colspan='6'></th><th colspan='6'>Three Months Ended</th>
            <th colspan='6'></th><th colspan='6'>Six Months Ended</th></tr>
        <tr><th colspan='6'></th><th colspan='6'>June 30,</th>
            <th colspan='6'></th><th colspan='6'>June 30,</th></tr>
        <tr><th colspan='6'></th><th colspan='6'>2026</th>
            <th colspan='6'>2025</th><th colspan='6'>2026</th></tr>
        <tr><td colspan='6'>NET INCOME</td><td>$</td><td colspan='5'>75,523</td></tr>
        <tr><td colspan='6'>FUNDS FROM OPERATIONS (“FFO”) ATTRIBUTABLE TO COMMON STOCKHOLDERS *</td>
            <td colspan='6'>126,771</td></tr>
        </table>
        """
    )
    observation = next(
        item
        for item in observations
        if item.locator_type == "table_cell" and item.raw_value_text == "126,771"
    )
    assert observation.header_path == ("Three Months Ended", "June 30,", "2026")
    assert "$" not in observation.reported_period_text_or_null
    assert classify_reit_row_role(observation) == "TOTAL_MEASURE"
    candidates, resolutions = build_supplemental_semantics(
        supplemental=_supplemental(observation),
        as_of_date="2026-08-28",
        filed_date="2026-07-22",
        archetype_profile_id="reit",
    )
    assert candidates[0]["candidate"]["numeric_value"] == "126771000"
    resolved = next(item for item in resolutions if item["metric_id"] == "reported_ffo")
    assert resolved["status"] == "RESOLVED"
    assert candidates[0]["period_start_or_null"] == "2026-04-01"
    assert candidates[0]["period_end_or_null"] == "2026-06-30"


def test_rst_hdr_005_006_unrelated_month_and_percentage_are_not_period():
    observations = _normalization_observations(
        """
        <table>
        <tr><th colspan='3'>Three Months Ended</th><th colspan='3'>Six Months Ended</th></tr>
        <tr><th colspan='3'>June 30,</th><th colspan='3'></th></tr>
        <tr><th colspan='3'>2026</th><th colspan='3'>2026</th></tr>
        <tr><td>Core FFO</td><td>$</td><td>10</td><td>Core FFO</td><td>%</td><td>20</td></tr>
        </table>
        """
    )
    second = next(item for item in observations if item.column_index_or_null == 5)
    assert second.trusted_numeric is False
    assert second.reported_period_text_or_null == "Six Months Ended 2026"
    assert "%" not in second.header_path


def test_rst_row_003_008_negative_order_and_bindings_remain_closed():
    excluding = _observation(
        "funds from operations",
        "FFO attributable to common stockholders, excluding gain on sale | 126,771",
    )
    shares = _observation(
        "funds from operations",
        "Diluted shares for earnings per share and funds from operations per share | 53,783",
    )
    component_a = _observation("core ffo", "Less: noncontrolling interest in Core FFO | (5,631)")
    component_b = _observation("core ffo", "Less: participating securities Core FFO | (668)")
    assert classify_reit_row_role(excluding) == "OTHER"
    assert classify_reit_row_role(shares) == "SHARES_COUNT"
    assert classify_reit_row_role(component_a) == "COMPONENT"
    assert classify_reit_row_role(component_b) == "COMPONENT"

    no_scale = _observation("funds from operations", "Funds From Operations (FFO) | 10", context="")
    no_period = _observation(
        "funds from operations", "Funds From Operations (FFO) | 10", period=None
    )
    for observation, reason in (
        (no_scale, "SCALE_BINDING_MISSING"),
        (no_period, "PERIOD_BINDING_MISSING"),
    ):
        candidates, _ = build_supplemental_semantics(
            supplemental=_supplemental(observation),
            as_of_date="2026-08-28",
            filed_date="2026-07-22",
            archetype_profile_id="reit",
        )
        assert candidates[0]["status"] == "REJECTED"
        assert reason in candidates[0]["reason_codes"]
