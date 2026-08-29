from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_agent.alpha_shared.contracts import (
    DiscoveryRequestIR,
    DiscoveredSourceCandidateIR,
    SecFilingIntentIR,
    SupplementalSourceError,
)
from research_agent.alpha_shared.source_authority import (
    NetworkResponse,
    SupplementalSourceAuthority,
    is_strict_filed_exhibit_name,
)
from research_agent.tests.test_rfc0011_shared_hardening import _policy


PARENT_ACCESSION = "0000001234-26-000009"
PARENT_NAME = "results-8k.htm"


def _candidate(name: str, *, family: str, accession: str = PARENT_ACCESSION):
    return DiscoveredSourceCandidateIR.create(
        source_family_id=family,
        issuer_cik="1234",
        accession_number=accession,
        filing_date="2026-07-28",
        report_date="2026-06-30",
        form="8-K" if family == "sec_filed_exhibit" else "8-K",
        document_name=name,
        locator=(
            "https://www.sec.gov/Archives/edgar/data/1234/"
            f"{accession.replace('-', '')}/{name}"
        ),
        parent_discovery_receipt_sha256="b" * 64,
    )


def _intent(*, earnings: bool = True):
    return SecFilingIntentIR.create(
        accession_number=PARENT_ACCESSION,
        filing_date="2026-07-28",
        report_date="2026-06-30",
        form="8-K",
        primary_document=PARENT_NAME,
        primary_document_description="8-K",
        filing_items=("2.02", "9.01") if earnings else ("8.01", "9.01"),
        intent_roles=("EARNINGS_RESULTS",) if earnings else (),
        parent_submissions_receipt_sha256="a" * 64,
    )


def _authority(tmp_path: Path, html: str, inventory: tuple[str, ...]):
    policy = _policy(as_of_date="2026-08-28", max_candidates=50)
    authority = SupplementalSourceAuthority(policy, tmp_path / "captures")
    parent = _candidate(PARENT_NAME, family="sec_primary_document")
    parent_set = authority.candidate_set((), (parent,))
    evidence = authority.capture_selected(
        parent_set,
        (parent,),
        lambda locator: NetworkResponse(
            payload=html.encode(),
            final_locator=locator,
            media_type="text/html",
            fetched_at_utc="2026-08-29T00:00:00Z",
        ),
    )
    index_locator = (
        "https://www.sec.gov/Archives/edgar/data/1234/"
        f"{PARENT_ACCESSION.replace('-', '')}/index.json"
    )
    request = DiscoveryRequestIR.create(
        request_id="index",
        policy_sha256=policy.policy_sha256,
        source_family_id="sec_filed_exhibit",
        locator=index_locator,
    )
    index = authority.capture_discovery(
        request,
        lambda locator: NetworkResponse(
            payload=json.dumps(
                {"directory": {"item": [{"name": name} for name in inventory]}}
            ).encode(),
            final_locator=locator,
            media_type="application/json",
            fetched_at_utc="2026-08-29T00:00:01Z",
        ),
    )
    return authority, parent, evidence.capture_receipts[0], index


def _html(*hrefs: tuple[str, str, str]) -> str:
    rows = "".join(
        "<tr>"
        f"<td><a style='-sec-extract:exhibit' href='{href}'>{number}</a></td>"
        f"<td><a href='{href}'>{description}</a></td>"
        "</tr>"
        for number, href, description in hrefs
    )
    return f"<html><body><table>{rows}</table></body></html>"


def test_exr_ir_001_004_reference_is_parent_and_hash_bound(tmp_path: Path):
    html = _html(("99.1", "pressreleaseq22026.htm", "Press Release"))
    authority, parent, capture, _ = _authority(
        tmp_path, html, ("results-8k.htm", "pressreleaseq22026.htm")
    )
    references = authority.derive_sec_exhibit_references(
        parent_intent=_intent(), parent_candidate=parent, parent_capture=capture
    )
    assert len(references.references) == 1
    reference = references.references[0]
    assert reference.parent_filing_intent_sha256 == _intent().intent_sha256
    assert reference.parent_document_sha256 == capture.payload_sha256
    assert reference.exhibit_number == "99.1"
    assert reference.referenced_document_name == "pressreleaseq22026.htm"
    assert reference.description == "Press Release"
    assert reference.sec_extract_exhibit_attribute is True
    assert (
        authority.derive_sec_exhibit_references(
            parent_intent=_intent(), parent_candidate=parent, parent_capture=capture
        ).reference_set_sha256
        == references.reference_set_sha256
    )


@pytest.mark.parametrize(
    "href",
    (
        "https://example.com/ex99.htm",
        "ex99.htm?download=1",
        "ex99.htm#fragment",
        "../other/ex99.htm",
        "/Archives/edgar/data/1234/ex99.htm",
    ),
)
def test_exr_ir_005_008_unsafe_href_is_blocked(tmp_path: Path, href: str):
    authority, parent, capture, _ = _authority(
        tmp_path, _html(("99.1", href, "Press Release")), ("ex99.htm",)
    )
    with pytest.raises(SupplementalSourceError, match="REIT_EXHIBIT_REFERENCE_HREF_UNSAFE"):
        authority.derive_sec_exhibit_references(
            parent_intent=_intent(), parent_candidate=parent, parent_capture=capture
        )


