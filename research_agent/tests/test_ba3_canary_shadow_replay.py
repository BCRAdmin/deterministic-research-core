from __future__ import annotations

from pathlib import Path

import pytest

from research_agent.semantic_compiler.source_frontend.legacy_replay import (
    replay_legacy_snapshot_zip,
)

PRODUCT_ROOT = Path(__file__).resolve().parents[3] / "company-dossier-lab"
CANARY_ROOT = (
    PRODUCT_ROOT
    / ".runtime/cross-company-release-current"
    / "ROOM16_WM_COST_ABT_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448"
)
EXPECTED = {
    "WM": "a6b6d15ad7004573a56ad057884563cfbeeb2c3162dae0641a1b361b5e416d72",
    "COST": "b97e6024855c7a772713ff9af4889987e4a9a8e5a3afca0d56a42a1ba8092ea4",
    "ABT": "0926d3cafd312556ec267b2b25214d255ff9352daed77a01b7852addbb48dc45",
}


@pytest.mark.parametrize("ticker", ["WM", "COST", "ABT"])
def test_accepted_canary_source_frontend_shadow_replay_is_stable(
    ticker: str,
    tmp_path: Path,
) -> None:
    archive = (
        CANARY_ROOT
        / f"ROOM16_{ticker}_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448.zip"
    )
    first = replay_legacy_snapshot_zip(
        archive=archive,
        work_root=tmp_path / "first",
    )
    second = replay_legacy_snapshot_zip(
        archive=archive,
        work_root=tmp_path / "second",
    )
    assert first == second
    assert first["archive_sha256_before"] == EXPECTED[ticker]
    assert first["archive_sha256_after"] == EXPECTED[ticker]
    assert first["candidate_archive_unchanged"] is True
    assert first["legacy_artifact_count"] == first["ba3_artifact_count"]
    assert first["all_legacy_sources_dispositioned"] is True
    assert first["all_ba3_artifacts_dispositioned"] is True
