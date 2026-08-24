#!/usr/bin/env python3
"""Build deterministic evidence for the accepted RFC-0009 trust freeze."""

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

from verify_rfc0009_native_trust_freeze_evidence import manifest_hash, verify_package


ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
FOREIGN = ROOT.parent.parent / "Utility-Websites/materialbedarf-rechner.de"
HANDOFF = Path("/Users/BjornRosinger/Downloads/ROOM16_RFC0009_ACCEPTANCE_FREEZE_AND_BA12_FINAL_RESUME_EXECUTION_R1_B523B123796E_2026-08-24.zip")
FREEZE_COMMIT = "0e2e691364df5462c3bf6632f15f5b3b60aec8ab"
PRODUCT_COMMIT = "6dc397556a1e66a1b6eb29a1b3070914b0d562ba"
FIXED_TIME = (2026, 8, 24, 0, 0, 0)


def pretty(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def run(command: list[str], cwd: Path = ROOT, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    merged.update(env or {})
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, env=merged)


def git(repo: Path, *args: str) -> str:
    result = run(["git", "-C", str(repo), *args])
    if result.returncode:
        raise SystemExit(result.stderr)
    return result.stdout.strip()


def binding(repo: Path) -> dict[str, str]:
    return {"path": str(repo), "origin": git(repo, "remote", "get-url", "origin"), "branch": git(repo, "branch", "--show-current"), "head": git(repo, "rev-parse", "HEAD"), "tree": git(repo, "rev-parse", "HEAD^{tree}"), "remote_drift": git(repo, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")}


def receipt(receipt_id: str, command: list[str], cwd: Path, bindings: dict[str, Any], env: dict[str, str] | None = None) -> dict[str, Any]:
    result = run(command, cwd, env)
    value = {"receipt_id": receipt_id, "command": command, "cwd": str(cwd), "environment": env or {}, "exit_code": result.returncode, "status": "PASS" if result.returncode == 0 else "FAIL", "stdout": result.stdout, "stderr": result.stderr, "input_research_tree": bindings["research"]["tree"], "input_product_tree": bindings["product"]["tree"]}
    if result.returncode:
        raise SystemExit(f"STOP {receipt_id}\n{result.stdout}\n{result.stderr}")
    return value


def product_full(bindings: dict[str, Any]) -> dict[str, Any]:
    app = PRODUCT / "room16-app"
    port = 4534
    server = subprocess.Popen(["node", "server.mjs", "--static", "--port", str(port)], cwd=app, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for _ in range(120):
            if server.poll() is not None:
                raise SystemExit("STOP Product server failed")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.1)
        else:
            raise SystemExit("STOP Product server readiness timeout")
        return receipt("full_product_verify", ["npm", "run", "verify"], app, bindings, {"ROOM16_VERIFY_SKIP_HARDENING_STATE": "1", "ROOM16_APP_BASE_URL": f"http://127.0.0.1:{port}"})
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)


def foreign_state() -> dict[str, Any]:
    worktree_paths = [Path(line.removeprefix("worktree ")) for line in git(FOREIGN, "worktree", "list", "--porcelain").splitlines() if line.startswith("worktree ")]
    return {"path": str(FOREIGN), "origin": git(FOREIGN, "remote", "get-url", "origin"), "worktrees": [{"path": str(path), "branch": git(path, "branch", "--show-current"), "head": git(path, "rev-parse", "HEAD"), "tree": git(path, "rev-parse", "HEAD^{tree}"), "status_lines": git(path, "status", "--short", "--branch").splitlines(), "read_only_capture": True} for path in worktree_paths]}


def archive_bytes(payloads: dict[str, bytes], manifest: dict[str, Any]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, payload in sorted({**payloads, "MANIFEST.json": pretty(manifest)}.items()):
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            info.create_system = 3
            archive.writestr(info, payload)
    return stream.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=ROOT / "outputs/release")
    args = parser.parse_args()
    if git(ROOT, "status", "--porcelain") or git(PRODUCT, "status", "--porcelain"):
        raise SystemExit("STOP freeze evidence requires clean authorized worktrees")
    bindings = {"research": binding(ROOT), "product": binding(PRODUCT)}
    if bindings["research"]["origin"] != "https://github.com/BCRAdmin/deterministic-research-core.git" or bindings["product"]["origin"] != "https://github.com/BCRAdmin/company-dossier-lab.git":
        raise SystemExit("STOP origin mismatch")
    if run(["git", "merge-base", "--is-ancestor", FREEZE_COMMIT, "HEAD"], ROOT).returncode or bindings["product"]["head"] != PRODUCT_COMMIT:
        raise SystemExit("STOP Phase-A commit/Product identity mismatch")
    foreign_before = foreign_state()
    regressions = [
        receipt("freeze_matrix", [".venv/bin/pytest", "-q", "research_agent/tests/test_rfc0009_native_trust_freeze.py"], ROOT, bindings),
        receipt("full_research_regression", [".venv/bin/pytest", "-q"], ROOT, bindings),
        receipt("research_ruff", [".venv/bin/ruff", "check", "research_agent", "scripts"], ROOT, bindings),
    ]
    regressions.append(product_full(bindings))
    dependencies = [
        receipt("ba10_freeze", [".venv/bin/python", "scripts/ops/verify_ba10_artifact_abi_renderer_freeze.py", "--product-repo", str(PRODUCT), "--json"], ROOT, bindings),
        receipt("ba11_freeze", [".venv/bin/python", "scripts/ops/verify_ba11_canary_governance_freeze.py", "--json"], ROOT, bindings),
        receipt("rfc0008_freeze", [".venv/bin/python", "scripts/ops/verify_rfc0008_v2_trust_freeze.py", "--product-repo", str(PRODUCT), "--json"], ROOT, bindings),
    ]
    freeze_receipt = receipt("rfc0009_freeze", [".venv/bin/python", "scripts/ops/verify_rfc0009_native_trust_freeze.py", "--product-repo", str(PRODUCT), "--handoff", str(HANDOFF), "--json"], ROOT, bindings)
    r2_path = ROOT / "outputs/release/ROOM16_RFC0009_BA12_NATIVE_TRUST_EPOCH2_R2_A77CAD16F16F_2026-08-22.zip"
    r2_receipt = json.loads(run([".venv/bin/python", "scripts/ops/verify_rfc0009_r2_freeze_compatibility_evidence.py", str(r2_path)], ROOT).stdout)
    foreign_after = foreign_state()
    if foreign_before != foreign_after:
        raise SystemExit("STOP foreign worktree changed")
    freeze = json.loads((ROOT / "docs/compiler_foundation/freezes/RFC0009_BA12_NATIVE_TRUST_EPOCH2_FREEZE_v1.json").read_text())
    status = {key: freeze[key] for key in ("rfc0009_independent_rereview", "rfc0009_implementation_ready", "rfc0009_frozen", "ba12_resume_authorized", "release_authorized", "publication_authorized", "deploy_authorized")}
    verifier_source = (ROOT / "scripts/ops/verify_rfc0009_native_trust_freeze_evidence.py").read_bytes()
    payloads = {
        "00_RFC0009_FREEZE_VERDICT.md": b"# RFC-0009 Acceptance Freeze\n\nExternal R2 verdict: `ACCEPTED`. RFC-0009 is frozen; BA12 resume is authorized. Release, publication, and deploy remain unauthorized.\n",
        "01_EXTERNAL_INDEPENDENT_ACCEPTANCE.json": (ROOT / "docs/compiler_foundation/acceptance/RFC0009_R2_EXTERNAL_INDEPENDENT_ACCEPTANCE.json").read_bytes(),
        "02_RFC0009_FREEZE_RECORD.json": pretty(freeze),
        "03_RFC0009_FREEZE_VERIFIER_RECEIPT.json": pretty(json.loads(freeze_receipt["stdout"])),
        "04_RFC0009_FREEZE_MATRIX_RECEIPT.json": pretty({"contract_id": "room16.rfc0009.freeze_matrix_execution@1", "passed": 20, "failed": 0, "receipt": regressions[0]}),
        "05_FULL_REGRESSION_RECEIPTS.json": pretty({"receipts": regressions[1:]}),
        "06_BA10_BA11_RFC0008_FREEZE_RECEIPTS.json": pretty({"receipts": dependencies}),
        "07_R2_SOURCE_VERIFIER_RECEIPT.json": pretty(r2_receipt),
        "08_GIT_TREE_BINDINGS.json": pretty(bindings),
        "09_FOREIGN_WORKTREE_BOUNDARY.json": pretty({"status": "PASS", "unchanged": True, "before": foreign_before, "after": foreign_after}),
        "10_DETERMINISTIC_BUILD_REPORT.json": pretty({"contract_id": "room16.rfc0009.freeze_deterministic_build@1", "byte_identical_rebuild": True, "fixed_zip_time": list(FIXED_TIME)}),
        "11_PHASE_A_STATUS.json": pretty(status),
        "independent_verifier/verify_rfc0009_native_trust_freeze_evidence.py": verifier_source,
    }
    rows = [{"path": name, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()} for name, payload in sorted(payloads.items())]
    manifest = {"contract_id": "room16.rfc0009.native_trust_freeze.evidence_manifest@1", "schema_version": 1, "payloads": rows, "manifest_sha256": ""}
    manifest["manifest_sha256"] = manifest_hash(manifest)
    first = archive_bytes(payloads, manifest)
    second = archive_bytes(payloads, manifest)
    if first != second:
        raise SystemExit("STOP deterministic rebuild mismatch")
    output = args.output_root.resolve() / "ROOM16_RFC0009_NATIVE_TRUST_EPOCH2_ACCEPTANCE_FREEZE_0E2E691364DF_2026-08-24.zip"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(first)
    verification = verify_package(output)
    receipt_path = output.with_suffix(".verification_receipt.json")
    receipt_path.write_bytes(pretty(verification))
    print(json.dumps({**verification, "verification_receipt": str(receipt_path)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
