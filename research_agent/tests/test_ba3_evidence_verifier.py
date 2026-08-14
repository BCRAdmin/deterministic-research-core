from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.ops.build_ba3_source_frontend_evidence import build
from scripts.ops.verify_ba3_source_frontend_evidence import verify


def test_ba3_evidence_build_verify_and_tamper(tmp_path: Path) -> None:
    output, archive = build(
        output_parent=tmp_path,
        research_tests="test fixture",
        ruff_status="PASS",
    )
    result = verify(output, archive)
    assert result["status"] == "pass"
    target = output / "04_BA3_VERDICT.json"
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["ba4_started"] = True
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="file_hash_invalid"):
        verify(output, archive)
