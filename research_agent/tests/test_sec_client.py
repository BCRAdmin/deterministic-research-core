import pytest

from research_agent.sources.sec.sec_client import SecClient, SecClientConfig


def test_sec_client_requires_user_agent_email():
    with pytest.raises(ValueError):
        SecClient(SecClientConfig(user_agent="mybot"))


def test_sec_client_accepts_identifying_user_agent():
    client = SecClient(SecClientConfig(user_agent="ResearchAgent contact@example.com", use_cache=False))

    assert client.config.user_agent == "ResearchAgent contact@example.com"


def test_sec_client_companyfacts_path_zero_pads_cik(monkeypatch):
    client = SecClient(SecClientConfig(user_agent="ResearchAgent contact@example.com", use_cache=False))
    captured = {}

    def fake_get_json(path):
        captured["path"] = path
        return {"ok": True}

    monkeypatch.setattr(client, "get_json", fake_get_json)

    assert client.get_companyfacts("1441816") == {"ok": True}
    assert captured["path"] == "/api/xbrl/companyfacts/CIK0001441816.json"
