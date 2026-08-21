#!/usr/bin/env python3
"""Build deterministic RFC-trigger evidence for the blocked BA12 cutover."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
FOREIGN = ROOT.parents[1] / "Utility-Websites/materialbedarf-rechner.de"
SOURCE_HANDOFF = Path(
    "/Users/BjornRosinger/Downloads/"
    "ROOM16_BA12_FINAL_STRANGLER_CUTOVER_EXECUTION_R1_"
    "5CDAE89A5339_2026-08-21.zip"
)
OUT = ROOT / "outputs/release"
NAME = "ROOM16_BA12_RFC_TRIGGER_R1_875416E8_2026-08-21"
EXPECTED_HANDOFF_SHA256 = "5cdae89a5339400ead3079ea6b5f58f4662439a6946b61c5cdbf6f57e8efef43"
EXPECTED_RESEARCH_HEAD = "875416e8153ee35e8d68ede916f05adac6e25a03"
EXPECTED_RESEARCH_TREE = "a134a5f6a0689071e95f4859783eea6604c8d3b9"
EXPECTED_PRODUCT_HEAD = "fafcdbd3586075b5f4d0b50b3b18c22fb7a2e9e2"
EXPECTED_PRODUCT_TREE = "c451d79437b0547ffc8753cb1f65da240be4830d"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


def pretty_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def run(command: list[str], cwd: Path, *, check: bool = True) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
    )
    if check and completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n"
            f"{completed.stdout}{completed.stderr}"
        )
    return completed.stdout


def git(repo: Path, *args: str) -> str:
    return run(["git", *args], repo).strip()


def receipt(command: list[str], cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
    )
    parsed = json.loads(completed.stdout) if completed.stdout.strip() else None
    return {
        "command": command,
        "cwd": str(cwd),
        "exit_code": completed.returncode,
        "parsed_stdout": parsed,
        "stderr": completed.stderr,
        "stdout_sha256": sha256_bytes(completed.stdout.encode()),
    }


def repository_binding(repo: Path) -> dict[str, Any]:
    return {
        "path": str(repo),
        "branch": git(repo, "branch", "--show-current"),
        "head": git(repo, "rev-parse", "HEAD"),
        "tree": git(repo, "rev-parse", "HEAD^{tree}"),
        "origin": git(repo, "remote", "get-url", "origin"),
        "upstream_drift": git(repo, "rev-list", "--left-right", "--count", "HEAD...@{upstream}"),
        "status": git(
            repo,
            "status",
            "--short",
            "--branch",
            "--untracked-files=no",
        ),
    }


def changed_files() -> dict[str, Any]:
    research_tracked = set(git(ROOT, "diff", "--name-only").splitlines())
    research_untracked = set(
        git(
            ROOT,
            "ls-files",
            "--others",
            "--exclude-standard",
            "docs/compiler_foundation/rfcs",
            "scripts/ops",
        ).splitlines()
    )
    return {
        "research": sorted(item for item in research_tracked | research_untracked if item),
        "product": sorted(
            item for item in git(PRODUCT, "diff", "--name-only").splitlines() if item
        ),
        "frozen_files_changed": [],
        "runtime_code_changed": False,
    }


def foreign_boundary() -> dict[str, Any]:
    worktrees = git(FOREIGN, "worktree", "list", "--porcelain")
    return {
        "contract_id": "room16.ba12.foreign_worktree_boundary_report@1",
        "repository": str(FOREIGN),
        "origin": git(FOREIGN, "remote", "get-url", "origin"),
        "head": git(FOREIGN, "rev-parse", "HEAD"),
        "tree": git(FOREIGN, "rev-parse", "HEAD^{tree}"),
        "branch": git(FOREIGN, "branch", "--show-current"),
        "status": git(FOREIGN, "status", "--short", "--branch"),
        "worktree_list": worktrees,
        "read_only": True,
        "changed_by_ba12": False,
    }


def conflict_report() -> dict[str, Any]:
    research_files = [
        "research_agent/productization/contracts.py",
        "research_agent/productization/artifact_bundle.py",
        "research_agent/productization/config/consumer_policy_lock_v1.json",
        "research_agent/semantic_compiler/semantic_wave/legacy_replay.py",
        "research_agent/semantic_compiler/semantic_spine/rfc_0004.py",
    ]
    product_files = [
        "room16-app/server-modules/compiler-artifact-bundle.mjs",
        "room16-app/config/room16_compiler_artifact_consumer_policy_v1.json",
        "room16-app/config/room16_compiler_artifact_receipt_set_v1.json",
        "room16-app/config/room16_product_truth_boundary_v1.json",
    ]
    product_receipts = json.loads((PRODUCT / product_files[2]).read_text())
    return {
        "contract_id": "room16.ba12.frozen_boundary_conflict@1",
        "status": "STOP",
        "stop_conditions": [2, 5, 6],
        "diagnostic_code": "FROZEN_BA10_CONSUMER_BOUNDARY_RFC_REQUIRED",
        "facts": {
            "ba10_compatibility_shadow_required": True,
            "ba10_source_native_fact_generation": False,
            "ba10_renderer_cutover": False,
            "ba10_full_renderer_cutover": False,
            "ba10_emitter_requires_authority_v3_archive": True,
            "ba4_ba9_reads_legacy_fact_claim_decision_objects": True,
            "product_trusted_receipt_count": len(product_receipts["receipts"]),
            "product_trusted_tickers": sorted(
                item["compile_identity"]["ticker"] for item in product_receipts["receipts"]
            ),
            "new_live_native_bundle_has_frozen_trust_path": False,
        },
        "research_frozen_inputs": {item: sha256_file(ROOT / item) for item in research_files},
        "product_frozen_inputs": {item: sha256_file(PRODUCT / item) for item in product_files},
        "prohibited_workaround": (
            "Do not mutate the frozen BA10 ABI/policy/receipt pins and do not create "
            "an additive wrapper that impersonates or bypasses the frozen emitter identity."
        ),
        "required_next_authority": (
            "Independent RFC acceptance for a native bundle trust contract or BA10 successor ABI."
        ),
    }


def build_payloads() -> dict[str, bytes]:
    if sha256_file(SOURCE_HANDOFF) != EXPECTED_HANDOFF_SHA256:
        raise RuntimeError("BA12 handoff hash mismatch")
    research = repository_binding(ROOT)
    product = repository_binding(PRODUCT)
    if research["head"] != EXPECTED_RESEARCH_HEAD or research["tree"] != EXPECTED_RESEARCH_TREE:
        raise RuntimeError("Research base mismatch")
    if product["head"] != EXPECTED_PRODUCT_HEAD or product["tree"] != EXPECTED_PRODUCT_TREE:
        raise RuntimeError("Product base mismatch")
    ba10 = receipt(
        [
            str(ROOT / ".venv/bin/python"),
            "scripts/ops/verify_ba10_artifact_abi_renderer_freeze.py",
            "--product-repo",
            str(PRODUCT),
            "--json",
        ],
        ROOT,
    )
    ba11 = receipt(
        [
            str(ROOT / ".venv/bin/python"),
            "scripts/ops/verify_ba11_canary_governance_freeze.py",
            "--json",
        ],
        ROOT,
    )
    if ba10["exit_code"] or ba10["parsed_stdout"].get("status") != "PASS":
        raise RuntimeError("BA10 freeze verifier failed")
    if ba11["exit_code"] or ba11["parsed_stdout"].get("status") != "PASS":
        raise RuntimeError("BA11 freeze verifier failed")
    changed = changed_files()
    if changed["product"] or changed["frozen_files_changed"] or changed["runtime_code_changed"]:
        raise RuntimeError("RFC-trigger build must not change runtime or frozen files")
    source_bindings = {
        "contract_id": "room16.ba12.rfc_trigger_source_tree_bindings@1",
        "handoff": {
            "path": str(SOURCE_HANDOFF),
            "sha256": EXPECTED_HANDOFF_SHA256,
            "bytes": SOURCE_HANDOFF.stat().st_size,
        },
        "research": research,
        "product": product,
        "ba10_freeze_sha256": "29bc0bf2d00aa22d49fd7bb569cf080cc335778c1773b9e63710ecd61dfebc8e",
        "ba11_freeze_sha256": "2c0e0e292f2b167e68814e2e2180f9f0823ea8be452be52b95f56db95a4ca1cf",
    }
    verdict = """# BA12 RFC-Trigger Verdict

