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
