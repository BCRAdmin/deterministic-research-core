from __future__ import annotations

import json

from research_agent.room16_os import projection


def _write_json(path, payload) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_authority_bundle_is_imported_as_reader_only_history(tmp_path, monkeypatch) -> None:
    """A legacy bundle is never silently promoted to the new compiler core."""

    monkeypatch.setattr(
        projection,
        "verify_authority_bundle",
        lambda _root: {"status": "pass", "blocking_failures": []},
    )
    _write_json(
        tmp_path / "authority_manifest.json",
        {
            "ticker": "ACME",
            "as_of_date": "2026-11-20",
            "generated_at": "2026-11-20T12:00:00+00:00",
            "artifacts": {
                "source_snapshot_manifest": {
                    "path": "source_snapshot_manifest.json",
                    "sha256": "a" * 64,
                },
                "source_registry": {"path": "source_registry.json", "sha256": "b" * 64},
            },
        },
    )
    _write_json(
        tmp_path / "source_snapshot_manifest.json",
        {
            "artifacts": [
                {"snapshot_id": "snapshot_acme_sec", "sha256": "c" * 64},
            ],
            "source_dispositions": [
                {
                    "source_id": "ACME_SEC",
                    "disposition": "material_evidence",
                    "snapshot_ids": ["snapshot_acme_sec"],
                    "url": "https://www.sec.gov/Archives/example",
                    "retrieved_at": {"value": "2026-11-20T11:00:00+00:00"},
                },
            ],
        },
    )
    _write_json(
        tmp_path / "source_registry.json",
        {
            "sources": [
                {"source_id": "ACME_SEC", "source_type": "sec_filing"},
            ],
        },
    )

    result = projection.project_historical_authority_bundle(tmp_path)

    assert result.migration_mode == "hash_verified_reader_only"
    assert result.dossier.quality_verdict == "historical_reference"
    assert result.dossier.historical_reader_only is True
    assert result.dossier.public_evidence_status == "blocked"
    assert result.research_run.status == "blocked"
    assert result.source_snapshots[0].private_research_rights == "blocked"