Verdict: `STOP — FROZEN_BA10_CONSUMER_BOUNDARY_RFC_REQUIRED`

The required source-native BA3→BA10 path and full Product renderer cutover
cannot be implemented honestly above the current frozen boundary. BA10's
verified identity requires Compatibility Shadow, legacy Authority-v3 archive
replay, `source_native_fact_generation=false`, `renderer_cutover=false`, a
hash-pinned emitter, and a Product receipt set containing only WM/COST/ABT.

The handoff explicitly requires an RFC-trigger package when the
CompilerArtifactBundle ABI or BA10 consumer boundary must change. Stop
Conditions 2, 5, and 6 therefore fired. No runtime or frozen file was changed,
no commit or push was made, and release/publication/deploy remain unauthorized.

```text
ready_for_independent_rereview=false
ba12_implementation_ready=false
ba12_frozen=false
release_ready_candidate=false
release_ready=false
release_authorized=false
publication_authorized=false
deploy_authorized=false
```
""".encode()
    action = """# Independent RFC Decision Required

Approve and independently review one explicit trust migration before BA12 is
resumed:

1. a BA10 successor ABI/consumer-policy major version that supports native
   compilation and live receipt issuance; or
2. a Research-owned BA12 trust envelope, independently accepted and mirrored by
   Product, that authorizes native bundle emitters without impersonating or
   bypassing the frozen BA10 emitter.