def test_exr_ir_009_010_non_item202_and_unbound_text_are_blocked(tmp_path: Path):
    authority, parent, capture, _ = _authority(
        tmp_path,
        "<table><tr><td>99.1</td><td>Press Release</td></tr></table>",
        ("pressrelease.htm",),
    )
    with pytest.raises(
        SupplementalSourceError, match="REIT_EXHIBIT_REFERENCE_PARENT_INTENT_MISMATCH"
    ):
        authority.derive_sec_exhibit_references(
            parent_intent=_intent(earnings=False),
            parent_candidate=parent,
            parent_capture=capture,
        )
    references = authority.derive_sec_exhibit_references(
        parent_intent=_intent(), parent_candidate=parent, parent_capture=capture
    )
    assert references.references == ()


def test_exr_idx_001_006_exact_membership_emits_v1_candidate_and_binding(tmp_path: Path):
    name = "pressreleaseq22026.htm"
    authority, parent, capture, index = _authority(
        tmp_path, _html(("99.1", name, "Press Release")), (PARENT_NAME, name)
    )
    references = authority.derive_sec_exhibit_references(
        parent_intent=_intent(), parent_candidate=parent, parent_capture=capture
    )
    candidates, bindings = authority.derive_referenced_exhibit_candidates(
        parent_intent=_intent(),
        reference_set=references,
        filing_index_receipt=index,
        issuer_cik="1234",
    )
    assert len(candidates) == len(bindings) == 1
    assert candidates[0].contract_version == 1
    assert candidates[0].source_family_id == "sec_filed_exhibit"
    assert candidates[0].document_name == name
    assert bindings[0].candidate_id == candidates[0].candidate_id
    assert bindings[0].candidate_sha256 == candidates[0].candidate_sha256
    assert bindings[0].exhibit_reference_sha256 == references.references[0].reference_sha256


def test_exr_idx_002_004_missing_or_cross_accession_membership_blocks(tmp_path: Path):
    name = "pressreleaseq22026.htm"
    authority, parent, capture, index = _authority(
        tmp_path, _html(("99.1", name, "Press Release")), (PARENT_NAME,)
    )
    references = authority.derive_sec_exhibit_references(
        parent_intent=_intent(), parent_candidate=parent, parent_capture=capture
    )
    with pytest.raises(
        SupplementalSourceError, match="REIT_EXHIBIT_REFERENCE_INDEX_MEMBERSHIP_MISSING"
    ):
        authority.derive_referenced_exhibit_candidates(
            parent_intent=_intent(),
            reference_set=references,
            filing_index_receipt=index,
            issuer_cik="1234",
        )
    with pytest.raises(
        SupplementalSourceError, match="REIT_EXHIBIT_REFERENCE_CROSS_ACCESSION_INDEX"
    ):
        authority.derive_referenced_exhibit_candidates(
            parent_intent=_intent(),
            reference_set=references,
            filing_index_receipt=index,
            issuer_cik="9999",
        )


def test_exr_sel_001_006_context_v3_uses_reference_not_filename_shape(tmp_path: Path):
    hrefs = (
        ("99.1", "pressreleaseq22026.htm", "Press Release"),
        ("99.2", "supplemental.htm", "Supplemental Information"),
    )
    inventory = (PARENT_NAME, *(item[1] for item in hrefs))
    authority, parent, capture, index = _authority(tmp_path, _html(*hrefs), inventory)
    intent = _intent()
    references = authority.derive_sec_exhibit_references(
        parent_intent=intent, parent_candidate=parent, parent_capture=capture
    )
    referenced, bindings = authority.derive_referenced_exhibit_candidates(
        parent_intent=intent,
        reference_set=references,
        filing_index_receipt=index,
        issuer_cik="1234",
    )
    current = DiscoveredSourceCandidateIR.create(
        source_family_id="sec_primary_document",
        issuer_cik="1234",
        accession_number="0000001234-26-000010",
        filing_date="2026-07-29",
        report_date="2026-06-30",
        form="10-Q",
        document_name="quarter.htm",
        locator="https://www.sec.gov/Archives/edgar/data/1234/000000123426000010/quarter.htm",
        parent_discovery_receipt_sha256="b" * 64,
    )
    random = _candidate("random-press-release.htm", family="sec_filed_exhibit")
    candidate_set = authority.candidate_set((), (current, parent, random, *referenced))
    from research_agent.alpha_shared.contracts import SecFilingIntentSetIR

    intents = SecFilingIntentSetIR.create(
        policy_sha256=authority.policy.policy_sha256,
        submissions_receipt_sha256="a" * 64,
        intents=(intent,),
    )
    context = authority.selection_context_v3(
        candidate_set, intents, (intent,), (references,), bindings
    )
    tags = dict(context.candidate_tags)
    assert tags[current.candidate_id] == "CURRENT_PRIMARY"
    assert tags[parent.candidate_id] == "ITEM_2_02_PARENT_PRIMARY"
    assert all(tags[item.candidate_id] == "ITEM_2_02_REFERENCED_EXHIBIT" for item in referenced)
    assert tags[random.candidate_id] == "OTHER_FILED_EXHIBIT"
    assert is_strict_filed_exhibit_name("pressreleaseq22026.htm") is False
    selected = authority.select(candidate_set, context)
    assert [item.document_name for item in selected] == [
        "quarter.htm",
        "pressreleaseq22026.htm",
        "supplemental.htm",
    ]
