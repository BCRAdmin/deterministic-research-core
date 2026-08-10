from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.evidence_ledger import EvidenceLedger
from research_agent.evidence.evidence_validator import (
    validate_claim_has_evidence,
    validate_guidance_consensus_separation,
    validate_metric_evidence,
    validate_news_event_date,
    validate_vendor_not_primary,
    validate_ledger,
)
from research_agent.research_core.models.claims import ResearchClaim


def test_missing_evidence_for_hard_metric_is_flagged():
    ledger = EvidenceLedger(ticker="MDB", as_of_date="2026-05-01", evidence_items=[])

    issue = validate_metric_evidence("free_cash_flow", ledger)

    assert issue["code"] == "MISSING_EVIDENCE_FOR_METRIC"


def test_vendor_source_for_hard_metric_warns():
    ledger = EvidenceLedger(
        ticker="MDB",
        as_of_date="2026-05-01",
        evidence_items=[
            EvidenceItem(
                evidence_id="MDB_VENDOR_FCF",
                ticker="MDB",
                claim_type="financial_metric",
                source_id="zacks_mdb",
                source_type="zacks",
                authority_rank=5,
                statement="FCF was 492.6M.",
                value=492600000,
                unit="usd",
                period="FY2026",
                supports_metrics=["free_cash_flow"],
            )
        ],
    )

    issue = validate_metric_evidence("free_cash_flow", ledger)
    vendor_issue = validate_vendor_not_primary("free_cash_flow", ledger)

    assert issue["code"] == "NO_PRIMARY_EVIDENCE_FOR_HARD_METRIC"
    assert vendor_issue["code"] == "VENDOR_SOURCE_USED_AS_PRIMARY"


def test_vendor_source_does_not_warn_when_primary_evidence_exists():
    ledger = EvidenceLedger(
        ticker="MDB",
        as_of_date="2026-05-01",
        evidence_items=[
            EvidenceItem(
                evidence_id="MDB_IR_FCF",
                ticker="MDB",
                claim_type="financial_metric",
                source_id="MDB_IR",
                source_type="company_ir",
                authority_rank=1,
                statement="Company-reported FCF.",
                value=492_600_000,
                unit="USD",
                period="FY2026",
                supports_metrics=["free_cash_flow"],
            ),
            EvidenceItem(
                evidence_id="MDB_VENDOR_FCF",
                ticker="MDB",
                claim_type="financial_metric",
                source_id="zacks_mdb",
                source_type="zacks",
                authority_rank=5,
                statement="Vendor copy of FCF.",
                value=492_600_000,
                unit="USD",
                period="FY2026",
                supports_metrics=["free_cash_flow"],
            ),
        ],
    )

    assert validate_vendor_not_primary("free_cash_flow", ledger) is None


def test_news_event_without_date_warns():
    item = EvidenceItem(
        evidence_id="MDB_NEWS_ITEM",
        ticker="MDB",
        claim_type="news",
        source_id="reuters_mdb",
        source_type="reuters",
        authority_rank=3,
        statement="MongoDB announced a product update.",
    )

    issue = validate_news_event_date(item)

    assert issue["code"] == "MISSING_DATE_FOR_NEWS_EVENT"


def test_future_news_is_blocked_by_ledger_as_of_date():
    ledger = EvidenceLedger(
        ticker="MDB",
        as_of_date="2026-05-01",
        evidence_items=[
            EvidenceItem(
                evidence_id="MDB_FUTURE_NEWS",
                ticker="MDB",
                claim_type="news",
                source_id="MDB_IR_FUTURE",
                source_type="company_ir",
                authority_rank=1,
                statement="A later publication must not enter this report.",
                date="2026-05-02",
            )
        ],
    )

    issues = validate_ledger(ledger)

    assert [issue["code"] for issue in issues] == [
        "EVIDENCE_DATE_AFTER_AS_OF_DATE"
    ]


def test_future_material_event_is_blocked_but_forward_calendar_is_allowed():
    future_material_event = EvidenceItem(
        evidence_id="MDB_FUTURE_EVENT",
        ticker="MDB",
        claim_type="event",
        source_id="MDB_IR_FUTURE_EVENT",
        source_type="company_ir",
        authority_rank=1,
        statement="A future event cannot be stated as completed evidence.",
        date="2026-05-02",
    )
    confirmed_calendar_event = future_material_event.model_copy(
        update={
            "evidence_id": "MDB_NEXT_EARNINGS",
            "supports_metrics": ["next_earnings_date", "earnings_event"],
        }
    )

    assert validate_news_event_date(
        future_material_event,
        as_of_date="2026-05-01",
    )["code"] == "EVIDENCE_DATE_AFTER_AS_OF_DATE"
    assert validate_news_event_date(
        confirmed_calendar_event,
        as_of_date="2026-05-01",
    ) is None


def test_same_day_and_past_evidence_dates_are_allowed():
    for evidence_date in ("2026-05-01", "2026-04-30T23:59:59Z"):
        item = EvidenceItem(
            evidence_id=f"MDB_NEWS_{evidence_date}",
            ticker="MDB",
            claim_type="news",
            source_id="MDB_IR",
            source_type="company_ir",
            authority_rank=1,
            statement="Evidence available by the report boundary.",
            date=evidence_date,
        )

        assert validate_news_event_date(
            item,
            as_of_date="2026-05-01",
        ) is None


