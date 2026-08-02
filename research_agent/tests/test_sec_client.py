import pytest

from research_agent.sources.sec.sec_client import SecClient, SecClientConfig


def test_sec_client_requires_user_agent_email():
    with pytest.raises(ValueError):
        SecClient(SecClientConfig(user_agent="mybot"))


def test_sec_client_accepts_identifying_user_agent():
    client = SecClient(
        SecClientConfig(user_agent="ResearchAgent contact@example.com", use_cache=False)
    )

    assert client.config.user_agent == "ResearchAgent contact@example.com"


def test_sec_client_default_cache_is_runtime_only():
    config = SecClientConfig(
        user_agent="ResearchAgent contact@example.com",
        use_cache=False,
    )

    assert config.cache_dir == ".runtime/cache/sec"


def test_sec_client_companyfacts_path_zero_pads_cik(monkeypatch):
    client = SecClient(
        SecClientConfig(user_agent="ResearchAgent contact@example.com", use_cache=False)
    )
    captured = {}

    def fake_get_json(path):
        captured["path"] = path
        return {"ok": True}

    monkeypatch.setattr(client, "get_json", fake_get_json)

    assert client.get_companyfacts("1441816") == {"ok": True}
    assert captured["path"] == "/api/xbrl/companyfacts/CIK0001441816.json"


def test_sec_company_ticker_map_uses_official_website_with_same_identity(monkeypatch):
    captured = {}

    def fake_get_json(self, path):
        captured["base_url"] = self.config.base_url
        captured["user_agent"] = self.config.user_agent
        captured["path"] = path
        return {"0": {"ticker": "GENR", "cik_str": 123}}

    monkeypatch.setattr(SecClient, "get_json", fake_get_json)
    client = SecClient(
        SecClientConfig(
            user_agent="ResearchAgent contact@example.com",
            use_cache=False,
        )
    )

    assert client.get_company_tickers()["0"]["ticker"] == "GENR"
    assert captured == {
        "base_url": "https://www.sec.gov",
        "user_agent": "ResearchAgent contact@example.com",
        "path": "/files/company_tickers.json",
    }


def test_sec_filing_uses_official_archive_with_same_identity(monkeypatch):
    captured = {}

    def fake_get_text(self, path):
        captured["base_url"] = self.config.base_url
        captured["user_agent"] = self.config.user_agent
        captured["path"] = path
        return "<html>filing</html>"

    monkeypatch.setattr(SecClient, "get_text", fake_get_text)
    client = SecClient(
        SecClientConfig(
            user_agent="ResearchAgent contact@example.com",
            use_cache=False,
        )
    )

    assert client.get_filing_html(
        cik="63908",
        accession_number="0000063908-26-000051",
        primary_document="mcd-20260331.htm",
    ) == "<html>filing</html>"
    assert captured == {
        "base_url": "https://www.sec.gov",
        "user_agent": "ResearchAgent contact@example.com",
        "path": "/Archives/edgar/data/63908/000006390826000051/mcd-20260331.htm",
    }
