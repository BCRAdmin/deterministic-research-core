from pathlib import Path

from research_agent.research_core.ingestion.news_loader import (
    load_news,
    news_evidence_items,
)


def test_official_news_manifest_becomes_coverage_and_evidence(tmp_path: Path):
    source = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "official_news"
        / "MCD_news.json"
    )
    (tmp_path / source.name).write_text(
        source.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    events = load_news("MCD", tmp_path)
    evidence = news_evidence_items("MCD", events)

    assert events[0]["event_type"] == "coverage_manifest"
    assert events[0]["status"] == "complete"
    assert len(evidence) == 3
    assert {item.source_id for item in evidence} == {
        "MCD_IR_Q1_2026_RESULTS",
        "MCD_IR_NEXT_2026",
        "SEC_0000063908_2026_Q1_OUTLOOK",
    }
    assert all(item.claim_type == "news" for item in evidence)


def test_missing_official_news_manifest_is_explicitly_empty(tmp_path: Path):
    assert load_news("MISSING", tmp_path) == []
