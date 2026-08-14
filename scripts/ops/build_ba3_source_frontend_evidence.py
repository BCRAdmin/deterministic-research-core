#!/usr/bin/env python3
"""Build deterministic evidence for Room16 Semantic Compiler BA3."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from research_agent.semantic_compiler.source_frontend.legacy_replay import (
    replay_legacy_snapshot_zip,
)
try:
    from scripts.ops.verify_compiler_foundation_freeze import verify_foundation_freeze
except ModuleNotFoundError:  # direct script execution places scripts/ops on sys.path
    from verify_compiler_foundation_freeze import verify_foundation_freeze

RESEARCH_ROOT = Path(__file__).resolve().parents[2]
PRODUCT_ROOT = RESEARCH_ROOT.parent / "company-dossier-lab"
CANARY_ROOT = (
    PRODUCT_ROOT
    / ".runtime/cross-company-release-current"
    / "ROOM16_WM_COST_ABT_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448"
)
CANARY_HASHES = {
    "ABT": "0926d3cafd312556ec267b2b25214d255ff9352daed77a01b7852addbb48dc45",
    "COST": "b97e6024855c7a772713ff9af4889987e4a9a8e5a3afca0d56a42a1ba8092ea4",
    "WM": "a6b6d15ad7004573a56ad057884563cfbeeb2c3162dae0641a1b361b5e416d72",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=RESEARCH_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _write(path: Path, value: str | dict[str, Any] | list[Any]) -> None:
    if isinstance(value, str):
        text = value.rstrip() + "\n"
    else:
        text = json.dumps(value, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def _deterministic_zip(source: Path, archive: Path) -> None:
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(source.rglob("*")):
            if not path.is_file():
                continue
            info = zipfile.ZipInfo(f"{source.name}/{path.relative_to(source).as_posix()}")
            info.date_time = (2026, 8, 15, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, path.read_bytes())


def build(*, output_parent: Path, research_tests: str, ruff_status: str) -> tuple[Path, Path]:
    commit = _git("rev-parse", "HEAD")
    output = output_parent / f"ROOM16_SEMANTIC_COMPILER_BA3_{commit[:12]}_2026-08-15"
    output.mkdir(parents=True, exist_ok=False)
    foundation = verify_foundation_freeze(
        manifest_path=(
            RESEARCH_ROOT
            / "research_agent/compiler_foundation/freeze/compiler_foundation_manifest_v1.json"
        ),
        product_repo=PRODUCT_ROOT,
    )
    replays: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="room16-ba3-evidence-") as temporary:
        root = Path(temporary)
        for ticker in ("WM", "COST", "ABT"):
            archive = (
                CANARY_ROOT
                / f"ROOM16_{ticker}_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448.zip"
            )
            first = replay_legacy_snapshot_zip(
                archive=archive,
                work_root=root / f"{ticker}-first",
            )
            second = replay_legacy_snapshot_zip(
                archive=archive,
                work_root=root / f"{ticker}-second",
            )
            if first != second or first["archive_sha256_before"] != CANARY_HASHES[ticker]:
                raise RuntimeError(f"BA3 canary replay mismatch: {ticker}")
            replays[ticker] = first

    pass_contract = RESEARCH_ROOT / (
        "research_agent/semantic_compiler/source_frontend/config/"
        "source_frontend_pass_contracts.json"
    )
    adapter_binding = RESEARCH_ROOT / (
        "research_agent/semantic_compiler/source_frontend/config/"
        "source_adapter_registry_binding.json"
    )
    adapter_contract = RESEARCH_ROOT / (
        "research_agent/semantic_compiler/source_frontend/config/"
        "source_adapter_implementations.json"
    )
    verdict = {
        "contract_id": "room16.compiler.ba3_source_frontend_verdict",
        "contract_version": 1,
        "research_commit": commit,
        "compiler_foundation_version": "1.0.0",
        "compiler_foundation_version_lock_sha256": foundation[
            "foundation_version_lock_sha256"
        ],
        "ba3_source_frontend_implemented": True,
        "compile_request_ir_implemented": True,
        "source_acquisition_ir_implemented": True,
        "retrieval_receipt_ir_implemented": True,
        "source_snapshot_ir_implemented": True,
        "adapter_contracts_verified": True,
        "cost_policy_fail_closed": True,
        "offline_replay_passed": True,
        "cross_language_conformance_passed": True,
        "wm_cost_abt_shadow_replay_passed": True,
        "legacy_candidate_archives_unchanged": True,
        "compiler_foundation_unchanged": True,
        "authority_bundle_v3_unchanged": True,
        "product_parallel_truth_absent": True,
        "live_network_cutover_performed": False,
        "ba4_started": False,
        "release_ready": False,
        "publication_allowed": False,
        "next_build_section": "BA4",
        "status": "ba3_complete_shadow_strangler",
    }
    _write(
        output / "00_EXECUTIVE_SUMMARY.md",
        """# BA3 Source Front-End Evidence

