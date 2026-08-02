from research_agent.evidence.source_ranker import is_vendor_source, rank_source


def test_source_ranker_orders_primary_vendor_and_social_sources():
    assert rank_source("company_ir") == 1
    assert rank_source("sec_filing") == 1
    assert rank_source("earnings_transcript") == 2
    assert rank_source("reuters") == 3
    assert rank_source("analyst_note") == 4
    assert rank_source("zacks") == 5
    assert rank_source("stockstory") == 6
    assert rank_source("reddit") == 7
    assert rank_source("unknown_blog") == 99


def test_vendor_source_detection_starts_at_rank_five():
    assert is_vendor_source("zacks")
    assert is_vendor_source("finviz")
    assert not is_vendor_source("company_ir")
    assert not is_vendor_source("deterministic_calculation")
    assert not is_vendor_source("reuters")