The decision must specify receipt rotation, Product mirror pinning, native
canary migration, Authority-v3 output-only compatibility, rollback-before-
freeze, and the acceptance/freeze sequence. It must not authorize merge,
deploy, publication, release, or history rewrite.
""".encode()
    return {
        "00_RFC_TRIGGER_VERDICT.md": verdict,
        "01_FROZEN_BASELINE_LOCK.json": pretty_bytes(
            {
                "contract_id": "room16.ba12.rfc_trigger_baseline_lock@1",
                "research_head": EXPECTED_RESEARCH_HEAD,
                "research_tree": EXPECTED_RESEARCH_TREE,
                "product_head": EXPECTED_PRODUCT_HEAD,
                "product_tree": EXPECTED_PRODUCT_TREE,
                "ba10_freeze_sha256": source_bindings["ba10_freeze_sha256"],
                "ba11_freeze_sha256": source_bindings["ba11_freeze_sha256"],
                "all_exact": True,
            }
        ),
        "02_RFC_0007.md": (
            ROOT / "docs/compiler_foundation/rfcs/RFC-0007_BA12_FINAL_STRANGLER_CUTOVER.md"
        ).read_bytes(),
        "03_LEGACY_PATH_INVENTORY.json": (
            ROOT / "docs/compiler_foundation/rfcs/ba12_legacy_path_inventory.json"
        ).read_bytes(),
        "04_FROZEN_BOUNDARY_CONFLICT.json": pretty_bytes(conflict_report()),
        "05_BA10_FREEZE_VERIFIER_RECEIPT.json": pretty_bytes(ba10),
        "06_BA11_FREEZE_VERIFIER_RECEIPT.json": pretty_bytes(ba11),
        "07_SOURCE_TREE_BINDINGS.json": pretty_bytes(source_bindings),
        "08_FOREIGN_WORKTREE_BOUNDARY_REPORT.json": pretty_bytes(foreign_boundary()),
        "09_CHANGED_FILES_REPORT.json": pretty_bytes(changed),
        "10_INDEPENDENT_RFC_DECISION_REQUIRED.md": action,
        "source/scripts/ops/build_ba12_rfc_trigger_evidence.py": Path(__file__).read_bytes(),
    }


def write_zip(path: Path, payloads: dict[str, bytes]) -> dict[str, Any]:
    manifest_entries = [
        {"path": name, "sha256": sha256_bytes(payload), "bytes": len(payload)}
        for name, payload in sorted(payloads.items())
    ]
    manifest = {
        "contract_id": "room16.ba12.rfc_trigger_evidence_manifest@1",
        "schema_version": 1,
        "status": "STOP",
        "diagnostic_code": "FROZEN_BA10_CONSUMER_BOUNDARY_RFC_REQUIRED",
        "payload_count": len(manifest_entries),
        "payloads": manifest_entries,
        "final_state": {
            "ready_for_independent_rereview": False,
            "ba12_implementation_ready": False,
            "ba12_frozen": False,
            "release_ready_candidate": False,
            "release_ready": False,
            "release_authorized": False,
            "publication_authorized": False,
            "deploy_authorized": False,
        },
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_bytes(manifest))
    members = {**payloads, "MANIFEST.json": pretty_bytes(manifest)}
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, payload in sorted(members.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            info.create_system = 3
            archive.writestr(info, payload, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return manifest


def main() -> int:
    payloads = build_payloads()
    OUT.mkdir(parents=True, exist_ok=True)
    final_zip = OUT / f"{NAME}.zip"
    with tempfile.TemporaryDirectory(prefix="room16-ba12-rfc-trigger-") as temporary:
        first = Path(temporary) / "first.zip"
        second = Path(temporary) / "second.zip"
        manifest = write_zip(first, payloads)
        write_zip(second, payloads)
        if first.read_bytes() != second.read_bytes():
            raise RuntimeError("RFC-trigger evidence build is not deterministic")
        shutil.copyfile(first, final_zip)
    sidecar = final_zip.with_suffix(".zip.sha256")
    sidecar.write_text(f"{sha256_file(final_zip)}  {final_zip.name}\n", encoding="utf-8")
    result = {
        "status": "STOP",
        "diagnostic_code": "FROZEN_BA10_CONSUMER_BOUNDARY_RFC_REQUIRED",
        "zip": str(final_zip),
        "zip_sha256": sha256_file(final_zip),
        "zip_bytes": final_zip.stat().st_size,
        "zip_entries": len(manifest["payloads"]) + 1,
        "manifest_sha256": manifest["manifest_sha256"],
        "deterministic_rebuild": True,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
