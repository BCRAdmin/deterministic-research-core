from research_agent.research_core.validation.metric_consistency import (
    validate_forward_eps_vs_guidance,
    validate_ttm_sum,
)
from research_agent.research_core.validation.source_quality import validate_news_price_causality
from research_agent.research_core.validation.trading_logic import validate_trade_levels


def test_nvda_fcf_ttm_sum_mismatch_detected():
    quarterly_fcf = [26.19, 13.47, 22.12, 34.90]
    reported_ttm = 58.10

    issue = validate_ttm_sum("free_cash_flow", quarterly_fcf, reported_ttm)

    assert issue is not None
    assert issue["code"] == "TTM_SUM_MISMATCH"


def test_ddog_long_stop_above_entry_detected():
    issues = validate_trade_levels(
        position_type="long",
        entry=132.0,
        stop_loss=140.0,
    )

    assert any(i["code"] == "LONG_STOP_ABOVE_ENTRY" for i in issues)


def test_mdb_weak_news_price_causality_detected():
    issue = validate_news_price_causality(
        news_date="2026-04-23",
        price_move_date="2026-04-30",
    )

    assert issue is not None
    assert issue["code"] == "WEAK_NEWS_PRICE_CAUSALITY"


def test_mdb_forward_eps_guidance_mismatch_detected():
    issue = validate_forward_eps_vs_guidance(
        consensus_eps=7.05,
        guidance_low=5.75,
        guidance_high=5.93,
    )

    assert issue is not None
    assert issue["code"] == "FORWARD_EPS_GUIDANCE_MISMATCH"

