from research_agent.reconciliation.fact_deduplicator import deduplicate_facts
from research_agent.sources.sec.companyfacts_parser import ParsedFact


def _fact(filed, value, form="10-Q"):
    return ParsedFact(
        metric_name="revenue",
        value=value,
        unit="USD",
        period="Q1_FY2026",
        fy=2026,
        fp="Q1",
        form=form,
        filed=filed,
        start="2025-02-01",
        end="2025-04-30",
        accession=filed,
    )


def test_deduplicator_selects_latest_filing():
    selected, warnings = deduplicate_facts([
        _fact(filed="2026-02-01", value=100),
        _fact(filed="2026-02-15", value=100),
    ])

    assert selected[0].filed == "2026-02-15"
    assert warnings == []


def test_duplicate_value_mismatch_warns():
    selected, warnings = deduplicate_facts([
        _fact(filed="2026-02-01", value=100),
        _fact(filed="2026-02-15", value=105),
    ])

    assert selected[0].value == 105
    assert any(warning["code"] == "DUPLICATE_FACT_VALUE_MISMATCH" for warning in warnings)
