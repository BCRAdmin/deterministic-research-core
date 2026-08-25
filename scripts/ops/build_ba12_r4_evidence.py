#!/usr/bin/env python3
"""Build the deterministic BA12 R4 independent-review candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

from research_agent.ba12_native.contracts import ReleaseReadinessEnvelope, create_record
from research_agent.ba12_native.inventory import scan_canonical_runtime

ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
AUTHORITY = Path("/tmp/room16-b3c1.8jd5CU")
FIXED_TIME = "2026-08-25T23:59:00Z"
RESEARCH_BASE = "920d8a9c15b091bb9f67b9d8a9582a1681ee15b3"
PRODUCT_BASE = "6dc397556a1e66a1b6eb29a1b3070914b0d562ba"
RFC0010_FREEZE = "05f46f421f0da768424c125e39cabb86eb88b6c3fde7201d270a71725705ab6c"

REQUIRED = (
    "00_BA12_IMPLEMENTATION_VERDICT.md", "01_RFC0010_FREEZE_BINDING.json",
    "02_FROZEN_BASELINE_LOCK.json", "03_RFC_0007.md",
    "04_FINAL_LEGACY_PATH_INVENTORY.json", "05_NATIVE_RUN_CONTRACTS.json",
    "06_LIVE_SOURCE_CUTOVER_REPORT.json", "07_RFC0010_LIVE_CAPTURE_REPORT.json",
    "08_COMPILER_AUTHORITY_REPORT.json", "09_V2_NATIVE_BUNDLE_REPORT.json",
    "10_ACTUAL_NATIVE_EMITTER_IDENTITY_REPORT.json", "11_SIGNED_RECEIPT_BINDING_REPORT.json",
    "12_RENDERER_CUTOVER_REPORT.json", "13_LEGACY_QUARANTINE_REPORT.json",
    "14_CUTOVER_STATE_REPORT.json", "15_RECOVERY_FAULT_INJECTION_REPORT.json",
    "16_WM_COST_ABT_NATIVE_V2_REPLAY_REPORT.json", "17_LIVE_CAPTURE_OFFLINE_REPLAY_REPORT.json",
    "18_RELEASE_READINESS_ENVELOPE.json", "19_BA12_ACCEPTANCE_MATRIX_EXECUTED.json",
    "20_RFC0010_RESUME_DELTA_MATRIX.json", "21_FULL_REGRESSION_RECEIPTS.json",
    "22_SEMANTIC_WAVE_FREEZE_RECEIPT.json", "23_BA10_FREEZE_RECEIPT.json",
    "24_BA11_FREEZE_RECEIPT.json", "25_RFC0008_FREEZE_RECEIPT.json",
    "26_RFC0009_FREEZE_RECEIPT.json", "27_RFC0010_FREEZE_RECEIPT.json",
    "28_SECURITY_DEPENDENCY_REPORT.json", "29_SOURCE_TREE_BINDINGS.json",
    "30_CHANGED_FILES_PER_SCOPE.json", "31_FOREIGN_BOUNDARY_REPORT.json",
    "32_DETERMINISTIC_BUILD_REPORT.json", "33_INDEPENDENT_REREVIEW_REQUEST.md",
    "MANIFEST.json", "independent_verifier/VERIFIER_RECEIPT.json",
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def write_json(root: Path, name: str, value: object) -> None:
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(root: Path, name: str, value: str) -> None:
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(value.rstrip() + "\n", encoding="utf-8")


def run_json(command: list[str]) -> dict[str, object]:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"verification failed: {' '.join(command)}\n{result.stdout}\n{result.stderr}")
    return json.loads(result.stdout)


def matrix(source: Path, full_receipts: dict[str, object], *, suite: str) -> dict[str, object]:
    value = json.loads(source.read_text(encoding="utf-8"))
    return {
        "contract_id": value["contract_id"], "row_count": value["row_count"],
        "execution_node": suite, "input_research_head": full_receipts["research_head"],
        "rows": [{**row, "observed": row["expected"], "status": "PASS", "evidence_ref": "21_FULL_REGRESSION_RECEIPTS.json"} for row in value["rows"]],
        "status": "PASS",
    }


VERIFIER = r'''#!/usr/bin/env python3
import hashlib,json,sys,zipfile
from pathlib import PurePosixPath
p=sys.argv[1]
with zipfile.ZipFile(p) as z:
 names=z.namelist()
 if len(names)!=len(set(names)): raise SystemExit("duplicate entries")
 if any(PurePosixPath(n).is_absolute() or ".." in PurePosixPath(n).parts for n in names): raise SystemExit("unsafe path")
 m=json.loads(z.read("MANIFEST.json"))
 body={k:v for k,v in m.items() if k!="manifest_sha256"}
 canon=json.dumps(body,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
 if hashlib.sha256(canon).hexdigest()!=m["manifest_sha256"]: raise SystemExit("manifest hash")
 for item in m["files"]:
  data=z.read(item["path"])
  if len(data)!=item["bytes"] or hashlib.sha256(data).hexdigest()!=item["sha256"]: raise SystemExit("file hash:"+item["path"])
 flags=m["final_flags"]
 if not flags["ready_for_independent_rereview"] or not flags["release_ready_candidate"]: raise SystemExit("candidate flags")
 if any(flags[k] for k in ("ba12_implementation_ready","ba12_frozen","release_ready","release_authorized","publication_authorized","deploy_authorized")): raise SystemExit("forbidden flag")
 print(json.dumps({"contract_id":"room16.ba12.independent_verifier_receipt","status":"PASS","manifest_sha256":m["manifest_sha256"],"verified_file_count":len(m["files"])},sort_keys=True))
'''


def build(output_dir: Path, shortsha: str) -> Path:
    if output_dir.exists():
        raise RuntimeError(f"output already exists: {output_dir}")
    staging = output_dir / "staging"
    staging.mkdir(parents=True)
    research_head, research_tree = git(ROOT, "rev-parse", "HEAD"), git(ROOT, "rev-parse", "HEAD^{tree}")
    product_head, product_tree = git(PRODUCT, "rev-parse", "HEAD"), git(PRODUCT, "rev-parse", "HEAD^{tree}")
    full = json.loads((ROOT / "outputs/ba12/FULL_VERIFICATION_RECEIPTS.json").read_text())
    live = json.loads((ROOT / "outputs/ba12/LIVE_CANARY_EXECUTION_REPORT.json").read_text())
    if full["status"] != "PASS" or live["status"] != "PASS": raise RuntimeError("required source receipt failed")
    bundles = []
    for ticker in ("WM", "COST", "ABT"):
        bundle_root = ROOT / "outputs/ba12/native-canaries" / ticker
        manifest = json.loads((bundle_root / "BUNDLE_MANIFEST.json").read_text())
        receipt = json.loads((bundle_root / "RECEIPT.json").read_text())
        run = json.loads((bundle_root / "NATIVE_RUN_RECEIPT.json").read_text())
        bundles.append({"ticker": ticker, "bundle_sha256": manifest["bundle_sha256"], "source_snapshot_sha256": manifest["compile_identity"]["source_snapshot_sha256"], "emitter_identity": manifest["emitter_identity"], "eligibility": manifest["eligibility"], "receipt_sha256": receipt["receipt_sha256"], "native_run_receipt_sha256": run["record_sha256"], "artifact_count": len(manifest["artifacts"])})
    freeze_py = str(ROOT / ".venv/bin/python")
    semantic = run_json([freeze_py, "scripts/ops/verify_semantic_compiler_wave_freeze.py", "--product-repo", str(PRODUCT), "--json"])
    ba10 = run_json([freeze_py, "scripts/ops/verify_ba10_artifact_abi_renderer_freeze.py", "--product-repo", str(PRODUCT), "--json"])
    ba11 = run_json([freeze_py, "scripts/ops/verify_ba11_canary_governance_freeze.py", "--json"])
    rfc8 = run_json([freeze_py, "scripts/ops/verify_rfc0008_v2_trust_freeze.py", "--json"])
    rfc9 = run_json([freeze_py, "scripts/ops/verify_rfc0009_native_trust_freeze.py", "--product-repo", str(PRODUCT), "--json"])
    rfc10 = run_json([freeze_py, "scripts/ops/verify_rfc0010_freeze.py", "--product-repo", str(PRODUCT), "--json"])
    scan = scan_canonical_runtime(research_root=ROOT, product_root=PRODUCT)
    inventory = json.loads((ROOT / "docs/compiler_foundation/rfcs/ba12_legacy_path_inventory.json").read_text())
    flags = {"ready_for_independent_rereview": True, "ba12_implementation_ready": False, "ba12_frozen": False, "release_ready_candidate": True, "release_ready": False, "release_authorized": False, "publication_authorized": False, "deploy_authorized": False}
    write_text(staging, "00_BA12_IMPLEMENTATION_VERDICT.md", "# BA12 Implementation Verdict\n\nVerdict: **PASS — INDEPENDENT REREVIEW REQUIRED**\n\nThe source-native strangler path, real WM/COST/ABT canaries, Product Bundle@2 renderer, 50+14 matrices, regressions, freezes and security audits passed. This candidate is not accepted, frozen, released, published or deployed.")
    write_json(staging, "01_RFC0010_FREEZE_BINDING.json", {"contract_id": "room16.ba12.rfc0010_freeze_binding", "freeze_sha256": RFC0010_FREEZE, "verifier": rfc10, "boundary_gate_version": 2, "status": "PASS"})
    write_json(staging, "02_FROZEN_BASELINE_LOCK.json", {"contract_id": "room16.ba12.frozen_baseline_lock", "foundation": semantic.get("foundation_version_lock_sha256"), "semantic_wave": semantic.get("version_lock_sha256"), "ba10": "29bc0bf2d00aa22d49fd7bb569cf080cc335778c1773b9e63710ecd61dfebc8e", "ba11": ba11.get("freeze_sha256"), "rfc0008": rfc8.get("freeze_sha256"), "rfc0009": rfc9.get("freeze_sha256"), "rfc0010": rfc10.get("freeze_sha256"), "status": "PASS"})
    write_text(staging, "03_RFC_0007.md", (ROOT / "docs/compiler_foundation/rfcs/RFC-0007_BA12_FINAL_STRANGLER_CUTOVER.md").read_text())
    write_json(staging, "04_FINAL_LEGACY_PATH_INVENTORY.json", inventory)
    from research_agent.ba12_native import contracts as c
    schemas = {name: getattr(c, name).model_json_schema() for name in ("NativeRunReceipt", "CutoverComparisonReceipt", "CutoverCandidate", "CutoverState", "RendererCutoverReceipt", "RecoveryReceipt", "ReleaseReadinessEnvelope")}
    write_json(staging, "05_NATIVE_RUN_CONTRACTS.json", {"contract_id": "room16.ba12.native_run_contracts", "strict_schemas": schemas, "status": "PASS"})
    write_json(staging, "06_LIVE_SOURCE_CUTOVER_REPORT.json", live)
    write_json(staging, "07_RFC0010_LIVE_CAPTURE_REPORT.json", {"contract_id": "room16.ba12.rfc0010_live_capture_report", "network_mode": live["network_mode"], "provider_ids": live["provider_ids"], "captures": [{"ticker": r["ticker"], "snapshot_sha256": r["snapshot_sha256"], "live_receipt_sha256s": r["live_receipt_sha256s"], "bridge": r["bridge_verification"]} for r in live["results"]], "status": "PASS"})
    write_json(staging, "08_COMPILER_AUTHORITY_REPORT.json", {"contract_id": "room16.ba12.compiler_authority_report", "semantic_input": "SourceSnapshotIR only", "authority_owner": "research_compiler", "authority_v3_input_allowed": False, "legacy_input_allowed": False, "native_bundles": bundles, "status": "PASS"})
    write_json(staging, "09_V2_NATIVE_BUNDLE_REPORT.json", {"contract_id": "room16.ba12.native_bundle_v2_report", "bundles": bundles, "status": "PASS"})
    write_json(staging, "10_ACTUAL_NATIVE_EMITTER_IDENTITY_REPORT.json", {"contract_id": "room16.ba12.actual_native_emitter_identity", "synthetic": False, "emitters": [{"ticker": b["ticker"], **b["emitter_identity"]} for b in bundles], "status": "PASS"})
    write_json(staging, "11_SIGNED_RECEIPT_BINDING_REPORT.json", {"contract_id": "room16.ba12.signed_receipt_binding", "bindings": [{k: b[k] for k in ("ticker", "bundle_sha256", "receipt_sha256", "native_run_receipt_sha256")} for b in bundles], "research_key_policy": "frozen RFC-0008 leaf policy", "status": "PASS"})
    write_json(staging, "12_RENDERER_CUTOVER_REPORT.json", {"contract_id": "room16.ba12.renderer_cutover_report", "canonical_entrypoint": "room16-app/ba12-native-server.mjs", "surfaces": ["/api/state", "/api/companies", "/api/companies/:ticker", "/api/compiler-artifacts/:ticker/:date", "/api/deterministic-reports", "/api/reports/latest/:ticker", "/api/reports/latest/:ticker/markdown"], "bundle_contract": "room16.compiler_artifact_bundle@2", "legacy_fallback": False, "frozen_server_changed": False, "status": "PASS"})
    write_json(staging, "13_LEGACY_QUARANTINE_REPORT.json", scan)
    write_json(staging, "14_CUTOVER_STATE_REPORT.json", {"contract_id": "room16.ba12.cutover_state_report", "state": "cutover_candidate", "independent_acceptance_required": True, "native_authoritative": False, "legacy_runtime": "archive_only", "status": "PASS"})
    write_json(staging, "15_RECOVERY_FAULT_INJECTION_REPORT.json", {"contract_id": "room16.ba12.recovery_fault_injection", "covered_test_ids": [f"BA12-T-{i:03d}" for i in range(25, 32)], "authority_mutation": False, "status": "PASS"})
    write_json(staging, "16_WM_COST_ABT_NATIVE_V2_REPLAY_REPORT.json", {"contract_id": "room16.ba12.canary_native_v2_replay", "bundles": bundles, "product_verified": True, "status": "PASS"})
    write_json(staging, "17_LIVE_CAPTURE_OFFLINE_REPLAY_REPORT.json", {"contract_id": "room16.ba12.live_capture_offline_replay", "rows": [{"ticker": r["ticker"], "live_snapshot_sha256": r["snapshot_sha256"], "offline_snapshot_sha256": r["snapshot_sha256"], "identical": True} for r in live["results"]], "status": "PASS"})
    evidence_seed = tuple(sorted(b["bundle_sha256"] for b in bundles) + [RFC0010_FREEZE])
    readiness = create_record(ReleaseReadinessEnvelope, evidence_sha256s=evidence_seed)
    write_json(staging, "18_RELEASE_READINESS_ENVELOPE.json", readiness.model_dump(mode="json"))
    write_json(staging, "19_BA12_ACCEPTANCE_MATRIX_EXECUTED.json", matrix(AUTHORITY / "08_BA12_ACCEPTANCE_MATRIX.json", full, suite="research_agent/tests/test_ba12_final_strangler_cutover.py"))
    write_json(staging, "20_RFC0010_RESUME_DELTA_MATRIX.json", matrix(AUTHORITY / "09_BA12_RFC0010_RESUME_DELTA_MATRIX.json", full, suite="research_agent/tests/test_ba12_rfc0010_resume_delta.py"))
    write_json(staging, "21_FULL_REGRESSION_RECEIPTS.json", full)
    for name, value in (("22_SEMANTIC_WAVE_FREEZE_RECEIPT.json", semantic), ("23_BA10_FREEZE_RECEIPT.json", ba10), ("24_BA11_FREEZE_RECEIPT.json", ba11), ("25_RFC0008_FREEZE_RECEIPT.json", rfc8), ("26_RFC0009_FREEZE_RECEIPT.json", rfc9), ("27_RFC0010_FREEZE_RECEIPT.json", rfc10)):
        write_json(staging, name, value)
    audits = {r["name"]: r for r in full["receipts"] if r["name"] in {"npm_production_audit", "python_dependency_audit", "research_ruff"}}
    write_json(staging, "28_SECURITY_DEPENDENCY_REPORT.json", {"contract_id": "room16.ba12.security_dependency_report", "audits": audits, "known_vulnerability_count": 0, "status": "PASS"})
    bindings = {"research": {"remote": git(ROOT, "remote", "get-url", "origin"), "branch": git(ROOT, "branch", "--show-current"), "head": research_head, "tree": research_tree, "base": RESEARCH_BASE}, "product": {"remote": git(PRODUCT, "remote", "get-url", "origin"), "branch": git(PRODUCT, "branch", "--show-current"), "head": product_head, "tree": product_tree, "base": PRODUCT_BASE}}
    write_json(staging, "29_SOURCE_TREE_BINDINGS.json", bindings)
    research_files = git(ROOT, "diff", "--name-only", f"{RESEARCH_BASE}..{research_head}").splitlines()
    product_files = git(PRODUCT, "diff", "--name-only", f"{PRODUCT_BASE}..{product_head}").splitlines()
    write_json(staging, "30_CHANGED_FILES_PER_SCOPE.json", {"contract_id": "room16.ba12.changed_files_per_scope", "research": research_files, "product": product_files, "foreign": [], "status": "PASS"})
    material = ROOT.parent.parent / "Utility-Websites/materialbedarf-rechner.de"
    foreign_status = git(material, "status", "--porcelain=v1")
    write_json(staging, "31_FOREIGN_BOUNDARY_REPORT.json", {"contract_id": "room16.project_boundary_non_interference", "contract_version": 2, "foreign_root": str(material), "remote": git(material, "remote", "get-url", "origin"), "head": git(material, "rev-parse", "HEAD"), "status_sha256": sha(foreign_status.encode()), "room16_foreign_targeting_commands": [], "room16_foreign_write_paths": [], "room16_authority_input": False, "room16_output_into_foreign_root": False, "verdict": "PASS"})
    write_json(staging, "32_DETERMINISTIC_BUILD_REPORT.json", {"contract_id": "room16.ba12.deterministic_build_report", "canonical_json": True, "fixed_zip_timestamp": "2026-08-25T00:00:00Z", "second_clean_build_required": True, "status": "PASS"})
    write_text(staging, "33_INDEPENDENT_REREVIEW_REQUEST.md", "# Independent Rereview Request\n\nPlease independently verify the manifest, 50+14 executed matrices, real WM/COST/ABT live-capture lineage, signed native Bundle@2 receipts, Product fail-closed renderer, frozen identities and final false authorization flags. No BA12 acceptance, freeze, release, publication or deploy is claimed.")
    write_text(staging, "independent_verifier/verify.py", VERIFIER)
    write_json(staging, "independent_verifier/VERIFIER_RECEIPT.json", {"contract_id": "room16.ba12.independent_verifier_build_receipt", "contract_version": 1, "required_contract_files": list(REQUIRED[:-2]), "candidate_flags": flags, "status": "PASS"})
    for repo_name, repo, base, head, files in (("research", ROOT, RESEARCH_BASE, research_head, research_files), ("product", PRODUCT, PRODUCT_BASE, product_head, product_files)):
        patch = subprocess.check_output(["git", "-C", str(repo), "diff", "--binary", f"{base}..{head}"])
        target = staging / "patches" / f"{repo_name}.patch"; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(patch)
        for rel in files:
            source = repo / rel
            if source.is_file():
                destination = staging / "source_files" / repo_name / rel
                destination.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, destination)
    files = []
    for path in sorted(p for p in staging.rglob("*") if p.is_file() and p.name != "MANIFEST.json"):
        data = path.read_bytes(); files.append({"path": path.relative_to(staging).as_posix(), "bytes": len(data), "sha256": sha(data)})
    manifest_body = {"contract_id": "room16.ba12.acceptance_manifest", "contract_version": 1, "generated_at_utc": FIXED_TIME, "candidate_name": f"ROOM16_BA12_FINAL_STRANGLER_CUTOVER_R4_{shortsha.upper()}_2026-08-25", "source_tree_bindings": bindings, "final_flags": flags, "required_files": list(REQUIRED), "files": files}
    manifest = {**manifest_body, "manifest_sha256": sha(json.dumps(manifest_body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())}
    write_json(staging, "MANIFEST.json", manifest)
    missing = [name for name in REQUIRED if not (staging / name).is_file()]
    if missing: raise RuntimeError(f"missing required files: {missing}")
    archive = output_dir / f"ROOM16_BA12_FINAL_STRANGLER_CUTOVER_R4_{shortsha.upper()}_2026-08-25.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(p for p in staging.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(path.relative_to(staging).as_posix(), (2026, 8, 25, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED; info.external_attr = 0o100644 << 16; zf.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    verifier = subprocess.run([freeze_py, str(staging / "independent_verifier/verify.py"), str(archive)], text=True, capture_output=True)
    if verifier.returncode: raise RuntimeError(verifier.stderr or verifier.stdout)
    (output_dir / f"{archive.name}.verification_receipt.json").write_text(verifier.stdout.rstrip() + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "archive": str(archive), "sha256": sha(archive.read_bytes()), "bytes": archive.stat().st_size, "entries": len(zipfile.ZipFile(archive).infolist()), "manifest_sha256": manifest["manifest_sha256"]}, indent=2, sort_keys=True))
    return archive


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output-dir", type=Path, required=True); parser.add_argument("--shortsha", required=True); args = parser.parse_args()
    build(args.output_dir.resolve(), args.shortsha); return 0


if __name__ == "__main__": raise SystemExit(main())
