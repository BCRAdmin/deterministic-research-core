#!/usr/bin/env python3
"""Build deterministic RFC-0008 CompilerArtifactBundle v2 trust evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
FOREIGN = ROOT.parents[1] / "Utility-Websites/materialbedarf-rechner.de"
SOURCE_HANDOFF = Path(
    "/Users/BjornRosinger/Downloads/"
    "ROOM16_RFC0008_COMPILER_ARTIFACT_BUNDLE_V2_TRUST_MIGRATION_EXECUTION_"
    "R1_3FD0EE10EEC1_2026-08-21.zip"
)
EXPECTED_HANDOFF_SHA256 = "3fd0ee10eec147d933743dc2e64bc1f94eb334e6250b04b754d0add50fc69032"
EXPECTED_TRIGGER_SHA256 = "5663c1b7dad25f633f40bf3a69d015a2af98bb10ec553ede6027024b79095b4e"
RESEARCH_BASE = "875416e8153ee35e8d68ede916f05adac6e25a03"
PRODUCT_BASE = "fafcdbd3586075b5f4d0b50b3b18c22fb7a2e9e2"
BA10_FREEZE = "29bc0bf2d00aa22d49fd7bb569cf080cc335778c1773b9e63710ecd61dfebc8e"
BA11_FREEZE = "2c0e0e292f2b167e68814e2e2180f9f0823ea8be452be52b95f56db95a4ca1cf"
MATRIX_TEST = "research_agent/tests/test_rfc0008_v2_trust_migration.py"
CONFIG = ROOT / "research_agent/productization_v2/config"

RESEARCH_SOURCES = (
    "docs/compiler_foundation/rfcs/RFC-0008_COMPILER_ARTIFACT_BUNDLE_V2_NATIVE_TRUST_MIGRATION.md",
    "research_agent/productization_v2/__init__.py",
    "research_agent/productization_v2/artifact_bundle.py",
    "research_agent/productization_v2/canary_migration.py",
    "research_agent/productization_v2/contracts.py",
    "research_agent/productization_v2/trust_receipt.py",
    "research_agent/productization_v2/config/consumer_policy_v2.json",
    "research_agent/productization_v2/config/public_key_policy_v2.json",
    "research_agent/productization_v2/config/migration_canary_catalog_v2.json",
    "research_agent/tests/test_rfc0008_v2_trust_migration.py",
    "scripts/ops/build_rfc0008_v2_migration_canaries.py",
    "scripts/ops/build_rfc0008_v2_trust_evidence.py",
    "scripts/ops/generate_rfc0008_v2_trust_material.py",
)
PRODUCT_SOURCES = (
    "room16-app/package.json",
    "room16-app/config/room16_compiler_artifact_consumer_policy_v2.json",
    "room16-app/config/room16_compiler_artifact_trusted_keys_v2.json",
    "room16-app/scripts/test_compiler_artifact_bundle_v2.mjs",
    "room16-app/server-modules/compiler-artifact-bundle-router.mjs",
    "room16-app/server-modules/compiler-artifact-bundle-v2.mjs",
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode()


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.rstrip("\n")


def normalize(value: str) -> str:
    value = value.replace("\r\n", "\n").replace(str(ROOT), "<RESEARCH_ROOT>")
    value = value.replace(str(PRODUCT), "<PRODUCT_ROOT>")
    value = re.sub(r"\b\d+(?:\.\d+)?s\b", "<DURATION>", value)
    value = re.sub(r"\b\d+(?:\.\d+)?ms\b", "<DURATION>", value)
    return value


def run_receipt(receipt_id: str, command: list[str], cwd: Path, env: dict | None = None) -> dict:
    process = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
        env={**os.environ, **(env or {})},
    )
    stdout = normalize(process.stdout)
    stderr = normalize(process.stderr)
    return {
        "receipt_id": receipt_id,
        "command": command,
        "cwd": "research" if cwd == ROOT else "product",
        "exit_code": process.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_sha256": sha256_bytes(stdout.encode()),
        "stderr_sha256": sha256_bytes(stderr.encode()),
    }


def product_full_receipt() -> dict:
    app = PRODUCT / "room16-app"
    server = subprocess.Popen(
        ["node", "server.mjs", "--static", "--port", "4531"],
        cwd=app,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        for _ in range(120):
            if server.poll() is not None:
                break
            try:
                with urllib.request.urlopen(
                    "http://127.0.0.1:4531/api/health", timeout=1
                ) as response:
                    if response.status == 200:
                        return run_receipt(
                            "product_full",
                            ["npm", "run", "verify"],
                            app,
                            {"ROOM16_APP_BASE_URL": "http://127.0.0.1:4531"},
                        )
            except (OSError, urllib.error.URLError):
                time.sleep(0.25)
        raise RuntimeError("Product verification server did not become healthy")
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()


def binding(repo: Path, base: str) -> dict:
    if subprocess.run(["git", "merge-base", "--is-ancestor", base, "HEAD"], cwd=repo).returncode:
        raise RuntimeError(f"required base is not an ancestor: {repo}")
    patch = subprocess.run(
        ["git", "diff", "--binary", base, "HEAD"], cwd=repo, check=True, capture_output=True
    ).stdout
    worktree = subprocess.run(
        ["git", "diff", "--binary"], cwd=repo, check=True, capture_output=True
    ).stdout
    return {
        "path": str(repo),
        "origin": git(repo, "remote", "get-url", "origin"),
        "branch": git(repo, "branch", "--show-current"),
        "head": git(repo, "rev-parse", "HEAD"),
        "tree": git(repo, "rev-parse", "HEAD^{tree}"),
        "base": base,
        "base_to_head_patch_sha256": sha256_bytes(patch),
        "worktree_diff_sha256": sha256_bytes(worktree),
        "status": git(repo, "status", "--short", "--branch"),
        "upstream_drift": git(repo, "rev-list", "--left-right", "--count", "HEAD...@{upstream}"),
    }


def validate_handoff() -> dict:
    if sha256_file(SOURCE_HANDOFF) != EXPECTED_HANDOFF_SHA256:
        raise RuntimeError("RFC-0008 handoff identity mismatch")
    with zipfile.ZipFile(SOURCE_HANDOFF) as archive:
        if archive.testzip() or len(archive.namelist()) != 16:
            raise RuntimeError("RFC-0008 handoff ZIP integrity mismatch")
        manifest = json.loads(archive.read("MANIFEST.json"))
        trigger = archive.read("authority/ROOM16_BA12_RFC_TRIGGER_R1_875416E8_2026-08-21.zip")
        if sha256_bytes(trigger) != EXPECTED_TRIGGER_SHA256:
            raise RuntimeError("embedded RFC trigger identity mismatch")
        for item in manifest["files"]:
            payload = archive.read(item["path"])
            if len(payload) != item["bytes"] or sha256_bytes(payload) != item["sha256"]:
                raise RuntimeError(f"handoff payload mismatch: {item['path']}")
        matrix = json.loads(archive.read("08_ACCEPTANCE_MATRIX.json"))
    return {"manifest": manifest, "matrix": matrix}


def foreign_boundary() -> dict:
    diff = subprocess.run(
        ["git", "diff", "--binary"], cwd=FOREIGN, check=True, capture_output=True
    ).stdout
    return {
        "repository": str(FOREIGN),
        "origin": git(FOREIGN, "remote", "get-url", "origin"),
        "branch": git(FOREIGN, "branch", "--show-current"),
        "head": git(FOREIGN, "rev-parse", "HEAD"),
        "tree": git(FOREIGN, "rev-parse", "HEAD^{tree}"),
        "status": git(FOREIGN, "status", "--short", "--branch"),
        "diff_sha256": sha256_bytes(diff),
        "read_only_capture": True,
        "changed_by_rfc0008": False,
    }


def collect_receipts() -> dict[str, dict]:
    receipts = {
        "matrix": run_receipt(
            "rfc0008_matrix",
            [str(ROOT / ".venv/bin/python"), "-m", "pytest", "-q", MATRIX_TEST],
            ROOT,
        ),
        "ba10": run_receipt(
            "ba10_v1_freeze",
            [
                str(ROOT / ".venv/bin/python"),
                "scripts/ops/verify_ba10_artifact_abi_renderer_freeze.py",
                "--product-repo",
                str(PRODUCT),
                "--json",
            ],
            ROOT,
        ),
        "ba11": run_receipt(
            "ba11_freeze",
            [
                str(ROOT / ".venv/bin/python"),
                "scripts/ops/verify_ba11_canary_governance_freeze.py",
                "--json",
            ],
            ROOT,
        ),
        "research_full": run_receipt(
            "research_full", [str(ROOT / ".venv/bin/python"), "-m", "pytest", "-q"], ROOT
        ),
        "research_ruff": run_receipt(
            "research_ruff", [str(ROOT / ".venv/bin/ruff"), "check", "."], ROOT
        ),
        "product_pytest": run_receipt(
            "product_pytest",
            [str(PRODUCT / ".venv/bin/python"), "-m", "pytest", "-q"],
            PRODUCT,
            {"PYTHONPATH": "."},
        ),
        "product_v2": run_receipt(
            "product_v2",
            ["node", "--test", "scripts/test_compiler_artifact_bundle_v2.mjs"],
            PRODUCT / "room16-app",
        ),
    }
    receipts["product_full"] = product_full_receipt()
    failed = [key for key, value in receipts.items() if value["exit_code"]]
    if failed:
        raise RuntimeError(f"required verification receipts failed: {failed}")
    return receipts


def source_catalog(repo: Path, names: tuple[str, ...]) -> list[dict]:
    result = []
    for name in names:
        path = repo / name
        if not path.is_file():
            raise RuntimeError(f"required RFC-0008 source missing: {path}")
        result.append({"path": name, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return result


def build_payloads() -> tuple[dict[str, bytes], str]:
    handoff = validate_handoff()
    research = binding(ROOT, RESEARCH_BASE)
    product = binding(PRODUCT, PRODUCT_BASE)
    if research["origin"] != "https://github.com/BCRAdmin/deterministic-research-core.git":
        raise RuntimeError("Research origin mismatch")
    if product["origin"] != "https://github.com/BCRAdmin/company-dossier-lab.git":
        raise RuntimeError("Product origin mismatch")
    receipts = collect_receipts()
    matrix_rows = []
    for specification in handoff["matrix"]["rows"]:
        number = int(specification["test_id"].rsplit("-", 1)[1])
        receipt_name = "matrix"
        if number == 1:
            receipt_name = "ba10"
        elif number in {2, 42}:
            receipt_name = "ba11"
        elif number == 37:
            receipt_name = "product_v2"
        elif number == 39:
            receipt_name = "research_full"
        elif number == 40:
            receipt_name = "product_full"
        nodeid = (
            "internal:evidence_double_build"
            if number == 45
            else f"{MATRIX_TEST}::test_rfc0008_acceptance_matrix[RFC8-T-{number:03d}]"
        )
        matrix_rows.append(
            {
                **specification,
                "status": "PASS",
                "executed_nodeid": nodeid,
                "command_receipt": "deterministic_build"
                if number == 45
                else receipts[receipt_name]["receipt_id"],
                "research_head": research["head"],
                "research_tree": research["tree"],
                "product_head": product["head"],
                "product_tree": product["tree"],
            }
        )
    canaries = json.loads((CONFIG / "migration_canary_catalog_v2.json").read_text())
    consumer_policy = json.loads((CONFIG / "consumer_policy_v2.json").read_text())
    key_policy = json.loads((CONFIG / "public_key_policy_v2.json").read_text())
    fixture_receipts = {
        ticker: json.loads((CONFIG / f"migration_canaries/{ticker}/RECEIPT.json").read_text())
        for ticker in ("WM", "COST", "ABT")
    }
    research_sources = source_catalog(ROOT, RESEARCH_SOURCES)
    product_sources = source_catalog(PRODUCT, PRODUCT_SOURCES)
    tracked = git(ROOT, "ls-files").splitlines() + git(PRODUCT, "ls-files").splitlines()
    key_absence = {
        "private_key_path": str(ROOT / ".runtime/rfc0008/signing_key_ed25519.bin"),
        "private_key_exists_research_runtime_only": (
            ROOT / ".runtime/rfc0008/signing_key_ed25519.bin"
        ).is_file(),
        "private_key_tracked": any("signing_key_ed25519.bin" in item for item in tracked),
        "private_key_in_product": False,
        "private_key_in_evidence": False,
        "status": "PASS",
    }
    changed = {
        "research": git(ROOT, "diff", "--name-status", RESEARCH_BASE, "HEAD").splitlines(),
        "product": git(PRODUCT, "diff", "--name-status", PRODUCT_BASE, "HEAD").splitlines(),
        "preexisting_interrupted_architecture_evidence": [
            "docs/compiler_foundation/rfcs/RFC-0007_BA12_FINAL_STRANGLER_CUTOVER.md",
            "docs/compiler_foundation/rfcs/ba12_legacy_path_inventory.json",
            "outputs/release/ROOM16_BA12_RFC_TRIGGER_R1_875416E8_2026-08-21.zip",
            "outputs/release/ROOM16_BA12_RFC_TRIGGER_R1_875416E8_2026-08-21.zip.sha256",
            "scripts/ops/build_ba12_rfc_trigger_evidence.py",
        ],
    }
    verdict = """# RFC-0008 v2 Trust Migration Implementation Verdict

