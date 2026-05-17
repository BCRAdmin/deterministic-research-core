import pytest

from research_agent.sources.sec.cik_mapper import CikMapper, CikRecord


def test_cik_mapper_resolves_ticker():
    mapper = CikMapper([
        CikRecord(ticker="MDB", cik="1441816", company_name="MongoDB Inc."),
        CikRecord(ticker="DDOG", cik="1561550", company_name="Datadog, Inc."),
    ])

    assert mapper.get_cik("MDB") == "1441816"
    assert mapper.get_cik("ddog") == "1561550"
    assert mapper.get_company_name("MDB") == "MongoDB Inc."


def test_cik_mapper_unknown_ticker_raises_clear_error():
    mapper = CikMapper([])

    with pytest.raises(KeyError, match="No CIK found"):
        mapper.get_cik("UNKNOWN")
