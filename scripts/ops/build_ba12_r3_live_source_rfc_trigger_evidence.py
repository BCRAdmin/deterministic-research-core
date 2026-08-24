#!/usr/bin/env python3
"""Build deterministic BA12 R3 live-source RFC-trigger evidence."""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path
from typing import Any

from verify_ba12_r3_live_source_rfc_trigger_evidence import manifest_hash, verify_package


ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
FOREIGN = ROOT.parents[1] / "Utility-Websites/materialbedarf-rechner.de"
HANDOFF = Path("/Users/BjornRosinger/Downloads/ROOM16_RFC0009_ACCEPTANCE_FREEZE_AND_BA12_FINAL_RESUME_EXECUTION_R1_B523B123796E_2026-08-24.zip")
PHASE_A = ROOT / "outputs/release/ROOM16_RFC0009_NATIVE_TRUST_EPOCH2_ACCEPTANCE_FREEZE_0E2E691364DF_2026-08-24.zip"
HANDOFF_SHA256 = "b523b123796e20c7bdaf52bb175be254376e35c5d17fa171651d18bda5163ebf"
PRODUCT_HEAD = "6dc397556a1e66a1b6eb29a1b3070914b0d562ba"
WAVE0_BASE = "6378226cb718650ae3858c8f01ce2e0432847dec"
STOP_COMMIT = "9b1fd85f2279a5aadab0105b6d5f59d634b143c7"
FIXED_TIME = (2026, 8, 24, 0, 0, 0)


def pretty(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True)


def git(repo: Path, *args: str) -> str:
    result = run(["git", *args], repo)
    if result.returncode:
        raise SystemExit(result.stderr)
    return result.stdout.strip()