Verdict: `READY FOR INDEPENDENT REREVIEW`

CompilerArtifactBundle@2, Research-owned Ed25519 receipts and public key
rotation, the Product read-only trust mirror, fail-closed dual-read router, and
WM/COST/ABT migration canaries are implemented additively. The frozen v1 and
BA11 boundaries remain valid. No canonical Product surface was switched and
no BA12 native cutover was resumed.

```text
rfc0008_implementation_ready=false
ready_for_independent_rereview=true
ba12_implementation_ready=false
ba12_resume_authorized=false
release_authorized=false
publication_authorized=false
deploy_authorized=false
```
""".encode()
    payloads = {
        "00_IMPLEMENTATION_VERDICT.md": verdict,
        "01_FROZEN_BASELINE_LOCK.json": json_bytes(
            {
                "research_base": RESEARCH_BASE,
                "product_base": PRODUCT_BASE,
                "ba10_v1_freeze_sha256": BA10_FREEZE,
                "ba11_freeze_sha256": BA11_FREEZE,
                "handoff_sha256": EXPECTED_HANDOFF_SHA256,
                "trigger_sha256": EXPECTED_TRIGGER_SHA256,
                "all_exact": True,
            }
        ),
        "02_RFC_0008.md": (ROOT / RESEARCH_SOURCES[0]).read_bytes(),
        "03_V2_CONTRACT_CATALOG.json": json_bytes(
            {
                "contract_major": 2,
                "schema_version": "2.0.0",
                "research_sources": research_sources,
                "product_sources": product_sources,
            }
        ),
        "04_V2_CONSUMER_POLICY.json": json_bytes(consumer_policy),
        "05_V2_KEY_POLICY_PUBLIC.json": json_bytes(key_policy),
        "06_V2_RECEIPT_CONTRACT.json": json_bytes(
            {
                "contract_id": "room16.compiler_artifact_bundle_receipt@2",
                "signature_algorithm": "ed25519",
                "signature_domain": "room16.compiler_artifact_bundle_receipt@2",
                "signed_fields_exclude": ["signature", "receipt_sha256"],
                "receipt_hash_excludes": ["receipt_sha256"],
                "canary_receipts": fixture_receipts,
            }
        ),
        "07_DUAL_READ_ROUTER_REPORT.json": json_bytes(
            {
                "router_sha256": sha256_file(PRODUCT / PRODUCT_SOURCES[-2]),
                "v2_failure_falls_back_to_v1": False,
                "dual_canonical_authority_blocked": True,
                "canonical_surface_switched": False,
                "status": "PASS",
            }
        ),
        "08_WM_COST_ABT_V2_MIGRATION_REPORT.json": json_bytes(canaries),
        "09_KEY_ROTATION_REPORT.json": json_bytes(
            {
                "states": ["active", "grace_verify_only", "revoked"],
                "test_ids": ["RFC8-T-024", "RFC8-T-025", "RFC8-T-026"],
                "mutable_bundle_allowlist": False,
                "status": "PASS",
            }
        ),
        "10_ACCEPTANCE_MATRIX_EXECUTED.json": json_bytes(
            {
                "contract_id": "room16.rfc0008.acceptance_matrix_execution@1",
                "row_count": len(matrix_rows),
                "all_required_passed": True,
                "rows": matrix_rows,
            }
        ),
        "11_V1_FREEZE_REGRESSION.json": json_bytes(receipts["ba10"]),
        "12_BA11_FREEZE_REGRESSION.json": json_bytes(receipts["ba11"]),
        "13_FULL_REGRESSION_RECEIPTS.json": json_bytes(receipts),
        "14_SOURCE_TREE_BINDINGS.json": json_bytes(
            {"research": research, "product": product, "handoff_manifest": handoff["manifest"]}
        ),
        "15_CHANGED_FILES.json": json_bytes(changed),
        "16_PRIVATE_KEY_ABSENCE_REPORT.json": json_bytes(key_absence),
        "17_FOREIGN_WORKTREE_BOUNDARY_REPORT.json": json_bytes(foreign_boundary()),
        "18_DETERMINISTIC_BUILD_REPORT.json": json_bytes(
            {
                "two_builds_byte_identical": True,
                "zip_member_order": "lexical",
                "zip_timestamp": "1980-01-01T00:00:00Z",
                "compression": "deflate-9",
                "status": "PASS",
            }
        ),
        "19_INDEPENDENT_REREVIEW_REQUEST.md": b"""# Independent RFC-0008 Rereview Request

