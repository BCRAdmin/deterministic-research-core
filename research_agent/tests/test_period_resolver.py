from research_agent.reconciliation.period_resolver import infer_period_type, resolve_period
from research_agent.sources.sec.companyfacts_parser import ParsedFact


def _fact(metric_name="revenue", start="2025-02-01", end="2026-01-31", fy=2026, fp="FY"):
    return ParsedFact(
        metric_name=metric_name,
        value=100,
        unit="USD",
        period="FY2026",
        fy=fy,
        fp=fp,
        form="10-K",
        filed="2026-03-01",
        start=start,
        end=end,
        accession="a",
    )


def test_revenue_is_duration_metric():
    assert infer_period_type("revenue") == "duration"


def test_cash_is_instant_metric():
    assert infer_period_type("cash_and_equivalents") == "instant"


def test_resolve_annual_period_from_fact_dates():
    resolved = resolve_period("revenue", _fact())

    assert resolved.period_label == "FY2026"
    assert resolved.period_type == "duration"
    assert resolved.period_bucket == "annual"
    assert resolved.is_annual
    assert not resolved.is_quarterly


def test_resolve_quarterly_period_from_fact_dates():
    resolved = resolve_period("revenue", _fact(start="2025-05-01", end="2025-07-31", fp="Q2"))

    assert resolved.period_label == "Q2_FY2026_quarterly"
    assert resolved.is_quarterly
    assert resolved.period_bucket == "quarterly"


def test_resolve_ytd_period_from_fact_dates():
    resolved = resolve_period(
        "revenue",
        _fact(start="2025-02-01", end="2025-10-31", fp="Q3"),
    )

    assert resolved.period_bucket == "ytd"
    assert resolved.is_ytd
