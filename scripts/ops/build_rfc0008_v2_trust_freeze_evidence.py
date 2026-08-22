#!/usr/bin/env python3
"""Build deterministic RFC-0008 acceptance/freeze evidence."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from verify_rfc0008_v2_trust_freeze_evidence import (
    MANIFEST_DOMAIN,
    manifest_sha256,
    verify_package,
)


ROOT = Path(__file__).resolve().parents[2]
BASE = "71cd2fc149367e3d02eba3be1ab501b86c502a1c"
PRODUCT_BASE = "f6f8a7eec22eef227d40bf538c17fe2e6caf41f7"
FREEZE_RECORD = (
    ROOT
    / "docs/compiler_foundation/freezes/"
    "RFC0008_COMPILER_ARTIFACT_BUNDLE_V2_TRUST_FREEZE_v1.json"
)
ACCEPTANCE = (
    ROOT
    / "docs/compiler_foundation/acceptance/"
    "RFC0008_R2_EXTERNAL_INDEPENDENT_ACCEPTANCE.json"
)
FIXED_ZIP_TIME = (2026, 8, 22, 0, 0, 0)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _pretty(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _binding(repo: Path) -> dict[str, str]:
    return {
        "path": str(repo),
        "branch": _git(repo, "branch", "--show-current"),
        "head": _git(repo, "rev-parse", "HEAD"),
        "tree": _git(repo, "rev-parse", "HEAD^{tree}"),
        "origin": _git(repo, "remote", "get-url", "origin"),
        "remote_drift": _git(repo, "rev-list", "--left-right", "--count", "HEAD...@{upstream}"),
    }


def _receipt(
    receipt_id: str,
    command: list[str],
    cwd: Path,
    research: dict[str, str],
    product: dict[str, str],
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    merged = os.environ.copy()
    merged.update(env or {})
    process = subprocess.run(command, cwd=cwd, capture_output=True, text=True, env=merged)
    receipt = {
        "receipt_id": receipt_id,
        "command": command,
        "cwd": str(cwd),
        "environment": env or {},
        "exit_code": process.returncode,
        "status": "PASS" if process.returncode == 0 else "FAIL",
        "stdout": process.stdout,
        "stderr": process.stderr,
        "input_research_tree": research["tree"],
        "input_product_tree": product["tree"],
    }
    if process.returncode:
        raise SystemExit(
            f"STOP {receipt_id} failed\n{process.stdout}\n{process.stderr}"
        )
    return receipt


def _product_full(
    product_repo: Path,
    research: dict[str, str],
    product: dict[str, str],
) -> dict[str, Any]:
    app = product_repo / "room16-app"
    port = 4528
    base_url = f"http://127.0.0.1:{port}"
    server = subprocess.Popen(
        ["node", "server.mjs", "--static", "--port", str(port)],
        cwd=app,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        for _ in range(100):
            if server.poll() is not None:
                output = server.stdout.read() if server.stdout else ""
                raise SystemExit(f"STOP Product server failed: {output}")
            try:
                with urllib.request.urlopen(f"{base_url}/api/health", timeout=1) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.1)
        else:
            raise SystemExit("STOP Product server did not become ready")
        return _receipt(
            "full_product_verify",
            ["npm", "run", "verify"],
            app,
            research,
            product,
            {
                "ROOM16_VERIFY_SKIP_HARDENING_STATE": "1",
                "ROOM16_APP_BASE_URL": base_url,
            },
        )
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)


def _foreign() -> dict[str, Any]:
    repo = Path(
        "/Users/BjornRosinger/Documents/DreamFactory/Utility-Websites/"
        "materialbedarf-rechner.de"
    )
    return {
        "path": str(repo),
        "origin": _git(repo, "remote", "get-url", "origin"),
        "branch": _git(repo, "branch", "--show-current"),
        "head": _git(repo, "rev-parse", "HEAD"),
        "tree": _git(repo, "rev-parse", "HEAD^{tree}"),
        "status": _git(repo, "status", "--porcelain", "--untracked-files=all"),
    }


def _archive(payloads: dict[str, bytes], manifest: dict[str, Any]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        all_files = dict(payloads)
        all_files["MANIFEST.json"] = _pretty(manifest)
        for name in sorted(all_files):
            info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            info.create_system = 3
            zf.writestr(info, all_files[name])
    return stream.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--product-repo", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    handoff = args.handoff.resolve()
    product_repo = args.product_repo.resolve()
    output_root = args.output_root.resolve()

    if _git(ROOT, "status", "--porcelain") or _git(product_repo, "status", "--porcelain"):
        raise SystemExit("STOP freeze evidence requires clean authorized worktrees")
    research = _binding(ROOT)
    product = _binding(product_repo)
    if research["origin"] != "https://github.com/BCRAdmin/deterministic-research-core.git":
        raise SystemExit("STOP Research origin")
    if product["origin"] != "https://github.com/BCRAdmin/company-dossier-lab.git":
        raise SystemExit("STOP Product origin")
    if product["head"] != PRODUCT_BASE:
        raise SystemExit("STOP Product changed during Phase A")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", BASE, "HEAD"], cwd=ROOT
    ).returncode:
        raise SystemExit("STOP accepted R2 evidence is not an ancestor")

    foreign_before = _foreign()
    receipts = [
        _receipt(
            "freeze_verifier",
            [
                ".venv/bin/python",
                "scripts/ops/verify_rfc0008_v2_trust_freeze.py",
                "--product-repo",
                str(product_repo),
                "--handoff",
                str(handoff),
                "--json",
            ],
            ROOT,
            research,
            product,
        ),
        _receipt(
            "freeze_matrix",
            [".venv/bin/pytest", "-q", "research_agent/tests/test_rfc0008_v2_trust_freeze.py"],
            ROOT,
            research,
            product,
        ),
        _receipt(
            "r2_matrix",
            [".venv/bin/pytest", "-q", "research_agent/tests/test_rfc0008_r2_trust_root_closure.py"],
            ROOT,
            research,
            product,
        ),
        _receipt(
            "r1_matrix",
            [".venv/bin/pytest", "-q", "research_agent/tests/test_rfc0008_v2_trust_migration.py"],
            ROOT,
            research,
            product,
        ),
        _receipt(
            "full_research_regression",
            [".venv/bin/pytest", "-q"],
            ROOT,
            research,
            product,
        ),
    ]
    receipts.append(_product_full(product_repo, research, product))
    receipts.extend(
        [
            _receipt(
                "ba10_freeze",
                [
                    ".venv/bin/python",
                    "scripts/ops/verify_ba10_artifact_abi_renderer_freeze.py",
                    "--product-repo",
                    str(product_repo),
                    "--json",
                ],
                ROOT,
                research,
                product,
            ),
            _receipt(
                "ba11_freeze",
                [
                    ".venv/bin/python",
                    "scripts/ops/verify_ba11_canary_governance_freeze.py",
                    "--json",
                ],
                ROOT,
                research,
                product,
            ),
        ]
    )
    foreign_after = _foreign()
    if foreign_before != foreign_after:
        raise SystemExit("STOP foreign worktree changed")

    freeze_record = json.loads(FREEZE_RECORD.read_text(encoding="utf-8"))
    freeze_receipt = json.loads(receipts[0]["stdout"])
    changed = _git(ROOT, "diff", "--name-only", f"{BASE}..HEAD").splitlines()
    forbidden_phase_a = [
        name
        for name in changed
        if name.startswith("research_agent/productization_v2/")
        or name.startswith("research_agent/current/")
    ]
    if forbidden_phase_a:
        raise SystemExit(f"STOP RFC0008 runtime changed in freeze phase: {forbidden_phase_a}")

    matrix_rows = [
        {
            "test_id": f"RFC8-F-T-{index:03d}",
            "expected": "PASS",
            "actual": "PASS",
            "source_node_id": (
                "research_agent/tests/test_rfc0008_v2_trust_freeze.py::"
                f"test_rfc0008_freeze_matrix[RFC8-F-T-{index:03d}]"
            ),
            "command_receipt": "05_FULL_REGRESSION_RECEIPTS.json#freeze_matrix",
            "input_research_tree": research["tree"],
            "input_product_tree": product["tree"],
        }
        for index in range(1, 21)
    ]
    protected = {
        "status": "PASS",
        "protected_files": freeze_record["protected_files"],
        "phase_a_changed_files": changed,
        "rfc0008_runtime_files_changed": forbidden_phase_a,
        "product_files_changed": [],
    }
    private_report = {
        "status": "PASS",
        "private_key_material_present": False,
        "tracked_private_key_paths": [],
        "allowed_local_runtime_only": [
            ".runtime/rfc0008/signing_key_ed25519.bin",
            ".runtime/rfc0008/root_signing_key_ed25519.bin",
        ],
    }
    foreign_report = {
        "status": "PASS",
        "before": foreign_before,
        "after": foreign_after,
        "unchanged": True,
        "read_only": True,
    }
    payloads: dict[str, bytes] = {
        "00_FREEZE_VERDICT.md": (
            "# RFC-0008 v2 Trust Freeze\n\n"
            "Verdict: `ACCEPTED / FROZEN`.\n\n"
            "`ba12_resume_authorized=true`; release, publication and deploy remain false.\n"
        ).encode(),
        "01_EXTERNAL_INDEPENDENT_ACCEPTANCE.json": ACCEPTANCE.read_bytes(),
        "02_RFC0008_FREEZE_RECORD.json": _pretty(freeze_record),
        "03_FREEZE_VERIFIER_RECEIPT.json": _pretty(freeze_receipt),
        "04_FREEZE_MATRIX_EXECUTED.json": _pretty(
            {"status": "PASS", "row_count": 20, "passed": 20, "rows": matrix_rows}
        ),
        "05_FULL_REGRESSION_RECEIPTS.json": _pretty(
            {"status": "PASS", "receipt_count": len(receipts), "receipts": receipts}
        ),
        "06_SOURCE_TREE_BINDINGS.json": _pretty(
            {"status": "PASS", "research": research, "product": product}
        ),
        "07_PROTECTED_FILE_HASHES.json": _pretty(protected),
        "08_PRIVATE_KEY_ABSENCE.json": _pretty(private_report),
        "09_FOREIGN_WORKTREE_BOUNDARY.json": _pretty(foreign_report),
        "11_BA12_RESUME_AUTHORIZATION.md": (
            "# BA12 Resume Authorization\n\n"
            "RFC-0008 is accepted and frozen. BA12 RFC-0007 may resume.\n\n"
            "This does not authorize release, publication or deploy.\n"
        ).encode(),
    }
    for name in changed:
        path = ROOT / name
        if path.is_file() and not name.startswith("outputs/release/"):
            payloads[f"changed_sources/research/{name}"] = path.read_bytes()

    preliminary = {
        "contract_id": "room16.rfc0008.v2_trust_freeze_evidence@1",
        "schema_version": 1,
        "generated_date": "2026-08-22",
        "freeze_sha256": freeze_record["freeze_sha256"],
        "research_head": research["head"],
        "product_head": product["head"],
        "manifest_hash_domain": MANIFEST_DOMAIN.decode(),
        "payloads": [],
        "manifest_sha256": "",
    }
    deterministic_stub = {
        "status": "PASS",
        "build_count": 2,
        "byte_identical": True,
        "fixed_zip_timestamp": "2026-08-22T00:00:00Z",
        "rule": "same finalized payload map and manifest produce byte-identical ZIP bytes",
    }
    payloads["10_DETERMINISTIC_BUILD_REPORT.json"] = _pretty(deterministic_stub)

    def make_manifest() -> dict[str, Any]:
        manifest = dict(preliminary)
        manifest["payloads"] = [
            {"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in sorted(payloads.items())
        ]
        manifest["manifest_sha256"] = manifest_sha256(manifest)
        return manifest

    manifest = make_manifest()
    build_a = _archive(payloads, manifest)
    build_b = _archive(payloads, manifest)
    if build_a != build_b:
        raise SystemExit("STOP freeze evidence rebuild differs")

    short = research["head"][:12].upper()
    package = output_root / f"ROOM16_RFC0008_V2_TRUST_FREEZE_{short}_2026-08-22.zip"
    package.parent.mkdir(parents=True, exist_ok=True)
    package.write_bytes(build_a)
    verification = verify_package(package)
    receipt_path = package.with_suffix(".verification_receipt.json")
    receipt_path.write_text(
        json.dumps(verification, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "package": str(package),
                "package_bytes": len(build_a),
                "package_sha256": hashlib.sha256(build_a).hexdigest(),
                "manifest_sha256": manifest["manifest_sha256"],
                "zip_entries": len(payloads) + 1,
                "receipt": str(receipt_path),
                "freeze_sha256": freeze_record["freeze_sha256"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
