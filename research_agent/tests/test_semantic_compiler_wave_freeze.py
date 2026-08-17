from pathlib import Path

from scripts.ops.verify_semantic_compiler_wave_freeze import verify


PRODUCT_REPO = Path(__file__).resolve().parents[3] / "company-dossier-lab"


def test_semantic_compiler_wave_freeze_is_self_consistent() -> None:
    result = verify(PRODUCT_REPO)

    assert result["status"] == "PASS"
    assert not result["failed_checks"]
    assert result["ba10_authorized"] is False
    assert result["ba10_started"] is False
