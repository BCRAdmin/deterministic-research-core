from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from research_agent.compiler_foundation.contracts import ContractError
from research_agent.compiler_foundation.shadow import file_sha256, shadow_replay_candidate


def make_candidate(path: Path, *, ticker: str = "FIX", version: int = 3, bad_entry: bool = False) -> str:
    root = "ROOM16_FIXTURE"
    data = b"frozen output\n"
    authority_data = json.dumps({
        "contract_id": "room16.research_authority_bundle",
        "contract_version": version,
    }).encode()
    manifest = {
        "contract_id": "room16.cross_company_release_candidate",
        "contract_version": version,
        "ticker": ticker,
        "files": [
            {"path": "case/research/final_report.md", "sha256": "0" * 64 if bad_entry else hashlib.sha256(data).hexdigest(), "bytes": len(data)},
            {"path": "case/research/authority_bundle/authority_manifest.json", "sha256": hashlib.sha256(authority_data).hexdigest(), "bytes": len(authority_data)},
        ],
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{root}/MANIFEST.json", json.dumps(manifest))
        archive.writestr(f"{root}/case/research/final_report.md", data)
        archive.writestr(f"{root}/case/research/authority_bundle/authority_manifest.json", authority_data)
    return file_sha256(path)


def test_shadow_replay_is_read_only_and_observes_all_layers(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.zip"
    digest = make_candidate(candidate)
    result = shadow_replay_candidate(candidate, ticker="FIX", expected_zip_sha256=digest)
    assert result["status"] == "pass"
    assert result["input_zip_sha256_before"] == result["input_zip_sha256_after"] == digest
    assert len(result["pass_records"]) == 12
    assert result["checks"]["no_llm_execution"] is True


@pytest.mark.parametrize("failure", ["zip_hash", "entry_hash", "version", "ticker"])
def test_shadow_replay_tamper_version_and_identity_fail_closed(tmp_path: Path, failure: str) -> None:
    candidate = tmp_path / "candidate.zip"
    digest = make_candidate(
        candidate,
        ticker="BAD" if failure == "ticker" else "FIX",
        version=2 if failure == "version" else 3,
        bad_entry=failure == "entry_hash",
    )
    if failure == "zip_hash":
        expected = "0" * 64
    else:
        expected = digest
    with pytest.raises(ContractError):
        shadow_replay_candidate(candidate, ticker="FIX", expected_zip_sha256=expected)
