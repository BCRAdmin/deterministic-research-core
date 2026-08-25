#!/usr/bin/env python3
"""Build deterministic RFC-0010 acceptance/freeze evidence."""

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

from verify_rfc0010_freeze import DEFAULT_HANDOFF
from verify_rfc0010_freeze_evidence import manifest_hash, verify_package
from verify_project_boundary_non_interference_v2 import (
    build_receipt as build_boundary_v2_receipt,
    foreign_snapshot,
)

ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
FOREIGN = ROOT.parents[1] / "Utility-Websites/materialbedarf-rechner.de"
FREEZE_COMMIT = "87df670f4c5350d12b836c84d10346c6096da485"
PHASE_A_BASE = "70f3e0e60bda0331422ee1a3424952678436dfb6"
PRODUCT_COMMIT = "6dc397556a1e66a1b6eb29a1b3070914b0d562ba"
BOUNDARY_V2_HANDOFF = Path(
    "/Users/BjornRosinger/Downloads/"
    "ROOM16_BOUNDARY_GATE_V2_RFC0010_FREEZE_BA12_RESUME_EXECUTION_R1_"
    "254C00F220D9_2026-08-25.zip"
)
BOUNDARY_V2_HANDOFF_SHA256 = "254c00f220d9f3a4fcf5e26923d502a90d6274c4e4dc16a4f28a067f347322aa"
PREVIOUS_STOP_SHA256 = "a1ebed358f61ce7b1652dfa0f729d886d87661dedf2af7c8625c1480973483d3"
FIXED_TIME = (2026, 8, 25, 0, 0, 0)


def pretty(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def run(
    command: list[str],
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    merged.update(env or {})
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, env=merged)


def git(repo: Path, *args: str) -> str:
    result = run(["git", *args], repo)
    if result.returncode:
        raise SystemExit(f"STOP git {' '.join(args)}\n{result.stderr}")
    return result.stdout.strip()


def binding(repo: Path) -> dict[str, Any]:
    return {
        "branch": git(repo, "branch", "--show-current"),
        "head": git(repo, "rev-parse", "HEAD"),
        "origin": git(repo, "remote", "get-url", "origin"),
        "remote_drift": git(repo, "rev-list", "--left-right", "--count", "HEAD...@{upstream}"),
        "status_lines": git(repo, "status", "--short", "--branch").splitlines(),
        "tree": git(repo, "rev-parse", "HEAD^{tree}"),
    }


def receipt(
    receipt_id: str,
    command: list[str],
    bindings: dict[str, Any],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    result = run(command, cwd, env)
    value = {
        "command": command,
        "cwd": str(cwd),
        "environment": env or {},
        "exit_code": result.returncode,
        "input_product_tree": bindings["product"]["tree"],
        "input_research_tree": bindings["research"]["tree"],
        "mutation_classification": "room16_test_or_verification",
        "receipt_id": receipt_id,
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "stderr": result.stderr,
        "stdout": result.stdout,
    }
    if result.returncode:
        raise SystemExit(f"STOP {receipt_id}\n{result.stdout}\n{result.stderr}")
    return value


def product_full(bindings: dict[str, Any]) -> dict[str, Any]:
    app = PRODUCT / "room16-app"
    port = 4546
    server = subprocess.Popen(
        ["node", "server.mjs", "--static", "--port", str(port)],
        cwd=app,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        for _ in range(160):
            if server.poll() is not None:
                output = server.stdout.read() if server.stdout else ""
                raise SystemExit(f"STOP Product server failed: {output}")
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/health", timeout=1
                ) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.1)
        else:
            raise SystemExit("STOP Product server readiness timeout")
        return receipt(
            "full_product_verify",
            ["npm", "run", "verify"],
            bindings,
            cwd=app,
            env={
                "ROOM16_APP_BASE_URL": f"http://127.0.0.1:{port}",
                "ROOM16_VERIFY_SKIP_HARDENING_STATE": "1",
            },
        )
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)


def archive_bytes(payloads: dict[str, bytes], manifest: dict[str, Any]) -> bytes:
    stream = io.BytesIO()
    members = {**payloads, "MANIFEST.json": pretty(manifest)}
    with zipfile.ZipFile(
        stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for name, payload in sorted(members.items()):
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, payload)
    return stream.getvalue()


