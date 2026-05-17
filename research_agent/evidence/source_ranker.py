from __future__ import annotations


SOURCE_AUTHORITY_RANKS = {
    "company_ir": 1,
    "sec_filing": 1,
    "earnings_release": 1,
    "earnings_transcript": 2,
    "exchange_ohlcv": 2,
    "official_press_release": 2,
    "earnings_calendar": 3,
    "reuters": 3,
    "barrons": 3,
    "wsj": 3,
    "marketwatch": 3,
    "analyst_note": 4,
    "zacks": 5,
    "yahoo_finance": 5,
    "stockanalysis": 5,
    "finviz": 5,
    "market_data_provider": 5,
    "simply_wall_st": 6,
    "insider_monkey": 6,
    "stockstory": 6,
    "motley_fool": 6,
    "reddit": 7,
    "stocktwits": 7,
    "x_twitter": 7,
    "social_media": 7,
}


def rank_source(source_type: str) -> int:
    return SOURCE_AUTHORITY_RANKS.get(source_type, 99)


def is_vendor_source(source_type: str) -> bool:
    return rank_source(source_type) >= 5