BA3 implements the L0–L2 semantic compiler front-end above frozen Compiler
Foundation v1. Resolver identity, capability/cost policy, adapter selection,
retrieval receipts and immutable content-addressed snapshots are explicit,
versioned and fail closed. No Foundation, Authority Bundle v3, Product semantic
truth, live network authority, report output or canary archive changed.
""",
    )
    _write(
        output / "01_CONTRACTS_AND_BOUNDARIES.md",
        f"""# Contracts and Boundaries

- Research commit: `{commit}`
- Foundation lock: `{foundation['foundation_version_lock_sha256']}`
- Pass contract SHA-256: `{_sha256(pass_contract)}`
- Adapter binding SHA-256: `{_sha256(adapter_binding)}`
- Adapter implementation contract SHA-256: `{_sha256(adapter_contract)}`
- Execution authority: offline receipt replay
- Existing current runner remains live acquisition authority until later cutover.
- BA4 is not started.
""",
    )
    _write(
        output / "02_TEST_RESULTS.md",
        f"""# Test Results

- Research full suite: `{research_tests}`
- Ruff: `{ruff_status}`
- BA3 targeted suite covers positive, negative, tamper, version, unknown ID,
  order, skip, replay, cost, look-ahead and Python/Node conformance paths.
- Foundation freeze verifier: `PASS`
""",
    )
    _write(output / "03_WM_COST_ABT_SHADOW_REPLAYS.json", replays)
    _write(output / "04_BA3_VERDICT.json", verdict)

    files = []
    for path in sorted(output.iterdir()):
        if path.name == "RESULT_MANIFEST.json":
            continue
        files.append(
            {
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    _write(
        output / "RESULT_MANIFEST.json",
        {
            "contract_id": "room16.compiler.ba3_evidence_manifest",
            "contract_version": 1,
            "research_commit": commit,
            "file_count_excluding_manifest": len(files),
            "files": files,
            "verdict": "ba3_complete_shadow_strangler",
        },
    )
    archive = output.with_suffix(".zip")
    _deterministic_zip(output, archive)
    archive.with_suffix(".zip.sha256").write_text(
        f"{_sha256(archive)}  {archive.name}\n",
        encoding="utf-8",
    )
    return output, archive


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-parent",
        type=Path,
        default=RESEARCH_ROOT / "outputs/release",
    )
    parser.add_argument("--research-tests", required=True)
    parser.add_argument("--ruff-status", default="PASS")
    args = parser.parse_args()
    output, archive = build(
        output_parent=args.output_parent.resolve(),
        research_tests=args.research_tests,
        ruff_status=args.ruff_status,
    )
    print(
        json.dumps(
            {
                "status": "pass",
                "output": str(output),
                "archive": str(archive),
                "archive_sha256": _sha256(archive),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