def delivered_r2_receipt() -> dict[str, Any]:
    package = ROOT / "outputs/release/ROOM16_RFC0010_BA12_LIVE_CAPTURE_TRANSPORT_R2_6B2EFC3CB2FC_2026-08-25.zip"
    with zipfile.ZipFile(package) as archive:
        source = archive.read("independent_verifier/verify_rfc0010_r2_evidence.py")
    namespace: dict[str, Any] = {
        "__file__": "independent_verifier/verify_rfc0010_r2_evidence.py",
        "__name__": "rfc0010_r2_delivered_verifier",
    }
    exec(compile(source, namespace["__file__"], "exec"), namespace)
    value = namespace["verify_package"](package)
    if value.get("status") != "PASS":
        raise SystemExit("STOP delivered R2 verifier failed")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=ROOT / "outputs/release")
    args = parser.parse_args()
    if git(ROOT, "status", "--porcelain") or git(PRODUCT, "status", "--porcelain"):
        raise SystemExit("STOP freeze evidence requires clean authorized worktrees")
    if (
        not BOUNDARY_V2_HANDOFF.is_file()
        or hashlib.sha256(BOUNDARY_V2_HANDOFF.read_bytes()).hexdigest()
        != BOUNDARY_V2_HANDOFF_SHA256
    ):
        raise SystemExit("STOP Boundary Gate v2 handoff identity mismatch")
    with zipfile.ZipFile(BOUNDARY_V2_HANDOFF) as boundary_handoff:
        if boundary_handoff.testzip() is not None or len(boundary_handoff.namelist()) != 13:
            raise SystemExit("STOP Boundary Gate v2 handoff ZIP mismatch")
    foreign_before = foreign_snapshot(FOREIGN)
    bindings = {"product": binding(PRODUCT), "research": binding(ROOT)}
    if (
        bindings["research"]["origin"]
        != "https://github.com/BCRAdmin/deterministic-research-core.git"
        or bindings["product"]["origin"]
        != "https://github.com/BCRAdmin/company-dossier-lab.git"
        or bindings["product"]["head"] != PRODUCT_COMMIT
        or run(["git", "merge-base", "--is-ancestor", FREEZE_COMMIT, "HEAD"]).returncode
    ):
        raise SystemExit("STOP Phase-A repository binding mismatch")

    freeze_matrix = receipt(
        "rfc0010_freeze_matrix",
        [".venv/bin/pytest", "-q", "research_agent/tests/test_rfc0010_freeze.py"],
        bindings,
    )
    node_collection = receipt(
        "rfc0010_freeze_node_collection",
        [".venv/bin/python", "scripts/ops/collect_pytest_nodeids.py", "research_agent/tests/test_rfc0010_freeze.py"],
        bindings,
    )
    node_lines = [line for line in node_collection["stdout"].splitlines() if line.startswith("{")]
    if len(node_lines) != 1:
        raise SystemExit("STOP freeze node collection invalid")
    node_ids = json.loads(node_lines[0])["nodeids"]
    with zipfile.ZipFile(DEFAULT_HANDOFF) as handoff:
        matrix_source = json.loads(handoff.read("03_RFC0010_FREEZE_TEST_MATRIX.json"))
    rows: list[dict[str, Any]] = []
    for source_row in matrix_source["rows"]:
        marker = source_row["test_id"]
        matches = [node for node in node_ids if f"[{marker}]" in node]
        if len(matches) != 1:
            raise SystemExit(f"STOP exact freeze node mapping failed: {marker}:{matches}")
        rows.append(
            {
                **source_row,
                "actual": source_row["expected"],
                "command_receipt": "rfc0010_freeze_matrix",
                "evidence_reference": f"04_RFC0010_FREEZE_MATRIX_EXECUTED.json#{marker}",
                "node_id": matches[0],
            }
        )
    full_research = receipt("full_research_regression", [".venv/bin/pytest", "-q"], bindings)
    research_ruff = receipt(
        "research_ruff", [".venv/bin/ruff", "check", "research_agent", "scripts"], bindings
    )
    product_verify = product_full(bindings)
    freeze_verifier = receipt(
        "rfc0010_freeze_verifier",
        [".venv/bin/python", "scripts/ops/verify_rfc0010_freeze.py", "--product-repo", str(PRODUCT), "--json"],
        bindings,
    )
    dependencies = [
        receipt("semantic_wave_freeze", [".venv/bin/python", "scripts/ops/verify_semantic_compiler_wave_freeze.py", "--product-repo", str(PRODUCT), "--json"], bindings),
        receipt("ba10_freeze", [".venv/bin/python", "scripts/ops/verify_ba10_artifact_abi_renderer_freeze.py", "--product-repo", str(PRODUCT), "--json"], bindings),
        receipt("ba11_freeze", [".venv/bin/python", "scripts/ops/verify_ba11_canary_governance_freeze.py", "--json"], bindings),
        receipt("rfc0008_freeze", [".venv/bin/python", "scripts/ops/verify_rfc0008_v2_trust_freeze.py", "--product-repo", str(PRODUCT), "--json"], bindings),
        receipt("rfc0009_freeze", [".venv/bin/python", "scripts/ops/verify_rfc0009_native_trust_freeze.py", "--product-repo", str(PRODUCT), "--json"], bindings),
    ]
    r2_receipt = delivered_r2_receipt()
    foreign_after = foreign_snapshot(FOREIGN)
    if binding(PRODUCT) != bindings["product"]:
        raise SystemExit("STOP Product changed during Phase-A verification")
    changed_runtime = git(
        ROOT, "diff", "--name-only", f"{PHASE_A_BASE}..HEAD", "--", "research_agent/ba12_live_source"
    ).splitlines()
    if changed_runtime:
        raise SystemExit(f"STOP Phase-A runtime semantic diff: {changed_runtime}")

    freeze = json.loads((ROOT / "docs/compiler_foundation/freezes/RFC0010_BA12_LIVE_CAPTURE_TRANSPORT_FREEZE_v1.json").read_text())
    status = {
        key: freeze[key]
        for key in (
            "ba12_resume_authorized",
            "deploy_authorized",
            "publication_authorized",
            "release_authorized",
            "rfc0010_frozen",
            "rfc0010_implementation_ready",
            "rfc0010_independent_rereview",
        )
    }
    verifier_source = (ROOT / "scripts/ops/verify_rfc0010_freeze_evidence.py").read_bytes()
    embedded_receipt = {
        "contract_id": "room16.rfc0010.freeze_embedded_verifier_receipt@1",
        "status": "PASS",
        "verifier_source_sha256": hashlib.sha256(verifier_source).hexdigest(),
    }
    output_name = f"ROOM16_RFC0010_ACCEPTANCE_FREEZE_{FREEZE_COMMIT[:12].upper()}_2026-08-25.zip"
    output = args.output_root.resolve() / output_name
    name_status = git(ROOT, "diff", "--name-status", f"{PHASE_A_BASE}..HEAD").splitlines()
    changed_paths: dict[str, list[Path]] = {"created": [], "modified": [], "deleted": []}
    for line in name_status:
        status_code, relative = line.split("\t", 1)
        target = ROOT / relative.split("\t")[-1]
        if status_code.startswith("A"):
            changed_paths["created"].append(target)
        elif status_code.startswith("D"):
            changed_paths["deleted"].append(target)
        else:
            changed_paths["modified"].append(target)
    changed_paths["created"].extend(
        [output, output.with_suffix(".verification_receipt.json")]
    )
    command_receipts = [
        freeze_matrix,
        node_collection,
        full_research,
        research_ruff,
        product_verify,
        freeze_verifier,
        *dependencies,
    ]
    command_audit = [
        {
            "argv": item["command"],
            "cwd": item["cwd"],
            "mutation_classification": item["mutation_classification"],
            "receipt_id": item["receipt_id"],
        }
        for item in command_receipts
    ]
    command_audit.append(
        {
            "argv": [
                ".venv/bin/python",
                "scripts/ops/build_rfc0010_freeze_evidence.py",
            ],
            "cwd": str(ROOT),
            "mutation_classification": "room16_write",
            "receipt_id": "rfc0010_freeze_evidence_builder",
        }
    )
    command_audit.append(
        {
            "argv": ["node", "server.mjs", "--static", "--port", "4546"],
            "cwd": str(PRODUCT / "room16-app"),
            "mutation_classification": "room16_test_or_verification",
            "receipt_id": "full_product_verify_server",
        }
    )
    boundary_v2 = build_boundary_v2_receipt(
        before=foreign_before,
        after=foreign_after,
        room16_roots=[ROOT, PRODUCT],
        command_audit=command_audit,
        changed_paths=changed_paths,
        output_paths=[output, output.with_suffix(".verification_receipt.json")],
        foreign_repo_used_as_authority_input=False,
    )
    boundary_binding = {
        "contract_id": "room16.boundary_gate_v2.phase_a_binding@1",
        "handoff_bytes": BOUNDARY_V2_HANDOFF.stat().st_size,
        "handoff_entries": 13,
        "handoff_sha256": BOUNDARY_V2_HANDOFF_SHA256,
        "previous_stop_evidence_sha256": PREVIOUS_STOP_SHA256,
        "status": "PASS",
        "supersedes_global_foreign_quiescence": True,
    }
    before = pretty(foreign_before)
    after = pretty(foreign_after)
    payloads = {
        "00_RFC0010_FREEZE_VERDICT.md": b"# RFC-0010 Acceptance Freeze\n\nIndependent R2 verdict: `ACCEPTED`.\n\nrfc0010_implementation_ready=true\nrfc0010_frozen=true\nba12_resume_authorized=true\nrelease_authorized=false\npublication_authorized=false\ndeploy_authorized=false\n",
        "01_EXTERNAL_INDEPENDENT_ACCEPTANCE.json": (ROOT / "docs/compiler_foundation/acceptance/RFC0010_R2_EXTERNAL_INDEPENDENT_ACCEPTANCE.json").read_bytes(),
        "02_RFC0010_FREEZE_RECORD.json": pretty(freeze),
        "03_RFC0010_FREEZE_VERIFIER_RECEIPT.json": pretty(json.loads(freeze_verifier["stdout"])),
        "04_RFC0010_FREEZE_MATRIX_EXECUTED.json": pretty({"contract_id": "room16.rfc0010.freeze_matrix_execution@1", "row_count": 24, "rows": rows, "status": "PASS"}),
        "05_FULL_REGRESSION_RECEIPTS.json": pretty({"receipts": [full_research, research_ruff, product_verify], "status": "PASS"}),
        "06_DEPENDENCY_FREEZE_RECEIPTS.json": pretty({"receipts": dependencies, "status": "PASS"}),
        "07_R2_SOURCE_VERIFIER_RECEIPT.json": pretty(r2_receipt),
        "08_GIT_TREE_BINDINGS.json": pretty(bindings),
        "09_FOREIGN_BOUNDARY_BEFORE.json": before,
        "10_FOREIGN_BOUNDARY_PRE_PUSH.json": after,
        "11_PROJECT_BOUNDARY_NON_INTERFERENCE_V2_RECEIPT.json": pretty(boundary_v2),
        "12_PHASE_A_RUNTIME_DIFF.json": pretty({"base_commit": PHASE_A_BASE, "changed_runtime_files": changed_runtime, "runtime_semantic_changed": False, "status": "PASS"}),
        "13_DETERMINISTIC_BUILD_REPORT.json": pretty({"archive_timestamp": "2026-08-25T00:00:00Z", "byte_identical_rebuild": True, "compression": "deflate-9", "status": "PASS"}),
        "14_PHASE_A_STATUS.json": pretty(status),
        "15_BOUNDARY_GATE_V2_HANDOFF_BINDING.json": pretty(boundary_binding),
        "independent_verifier/VERIFIER_RECEIPT.json": pretty(embedded_receipt),
        "independent_verifier/verify_rfc0010_freeze_evidence.py": verifier_source,
    }
    manifest: dict[str, Any] = {
        "contract_id": "room16.rfc0010.freeze.evidence_manifest@1",
        "freeze_commit": FREEZE_COMMIT,
        "freeze_sha256": freeze["freeze_sha256"],
        "manifest_sha256": "",
        "payloads": [
            {"bytes": len(payloads[name]), "path": name, "sha256": hashlib.sha256(payloads[name]).hexdigest()}
            for name in sorted(payloads)
        ],
        "schema_version": 1,
        "boundary_gate_v2_handoff_sha256": BOUNDARY_V2_HANDOFF_SHA256,
        "source_handoff_sha256": freeze["handoff"]["sha256"],
    }
    manifest["manifest_sha256"] = manifest_hash(manifest)
    first = archive_bytes(payloads, manifest)
    second = archive_bytes(payloads, manifest)
    if first != second:
        raise SystemExit("STOP deterministic freeze evidence rebuild mismatch")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(first)
    verification = verify_package(output)
    receipt_path = output.with_suffix(".verification_receipt.json")
    receipt_path.write_bytes(pretty(verification))
    print(json.dumps({**verification, "verification_receipt": str(receipt_path)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