def json_receipt(receipt_id: str, command: list[str]) -> dict[str, Any]:
    result = run(command)
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"STOP {receipt_id} invalid JSON: {result.stdout}: {result.stderr}") from exc
    if result.returncode or parsed.get("status") != "PASS":
        raise SystemExit(f"STOP {receipt_id}: {result.stdout}: {result.stderr}")
    return {"receipt_id": receipt_id, "status": "PASS", "command": command, "result": parsed, "stdout_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(), "stderr": result.stderr}


def foreign_state() -> dict[str, Any]:
    paths = [Path(line.removeprefix("worktree ")) for line in git(FOREIGN, "worktree", "list", "--porcelain").splitlines() if line.startswith("worktree ")]
    return {"path": str(FOREIGN), "origin": git(FOREIGN, "remote", "get-url", "origin"), "worktrees": [{"path": str(path), "branch": git(path, "branch", "--show-current"), "head": git(path, "rev-parse", "HEAD"), "tree": git(path, "rev-parse", "HEAD^{tree}"), "status_lines": git(path, "status", "--short", "--branch").splitlines(), "read_only": True} for path in paths]}


def archive(payloads: dict[str, bytes], manifest: dict[str, Any]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as target:
        for name, payload in sorted({**payloads, "MANIFEST.json": pretty(manifest)}.items()):
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            info.create_system = 3
            target.writestr(info, payload)
    return stream.getvalue()


def main() -> int:
    if git(ROOT, "status", "--porcelain") or git(PRODUCT, "status", "--porcelain"):
        raise SystemExit("STOP evidence build requires clean authorized worktrees")
    if sha(HANDOFF) != HANDOFF_SHA256 or git(PRODUCT, "rev-parse", "HEAD") != PRODUCT_HEAD:
        raise SystemExit("STOP handoff/Product identity mismatch")
    if run(["git", "merge-base", "--is-ancestor", STOP_COMMIT, "HEAD"]).returncode:
        raise SystemExit("STOP conflict evidence commit is not an ancestor")
    before = foreign_state()
    conflict = json_receipt("ba12_r3_conflict", [".venv/bin/python", "scripts/ops/verify_ba12_r3_live_source_contract_conflict.py", "--json"])
    semantic = json_receipt("semantic_wave_freeze", [".venv/bin/python", "scripts/ops/verify_semantic_compiler_wave_freeze.py", "--product-repo", str(PRODUCT), "--json"])
    rfc9 = json_receipt("rfc0009_freeze", [".venv/bin/python", "scripts/ops/verify_rfc0009_native_trust_freeze.py", "--product-repo", str(PRODUCT), "--json"])
    dependencies = [
        json_receipt("ba10_freeze", [".venv/bin/python", "scripts/ops/verify_ba10_artifact_abi_renderer_freeze.py", "--product-repo", str(PRODUCT), "--json"]),
        json_receipt("ba11_freeze", [".venv/bin/python", "scripts/ops/verify_ba11_canary_governance_freeze.py", "--json"]),
        json_receipt("rfc0008_freeze", [".venv/bin/python", "scripts/ops/verify_rfc0008_v2_trust_freeze.py", "--product-repo", str(PRODUCT), "--json"]),
    ]
    phase_a = json.loads(run([".venv/bin/python", "scripts/ops/verify_rfc0009_native_trust_freeze_evidence.py", str(PHASE_A)]).stdout)
    targeted_run = run([".venv/bin/pytest", "-q", "research_agent/tests/test_ba12_r3_live_source_contract_conflict.py"])
    if targeted_run.returncode:
        raise SystemExit(f"STOP targeted conflict tests: {targeted_run.stdout}: {targeted_run.stderr}")
    targeted = {"status": "PASS", "command": [".venv/bin/pytest", "-q", "research_agent/tests/test_ba12_r3_live_source_contract_conflict.py"], "stdout": targeted_run.stdout, "stderr": targeted_run.stderr}
    after = foreign_state()
    if before != after:
        raise SystemExit("STOP foreign worktree changed")
    bindings = {"research": {"path": str(ROOT), "origin": git(ROOT, "remote", "get-url", "origin"), "branch": git(ROOT, "branch", "--show-current"), "head": git(ROOT, "rev-parse", "HEAD"), "tree": git(ROOT, "rev-parse", "HEAD^{tree}"), "drift": git(ROOT, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")}, "product": {"path": str(PRODUCT), "origin": git(PRODUCT, "remote", "get-url", "origin"), "branch": git(PRODUCT, "branch", "--show-current"), "head": git(PRODUCT, "rev-parse", "HEAD"), "tree": git(PRODUCT, "rev-parse", "HEAD^{tree}"), "drift": git(PRODUCT, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")}}
    changed_names = git(ROOT, "diff", "--name-only", f"{WAVE0_BASE}..HEAD").splitlines()
    allowed_prefixes = ("docs/compiler_foundation/rfcs/", "research_agent/tests/", "scripts/ops/")
    changed = {"base": WAVE0_BASE, "head": bindings["research"]["head"], "files": changed_names, "runtime_code_changed": any(not name.startswith(allowed_prefixes) for name in changed_names), "product_changed": bindings["product"]["head"] != PRODUCT_HEAD, "frozen_file_changed": any(name.startswith("research_agent/semantic_compiler/") or name.startswith("research_agent/productization") for name in changed_names)}
    if changed["runtime_code_changed"] or changed["product_changed"] or changed["frozen_file_changed"]:
        raise SystemExit("STOP change scope mismatch")
    final_state = {"diagnostic_code": "FROZEN_BA3_LIVE_RECEIPT_TRANSPORT_UNREPRESENTABLE", "ready_for_independent_rereview": False, "ba12_implementation_ready": False, "ba12_frozen": False, "release_ready_candidate": False, "release_ready": False, "release_authorized": False, "publication_authorized": False, "deploy_authorized": False}
    verdict = b"# BA12 R3 RFC-Trigger Verdict\n\nBA12 stopped before runtime edits because frozen `RetrievalReceiptIR@1` cannot truthfully represent `live_acquisition`. Original Stop Conditions 2 and 4 fired. RFC-0009 remains frozen and Product remains unchanged.\n"
    decision = b"# Independent RFC Decision Required\n\nApprove and independently freeze a versioned additive live-retrieval receipt transport contract or BA3 successor. It must preserve the accepted meanings of `offline_replay` and `offline_fixture`, add a truthful `live_acquisition` transport, define compatibility and replay rules, update the semantic-wave schema/version lock, and require WM/COST/ABT plus live-capture replay evidence. It does not authorize release, publication, deploy, merge, or history rewrite.\n"
    payloads = {
        "00_RFC_TRIGGER_VERDICT.md": verdict,
        "01_BA12_LIVE_SOURCE_CONFLICT.json": (ROOT / "docs/compiler_foundation/rfcs/BA12_R3_LIVE_SOURCE_CONTRACT_CONFLICT_STOP.json").read_bytes(),
        "02_LEGACY_PATH_INVENTORY.json": (ROOT / "docs/compiler_foundation/rfcs/ba12_legacy_path_inventory.json").read_bytes(),
        "03_RFC_0007_STATUS.md": (ROOT / "docs/compiler_foundation/rfcs/RFC-0007_BA12_FINAL_STRANGLER_CUTOVER.md").read_bytes(),
        "04_CONFLICT_VERIFIER_RECEIPT.json": pretty(conflict["result"]),
        "05_SEMANTIC_WAVE_FREEZE_RECEIPT.json": pretty(semantic["result"]),
        "06_RFC0009_FREEZE_RECEIPT.json": pretty(rfc9["result"]),
        "07_BA10_BA11_RFC0008_FREEZE_RECEIPTS.json": pretty({"receipts": dependencies}),
        "08_PHASE_A_EVIDENCE_RECEIPT.json": pretty(phase_a),
        "09_TARGETED_TEST_RECEIPT.json": pretty(targeted),
        "10_GIT_TREE_BINDINGS.json": pretty(bindings),
        "11_CHANGED_FILES_REPORT.json": pretty(changed),
        "12_FOREIGN_WORKTREE_BOUNDARY.json": pretty({"status": "PASS", "unchanged": True, "before": before, "after": after}),
        "13_HANDOFF_IDENTITY.json": pretty({"filename": HANDOFF.name, "bytes": HANDOFF.stat().st_size, "sha256": sha(HANDOFF), "zip_entries": len(zipfile.ZipFile(HANDOFF).namelist())}),
        "14_INDEPENDENT_RFC_DECISION_REQUIRED.md": decision,
        "15_FINAL_STATE.json": pretty(final_state),
        "independent_verifier/verify_ba12_r3_live_source_rfc_trigger_evidence.py": (ROOT / "scripts/ops/verify_ba12_r3_live_source_rfc_trigger_evidence.py").read_bytes(),
    }
    rows = [{"path": name, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()} for name, payload in sorted(payloads.items())]
    manifest = {"contract_id": "room16.ba12.r3.live_source_rfc_trigger.manifest@1", "schema_version": 1, "status": "STOP", "diagnostic_code": final_state["diagnostic_code"], "payloads": rows, "manifest_sha256": ""}
    manifest["manifest_sha256"] = manifest_hash(manifest)
    first = archive(payloads, manifest)
    second = archive(payloads, manifest)
    if first != second:
        raise SystemExit("STOP deterministic rebuild mismatch")
    output = ROOT / "outputs/release/ROOM16_BA12_R3_LIVE_SOURCE_RFC_TRIGGER_9B1FD85F2279_2026-08-24.zip"
    output.write_bytes(first)
    result = verify_package(output)
    receipt_path = output.with_suffix(".verification_receipt.json")
    receipt_path.write_bytes(pretty(result))
    print(json.dumps({**result, "verification_receipt": str(receipt_path)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