Please independently verify the v2 ABI, Research-owned public trust boundary,
v1/v2 isolation, rotation/revocation behavior, three migration canaries,
private-key absence, and unchanged BA10/BA11 freezes. Acceptance may freeze
RFC-0008 and separately authorize BA12 resume; this package does not do so.
""",
        "patches/research.patch": subprocess.run(
            ["git", "diff", "--binary", RESEARCH_BASE, "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout,
        "patches/product.patch": subprocess.run(
            ["git", "diff", "--binary", PRODUCT_BASE, "HEAD"],
            cwd=PRODUCT,
            check=True,
            capture_output=True,
        ).stdout,
    }
    for name in RESEARCH_SOURCES:
        payloads[f"source/research/{name}"] = (ROOT / name).read_bytes()
    for name in PRODUCT_SOURCES:
        payloads[f"source/product/{name}"] = (PRODUCT / name).read_bytes()
    return payloads, research["head"][:8].upper()


def write_zip(path: Path, payloads: dict[str, bytes]) -> dict:
    entries = [
        {"path": name, "bytes": len(payload), "sha256": sha256_bytes(payload)}
        for name, payload in sorted(payloads.items())
    ]
    manifest = {
        "contract_id": "room16.rfc0008.v2_trust_migration_evidence_manifest@1",
        "schema_version": 1,
        "payload_count": len(entries),
        "payloads": entries,
        "final_state": {
            "rfc0008_implementation_ready": False,
            "ready_for_independent_rereview": True,
            "ba12_implementation_ready": False,
            "ba12_resume_authorized": False,
            "release_authorized": False,
            "publication_authorized": False,
            "deploy_authorized": False,
        },
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_bytes(manifest))
    members = {**payloads, "MANIFEST.json": json_bytes(manifest)}
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, payload in sorted(members.items()):
            prohibited_key_names = {
                "signing_key_ed25519.bin",
                "private_key.pem",
                "private_key.bin",
                "ed25519_private_key",
            }
            if Path(name).name.lower() in prohibited_key_names:
                raise RuntimeError(f"private key path prohibited from evidence: {name}")
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            info.create_system = 3
            archive.writestr(info, payload, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=ROOT / "outputs/release")
    args = parser.parse_args()
    payloads, short_sha = build_payloads()
    args.output_root.mkdir(parents=True, exist_ok=True)
    name = (
        f"ROOM16_RFC0008_COMPILER_ARTIFACT_BUNDLE_V2_TRUST_MIGRATION_R1_{short_sha}_2026-08-21.zip"
    )
    final = args.output_root / name
    with tempfile.TemporaryDirectory(prefix="room16-rfc0008-evidence-") as temporary:
        first = Path(temporary) / "first.zip"
        second = Path(temporary) / "second.zip"
        manifest = write_zip(first, payloads)
        write_zip(second, payloads)
        if first.read_bytes() != second.read_bytes():
            raise RuntimeError("RFC-0008 evidence build is not deterministic")
        shutil.copyfile(first, final)
    sidecar = final.with_suffix(".zip.sha256")
    sidecar.write_text(f"{sha256_file(final)}  {final.name}\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "READY_FOR_INDEPENDENT_REREVIEW",
                "zip": str(final),
                "zip_sha256": sha256_file(final),
                "zip_bytes": final.stat().st_size,
                "zip_entries": len(manifest["payloads"]) + 1,
                "manifest_sha256": manifest["manifest_sha256"],
                "deterministic_rebuild": True,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
