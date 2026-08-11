import json
import shutil
from pathlib import Path

import pytest

from research_agent.sources.earnings.official_calendar_snapshot import (
    DEFAULT_ROOT,
    materialize_official_calendar_snapshot,
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
            allow_capture_template=True,
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


def test_calendar_snapshot_rejects_declared_but_missing_raw_artifact(
    tmp_path: Path,
) -> None:
    payload = json.loads(
        (DEFAULT_ROOT / "WM_2026-08-10.json").read_text(encoding="utf-8")
    )
    source = payload["sources_checked"][0]
    source["snapshot_artifact"] = {
        "path": "evidence/missing.md",
        "sha256": "0" * 64,
        "bytes": 42,
        "media_type": "text/markdown",
        "retrieved_at": "2026-08-10T20:30:00+00:00",
    }
    result = verify_official_calendar_snapshot(
        payload,
        ticker="WM",
        as_of_date="2026-08-10",
        snapshot_root=tmp_path,
    )
    assert result["verified"] is False
    assert "calendar_physical_snapshot_integrity" in result["blocking_failures"]


def test_current_wm_calendar_preserves_proxy_transport_limit() -> None:
    path = DEFAULT_ROOT / "WM_2026-08-11.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    result = verify_official_calendar_snapshot(
        payload,
        ticker="WM",
        as_of_date="2026-08-11",
        snapshot_root=path.parent,
    )
    assert result["verified"] is True
    assert result["content_snapshot_verified"] is True
    assert result["origin_capture_verified"] is False
    assert result["transport_assurance"] == (
        "proxy_observation_origin_response_unverified"
    )


def test_past_calendar_template_cannot_be_live_reconstructed(tmp_path: Path) -> None:
    source = DEFAULT_ROOT / "WM_2026-08-10.json"
    template = tmp_path / source.name
    shutil.copy2(source, template)

    with pytest.raises(ValueError, match="cannot be reconstructed"):
        materialize_official_calendar_snapshot(
            template,
            output_root=tmp_path / "runtime",
            user_agent="Room16 test",
        )
