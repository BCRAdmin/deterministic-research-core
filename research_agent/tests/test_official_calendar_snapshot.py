import json
from pathlib import Path

from research_agent.sources.earnings.official_calendar_snapshot import (
    DEFAULT_ROOT,
    resolve_official_calendar_snapshot,
    verify_official_calendar_snapshot,
)


def test_registered_wm_cost_abt_snapshots_are_point_in_time_valid() -> None:
    for ticker in ("WM", "COST", "ABT"):
        path = resolve_official_calendar_snapshot(ticker, "2026-08-10")
        assert path == DEFAULT_ROOT / f"{ticker}_2026-08-10.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert verify_official_calendar_snapshot(
            payload,
            ticker=ticker,
            as_of_date="2026-08-10",
        )["verified"] is True


def test_calendar_snapshot_rejects_unconfirmed_vendor_style_event(tmp_path: Path) -> None:
    payload = json.loads(
        (DEFAULT_ROOT / "COST_2026-08-10.json").read_text(encoding="utf-8")
    )
    payload["events"][0]["confirmed"] = False
    payload["events"][0]["source_type"] = "market_data_vendor"
    result = verify_official_calendar_snapshot(
        payload,
        ticker="COST",
        as_of_date="2026-08-10",
    )
    assert result["verified"] is False
    assert "calendar_event_authority" in result["blocking_failures"]


def test_calendar_snapshot_rejects_hindsight_capture() -> None:
    payload = json.loads(
        (DEFAULT_ROOT / "WM_2026-08-10.json").read_text(encoding="utf-8")
    )
    payload["checked_at"] = "2026-08-11T00:00:00+00:00"
    result = verify_official_calendar_snapshot(
        payload,
        ticker="WM",
        as_of_date="2026-08-10",
    )
    assert result["verified"] is False
    assert "calendar_point_in_time_capture" in result["blocking_failures"]
