from research_agent.reconciliation.restatement_resolver import is_amended_form, prefer_restatement
from research_agent.sources.sec.companyfacts_parser import ParsedFact


def _fact(form, filed, value):
    return ParsedFact(
        metric_name="net_income",
        value=value,
        unit="USD",
        period="FY2026",
        fy=2026,
        fp="FY",
        form=form,
        filed=filed,
        start="2025-02-01",
        end="2026-01-31",
        accession=filed,
    )


def test_is_amended_form_detects_10k_a_and_10q_a():
    assert is_amended_form("10-K/A")
    assert is_amended_form("10-Q/A")
    assert not is_amended_form("10-K")


def test_prefer_restatement_selects_latest_amendment():
    selected = prefer_restatement([
        _fact("10-K", "2026-03-01", 100),
        _fact("10-K/A", "2026-04-01", 105),
    ])

    assert selected[0].form == "10-K/A"
    assert selected[0].value == 105


def test_prefer_restatement_uses_latest_sec_comparative_across_fiscal_labels():
    original = _fact("10-Q", "2025-04-22", 4_840)
    original.fy = 2025
    original.fp = "Q1"
    original.start = "2025-01-01"
    original.end = "2025-03-31"
    original.frame = None
    original.concept = "us-gaap:Revenues"
    restated = _fact("10-Q", "2026-04-28", 4_054)
    restated.fy = 2026
    restated.fp = "Q1"
    restated.start = "2025-01-01"
    restated.end = "2025-03-31"
    restated.frame = "CY2025Q1"
    restated.concept = "us-gaap:Revenues"

    selected = prefer_restatement([original, restated])

    assert selected == [restated]


def test_prefer_restatement_keeps_distinct_sec_measurement_periods():
    first_quarter = _fact("10-Q", "2026-04-28", 4_054)
    first_quarter.start = "2025-01-01"
    first_quarter.end = "2025-03-31"
    first_quarter.concept = "us-gaap:Revenues"
    second_quarter = _fact("10-Q", "2026-07-28", 4_120)
    second_quarter.start = "2025-04-01"
    second_quarter.end = "2025-06-30"
    second_quarter.concept = "us-gaap:Revenues"

    selected = prefer_restatement([first_quarter, second_quarter])

    assert selected == [first_quarter, second_quarter]


def test_latest_regular_comparative_supersedes_older_amendment():
    amendment = _fact("10-Q/A", "2025-05-01", 4_840)
    amendment.start = "2025-01-01"
    amendment.end = "2025-03-31"
    amendment.concept = "us-gaap:Revenues"
    later_comparative = _fact("10-Q", "2026-04-28", 4_054)
    later_comparative.start = "2025-01-01"
    later_comparative.end = "2025-03-31"
    later_comparative.concept = "us-gaap:Revenues"

    selected = prefer_restatement([amendment, later_comparative])

    assert selected == [later_comparative]