def test_malformed_evidence_date_is_blocking():
    item = EvidenceItem(
        evidence_id="MDB_BAD_DATE",
        ticker="MDB",
        claim_type="news",
        source_id="MDB_IR",
        source_type="company_ir",
        authority_rank=1,
        statement="Malformed dates must fail closed.",
        date="not-a-date",
    )

    issue = validate_news_event_date(item, as_of_date="2026-05-01")

    assert issue["severity"] == "error"
    assert issue["code"] == "INVALID_EVIDENCE_DATE"


def test_guidance_and_consensus_are_separate_evidence_items():
    ledger = _build_mdb_fixture_ledger()

    guidance_items = ledger.find_by_metric("company_guidance_eps")
    consensus_items = ledger.find_by_metric("consensus_forward_eps")

    assert validate_guidance_consensus_separation(ledger) is None
    assert guidance_items[0].source_type == "company_ir"
    assert consensus_items[0].source_type in {"finviz", "stockanalysis", "market_data_provider"}


def test_guidance_consensus_conflation_is_flagged():
    ledger = EvidenceLedger(
        ticker="MDB",
        as_of_date="2026-05-01",
        evidence_items=[
            EvidenceItem(
                evidence_id="MDB_EPS_CONFLATED",
                ticker="MDB",
                claim_type="guidance",
                source_id="mixed_eps",
                source_type="zacks",
                authority_rank=5,
                statement="EPS guidance and consensus were mixed.",
                supports_metrics=["company_guidance_eps", "consensus_forward_eps"],
            )
        ],
    )

    issue = validate_guidance_consensus_separation(ledger)

    assert issue["code"] == "GUIDANCE_CONSENSUS_CONFLATION"


def test_qualitative_claim_accepts_one_exact_evidence_id():
    item = EvidenceItem(
        evidence_id="ANY_BSE_BUSINESS_CONTEXT",
        ticker="ANY",
        claim_type="event",
        source_id="BSE_ANY_PROFILE",
        source_type="company_ir",
        authority_rank=1,
        statement="ANY provides secure identity solutions.",
    )
    claim = ResearchClaim(
        agent="business_context",
        claim="ANY provides secure identity solutions.",
        evidence_metrics=[],
        evidence_ids=[item.evidence_id],
        source_ids=[item.source_id],
        confidence="high",
    )
    ledger = EvidenceLedger(
        ticker="ANY",
        as_of_date="2026-07-24",
        evidence_items=[item],
    )

    assert validate_claim_has_evidence(claim, ledger) is None


def test_qualitative_claim_rejects_missing_or_non_unique_evidence_id():
    duplicate_items = [
        EvidenceItem(
            evidence_id="ANY_BSE_BUSINESS_CONTEXT",
            ticker="ANY",
            claim_type="event",
            source_id=source_id,
            source_type="company_ir",
            authority_rank=1,
            statement="ANY provides secure identity solutions.",
        )
        for source_id in ("BSE_ANY_PROFILE", "BSE_ANY_PROFILE_COPY")
    ]
    claim = ResearchClaim(
        agent="business_context",
        claim="ANY provides secure identity solutions.",
        evidence_metrics=[],
        evidence_ids=["ANY_BSE_BUSINESS_CONTEXT", "ANY_MISSING_CONTEXT"],
        source_ids=["BSE_ANY_PROFILE"],
        confidence="high",
    )
    ledger = EvidenceLedger(
        ticker="ANY",
        as_of_date="2026-07-24",
        evidence_items=duplicate_items,
    )

    issue = validate_claim_has_evidence(claim, ledger)

    assert issue["code"] == "MISSING_EVIDENCE_FOR_CLAIM"
    assert issue["evidence_ids"] == [
        "ANY_BSE_BUSINESS_CONTEXT",
        "ANY_MISSING_CONTEXT",
    ]


def _build_mdb_fixture_ledger():
    return EvidenceLedger(
        ticker="MDB",
        as_of_date="2026-05-01",
        evidence_items=[
            EvidenceItem(
                evidence_id="MDB_IR_GUIDANCE_EPS",
                ticker="MDB",
                claim_type="guidance",
                source_id="MDB_IR_Q4_FY2026",
                source_type="company_ir",
                authority_rank=1,
                statement="Company guided FY2027 non-GAAP EPS to 5.75-5.93.",
                period="FY2027",
                supports_metrics=["company_guidance_eps"],
            ),
            EvidenceItem(
                evidence_id="MDB_CONSENSUS_FORWARD_EPS",
                ticker="MDB",
                claim_type="valuation_metric",
                source_id="market_data_provider_mdb",
                source_type="market_data_provider",
                authority_rank=5,
                statement="Consensus FY2027 EPS was 7.05.",
                value=7.05,
                period="FY2027",
                supports_metrics=["consensus_forward_eps"],
            ),
        ],
    )
