from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from research_agent.tests.test_ba12_final_strangler_cutover import CASES as R4_CASES
from research_agent.tests.test_ba12_rfc0010_resume_delta import CASES as RFC10_CASES

ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
APP = PRODUCT / "room16-app"
CASES = tuple(f"BA12-R5-T-{index:03d}" for index in range(1, 34))
EXPECTED_BUNDLES = {
    "WM": "f1ec2e40c19553c2186586f9cce71fd97b63d0035aea25844a99a7da70b35f9b",
    "COST": "d441912511302526f8b4db5f494d00202748510e669daafad2ef22203781c637",
    "ABT": "565276cfa38d81c63caac6d2bb5d28db1c563308ff0724b6e8a1077d72be2e77",
}


@pytest.fixture(scope="module")
def product_runtime_receipt() -> dict[str, object]:
    launch = subprocess.run(
        ["node", "scripts/verify_ba12_canonical_runtime.mjs"],
        cwd=APP,
        text=True,
        capture_output=True,
        check=False,
    )
    runtime = subprocess.run(
        [
            "node",
            "--test",
            "scripts/test_ba12_native_cutover.mjs",
            "scripts/test_ba12_r5_runtime_activation.mjs",
        ],
        cwd=APP,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "launch_exit": launch.returncode,
        "launch": json.loads(launch.stdout),
        "runtime_exit": runtime.returncode,
        "runtime_output": runtime.stdout + runtime.stderr,
        "package": json.loads((APP / "package.json").read_text(encoding="utf-8")),
    }


@pytest.mark.parametrize("test_id", CASES, ids=CASES)
def test_ba12_r5_acceptance_matrix(
    test_id: str,
    product_runtime_receipt: dict[str, object],
) -> None:
    number = int(test_id[-3:])
    launch = product_runtime_receipt["launch"]
    runtime_output = str(product_runtime_receipt["runtime_output"])
    package = product_runtime_receipt["package"]
    assert product_runtime_receipt["launch_exit"] == 0
    assert product_runtime_receipt["runtime_exit"] == 0

    if number in {1, 2, 3, 4, 15, 16}:
        assert launch["status"] == "PASS"
        assert launch["canonical_runtime_count"] == 1
        assert launch["canonical_legacy_semantic_readers"] == 0
        assert launch["legacy_fallback_edges"] == 0
        assert launch["normal_launcher_targets_legacy_server"] is False
    elif 5 <= number <= 14 or 17 <= number <= 20 or number in {24, 31}:
        assert test_id in runtime_output
    elif number == 21:
        assert package["scripts"]["build"] == "node scripts/room16_locked_build.mjs"
    elif number == 22:
        assert package["scripts"]["lint"] == "tsc -b --pretty false"
    elif number == 23:
        assert "verify:ba12-runtime" in package["scripts"]["verify"]
    elif number == 25:
        for ticker, expected in EXPECTED_BUNDLES.items():
            manifest = json.loads(
                (ROOT / f"outputs/ba12/native-canaries/{ticker}/BUNDLE_MANIFEST.json").read_text()
            )
            assert manifest["bundle_sha256"] == expected
    elif number == 26:
        assert len(R4_CASES) == 50
    elif number == 27:
        assert len(RFC10_CASES) == 14
    elif number == 28:
        assert all(
            (ROOT / path).is_file()
            for path in (
                "scripts/ops/verify_semantic_compiler_wave_freeze.py",
                "scripts/ops/verify_ba10_artifact_abi_renderer_freeze.py",
                "scripts/ops/verify_ba11_canary_governance_freeze.py",
                "scripts/ops/verify_rfc0008_v2_trust_freeze.py",
                "scripts/ops/verify_rfc0009_native_trust_freeze.py",
                "scripts/ops/verify_rfc0010_freeze.py",
            )
        )
    elif number == 29:
        assert "audit" in package["scripts"]["verify:dependency-audit"]
    elif number == 30:
        assert (ROOT / "scripts/ops/verify_project_boundary_non_interference_v2.py").is_file()
    elif number in {32, 33}:
        assert (ROOT / "scripts/ops/build_ba12_r5_evidence.py").is_file()
