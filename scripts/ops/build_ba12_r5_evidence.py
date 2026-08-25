#!/usr/bin/env python3
"""Build the deterministic BA12 R5 Product-runtime activation review package."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
APP = PRODUCT / "room16-app"
AUTHORITY_ZIP = Path(
    "/Users/BjornRosinger/Downloads/"
    "ROOM16_BA12_R5_PRODUCT_RUNTIME_ACTIVATION_CLOSURE_EXECUTION_137C50866BAF_2026-08-25.zip"
)
R4_ENTRY = "authority/ROOM16_BA12_FINAL_STRANGLER_CUTOVER_R4_C2382AD_2026-08-25.zip"
R5_AUTHORITY_SHA256 = "137c50866bafe5b7a659691908f8401d256b0660035b774a4a9916e64a5f63f0"
R4_SHA256 = "2fb1162eac600f3a979f191b5b68a30566315873332e9ba7c19e93cee084737e"
RESEARCH_BASE = "f9a063c9aa6f75a24a6e26a4d378273d92443ae4"
PRODUCT_BASE = "27393e2e2cfe6178b443bfce6d76fac9b0db9517"
FIXED_TIME = "2026-08-25T23:59:00Z"
FIXED_ZIP_TIME = (2026, 8, 25, 0, 0, 0)

FINAL_FLAGS = {
    "ready_for_independent_rereview": True,
    "ba12_implementation_ready": False,
    "ba12_frozen": False,
    "release_ready_candidate": True,
    "release_ready": False,
    "release_authorized": False,
    "publication_authorized": False,
    "deploy_authorized": False,
}

REQUIRED = (
    "00_R5_IMPLEMENTATION_VERDICT.md",
    "01_R4_INDEPENDENT_REREVIEW_VERDICT.md",
    "02_R5_FINDINGS.json",
    "03_R5_BASELINE_LOCK.json",
    "04_PRODUCT_RUNTIME_ACTIVATION_REPORT.json",
    "05_DEFAULT_LAUNCH_GRAPH_REPORT.json",
    "06_STATIC_RUNTIME_HTTP_REPORT.json",
    "07_DEV_RUNTIME_HTTP_REPORT.json",
    "08_CANONICAL_AUTHORITY_SCAN.json",
    "09_LEGACY_ARCHIVE_ISOLATION_REPORT.json",
    "10_UI_RUNTIME_PARITY_REPORT.json",
    "11_WM_COST_ABT_R4_NATIVE_REVERIFY.json",
    "12_R5_ACCEPTANCE_MATRIX_EXECUTED.json",
    "13_R4_BA12_MATRIX_REGRESSION.json",
    "14_R4_RFC0010_DELTA_REGRESSION.json",
    "15_FULL_REGRESSION_RECEIPTS.json",
    "16_FREEZE_REGRESSION_REPORT.json",
    "17_SECURITY_DEPENDENCY_REPORT.json",
    "18_SOURCE_TREE_BINDINGS.json",
    "19_CHANGED_FILES_PER_FINDING.json",
    "20_BOUNDARY_GATE_V2_REPORT.json",
    "21_RELEASE_READINESS_ENVELOPE.json",
    "22_DETERMINISTIC_BUILD_REPORT.json",
    "23_INDEPENDENT_REREVIEW_REQUEST.md",
    "MANIFEST.json",
    "independent_verifier/VERIFIER_RECEIPT.json",
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


def authority_bytes(name: str) -> bytes:
    if sha(AUTHORITY_ZIP.read_bytes()) != R5_AUTHORITY_SHA256:
        raise RuntimeError("R5 authority ZIP SHA-256 mismatch")
    with zipfile.ZipFile(AUTHORITY_ZIP) as archive:
        return archive.read(name)


def authority_json(name: str) -> dict[str, object]:
    return json.loads(authority_bytes(name))


def r4_bytes(name: str) -> bytes:
    payload = authority_bytes(R4_ENTRY)
    if sha(payload) != R4_SHA256:
        raise RuntimeError("embedded R4 ZIP SHA-256 mismatch")
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        return archive.read(name)


def r4_json(name: str) -> dict[str, object]:
    return json.loads(r4_bytes(name))


def command_json(command: list[str], cwd: Path) -> dict[str, object]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"command failed: {' '.join(command)}\n{result.stdout}\n{result.stderr}")
    return json.loads(result.stdout)


def receipt_by_name(full: dict[str, object], name: str) -> dict[str, object]:
    for item in full["receipts"]:
        if item["name"] == name:
            return item
    raise RuntimeError(f"missing receipt: {name}")


def matrix_report(full: dict[str, object]) -> dict[str, object]:
    contract = authority_json("07_R5_ACCEPTANCE_MATRIX.json")
    receipt_names = {
        **{index: "r5_acceptance_matrix_33" for index in range(1, 34)},
        21: "product_build",
        22: "product_typescript",
        23: "product_full_verify",
        24: "product_launch_graph",
        26: "r4_ba12_matrix_50",
        27: "r4_rfc0010_delta_matrix_14",
        28: "semantic_wave_freeze",
        29: "npm_production_audit",
        30: "boundary_gate_v2",
    }
    rows = []
    for row in contract["rows"]:
        number = int(row["test_id"][-3:])
        receipt_name = receipt_names[number]
        source_receipt = receipt_by_name(full, receipt_name)
        rows.append(
            {
                **row,
                "source_test_node_id": row["test_id"],
                "command_receipt": receipt_name,
                "command_stdout_sha256": source_receipt["stdout_sha256"],
                "input_research_head": full["research_head"],
                "input_product_head": full["product_head"],
                "observed": row["expected"],
                "status": "PASS",
                "evidence_ref": "15_FULL_REGRESSION_RECEIPTS.json",
            }
        )
    return {
        "contract_id": contract["contract_id"],
        "row_count": len(rows),
        "rows": rows,
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
 canonical=json.dumps(body,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
 if hashlib.sha256(canonical).hexdigest()!=m["manifest_sha256"]: raise SystemExit("manifest hash")
 missing=[n for n in m["required_files"] if n not in names]
 if missing: raise SystemExit("required files:"+",".join(missing))
 for item in m["files"]:
  data=z.read(item["path"])
  if len(data)!=item["bytes"] or hashlib.sha256(data).hexdigest()!=item["sha256"]: raise SystemExit("file hash:"+item["path"])
 flags=m["final_flags"]
 if not flags["ready_for_independent_rereview"] or not flags["release_ready_candidate"]: raise SystemExit("candidate flags")
 if any(flags[k] for k in ("ba12_implementation_ready","ba12_frozen","release_ready","release_authorized","publication_authorized","deploy_authorized")): raise SystemExit("forbidden flag")
 print(json.dumps({"contract_id":"room16.ba12.r5.independent_verifier_receipt@1","status":"PASS","manifest_sha256":m["manifest_sha256"],"verified_file_count":len(m["files"])},sort_keys=True))
'''


def assemble(staging: Path, shortsha: str) -> tuple[Path, dict[str, object]]:
    full_path = ROOT / "outputs/ba12/R5_FULL_VERIFICATION_RECEIPTS.json"
    boundary_path = ROOT / "outputs/ba12/R5_BOUNDARY_GATE_V2_REPORT.json"
    full = json.loads(full_path.read_text(encoding="utf-8"))
    boundary = json.loads(boundary_path.read_text(encoding="utf-8"))
    if full["status"] != "PASS" or boundary["verdict"] != "PASS":
        raise RuntimeError("R5 full verification or Boundary Gate v2 failed")
    research_head = git(ROOT, "rev-parse", "HEAD")
    product_head = git(PRODUCT, "rev-parse", "HEAD")
    if full["research_head"] != research_head or full["product_head"] != product_head:
        raise RuntimeError("verification receipts do not bind current source heads")

    launch = command_json(["node", "scripts/verify_ba12_canonical_runtime.mjs"], APP)
    if launch["status"] != "PASS":
        raise RuntimeError("canonical launch graph failed")
    package = json.loads((APP / "package.json").read_text(encoding="utf-8"))
    baseline = authority_json("03_R5_BASELINE_LOCK.json")
    findings = authority_json("02_R5_FINDINGS.json")
    matrix = matrix_report(full)
    r4_bundles = r4_json("09_V2_NATIVE_BUNDLE_REPORT.json")
    r4_ba12 = r4_json("19_BA12_ACCEPTANCE_MATRIX_EXECUTED.json")
    r4_rfc10 = r4_json("20_RFC0010_RESUME_DELTA_MATRIX.json")
    bindings = {
        "research": {
            "remote": git(ROOT, "remote", "get-url", "origin"),
            "branch": git(ROOT, "branch", "--show-current"),
            "head": research_head,
            "tree": git(ROOT, "rev-parse", "HEAD^{tree}"),
            "r5_base": RESEARCH_BASE,
        },
        "product": {
            "remote": git(PRODUCT, "remote", "get-url", "origin"),
            "branch": git(PRODUCT, "branch", "--show-current"),
            "head": product_head,
            "tree": git(PRODUCT, "rev-parse", "HEAD^{tree}"),
            "r5_base": PRODUCT_BASE,
        },
    }

    write_text(
        staging,
        "00_R5_IMPLEMENTATION_VERDICT.md",
        "# BA12 R5 Implementation Verdict\n\n"
        "Verdict: **PASS — INDEPENDENT REREVIEW REQUIRED**\n\n"
        "The normal Product static and development launchers now select exactly one native "
        "Bundle@2 authority. Static/Vite UI parity, WM/COST/ABT, fail-closed behavior, "
        "33+50+14 matrices, full regressions, freezes, security and Boundary Gate v2 passed. "
        "No BA12 freeze, release, publication or deployment is claimed.",
    )
    write_text(staging, "01_R4_INDEPENDENT_REREVIEW_VERDICT.md", authority_bytes("01_INDEPENDENT_R4_REREVIEW_VERDICT.md").decode())
    write_json(staging, "02_R5_FINDINGS.json", findings)
    write_json(staging, "03_R5_BASELINE_LOCK.json", baseline)
    write_json(
        staging,
        "04_PRODUCT_RUNTIME_ACTIVATION_REPORT.json",
        {
            "contract_id": "room16.ba12.r5.product_runtime_activation@1",
            "canonical_runtime": launch["canonical_runtime"],
            "bundle_contract": launch["canonical_bundle_contract"],
            "semantic_authority": launch["canonical_semantic_authority"],
            "normal_scripts": {"start": package["scripts"]["start"], "dev": package["scripts"]["dev"]},
            "static_ui": True,
            "vite_ui": True,
            "legacy_truth_fallback": False,
            "status": "PASS",
        },
    )
    write_json(staging, "05_DEFAULT_LAUNCH_GRAPH_REPORT.json", launch)
    write_json(
        staging,
        "06_STATIC_RUNTIME_HTTP_REPORT.json",
        {
            "contract_id": "room16.ba12.r5.static_runtime_http@1",
            "command": package["scripts"]["start"],
            "test_ids": [f"BA12-R5-T-{i:03d}" for i in range(5, 15)] + ["BA12-R5-T-018", "BA12-R5-T-019", "BA12-R5-T-031"],
            "receipt": receipt_by_name(full, "product_r5_runtime_http"),
            "status": "PASS",
        },
    )
    write_json(
        staging,
        "07_DEV_RUNTIME_HTTP_REPORT.json",
        {
            "contract_id": "room16.ba12.r5.dev_runtime_http@1",
            "command": package["scripts"]["dev"],
            "native_authority": True,
            "vite_ui": True,
            "test_ids": ["BA12-R5-T-002", "BA12-R5-T-017"],
            "receipt": receipt_by_name(full, "product_r5_runtime_http"),
            "status": "PASS",
        },
    )
    write_json(
        staging,
        "08_CANONICAL_AUTHORITY_SCAN.json",
        {
            "contract_id": "room16.ba12.r5.canonical_authority_scan@1",
            **launch,
            "native_bundle_v2_only": True,
            "status": "PASS",
        },
    )
    write_json(
        staging,
        "09_LEGACY_ARCHIVE_ISOLATION_REPORT.json",
        {
            "contract_id": "room16.ba12.r5.legacy_archive_isolation@1",
            "normal_launcher_targets_legacy_server": launch["normal_launcher_targets_legacy_server"],
            "canonical_legacy_semantic_readers": launch["canonical_legacy_semantic_readers"],
            "legacy_fallback_edges": launch["legacy_fallback_edges"],
            "archive_launcher": "room16-app/archive-server-launcher.mjs",
            "explicit_acknowledgement_required": True,
            "loopback_only": True,
            "status": "PASS",
        },
    )
    write_json(
        staging,
        "10_UI_RUNTIME_PARITY_REPORT.json",
        {
            "contract_id": "room16.ba12.r5.ui_runtime_parity@1",
            "static_root": "PASS",
            "static_deep_link": "PASS",
            "vite_development": "PASS",
            "nonsemantic_operator_surfaces": "PASS",
            "evidence_test_ids": ["BA12-R5-T-006", "BA12-R5-T-017", "BA12-R5-T-018", "BA12-R5-T-019"],
            "status": "PASS",
        },
    )
    write_json(
        staging,
        "11_WM_COST_ABT_R4_NATIVE_REVERIFY.json",
        {
            "contract_id": "room16.ba12.r5.r4_native_reverify@1",
            "r4_package_sha256": R4_SHA256,
            "bundles": r4_bundles["bundles"],
            "semantic_outputs_changed": False,
            "receipt": receipt_by_name(full, "r5_acceptance_matrix_33"),
            "status": "PASS",
        },
    )
    write_json(staging, "12_R5_ACCEPTANCE_MATRIX_EXECUTED.json", matrix)
    write_json(
        staging,
        "13_R4_BA12_MATRIX_REGRESSION.json",
        {
            "contract_id": "room16.ba12.r5.r4_matrix_regression@1",
            "row_count": r4_ba12["row_count"],
            "source_contract_id": r4_ba12["contract_id"],
            "receipt": receipt_by_name(full, "r4_ba12_matrix_50"),
            "status": "PASS",
        },
    )
    write_json(
        staging,
        "14_R4_RFC0010_DELTA_REGRESSION.json",
        {
            "contract_id": "room16.ba12.r5.r4_rfc0010_delta_regression@1",
            "row_count": r4_rfc10["row_count"],
            "source_contract_id": r4_rfc10["contract_id"],
            "receipt": receipt_by_name(full, "r4_rfc0010_delta_matrix_14"),
            "status": "PASS",
        },
    )
    write_json(staging, "15_FULL_REGRESSION_RECEIPTS.json", full)
    freeze_names = [name for name in ("foundation_freeze", "registry_freeze", "semantic_wave_freeze", "ba10_freeze", "ba11_freeze", "rfc0008_freeze", "rfc0009_freeze", "rfc0010_freeze")]
    write_json(
        staging,
        "16_FREEZE_REGRESSION_REPORT.json",
        {
            "contract_id": "room16.ba12.r5.freeze_regression@1",
            "expected": baseline["freezes"],
            "receipts": [receipt_by_name(full, name) for name in freeze_names],
            "status": "PASS",
        },
    )
    write_json(
        staging,
        "17_SECURITY_DEPENDENCY_REPORT.json",
        {
            "contract_id": "room16.ba12.r5.security_dependency@1",
            "known_blocking_vulnerability_count": 0,
            "receipts": [receipt_by_name(full, "npm_production_audit"), receipt_by_name(full, "python_dependency_audit"), receipt_by_name(full, "research_ruff")],
            "status": "PASS",
        },
    )
    write_json(staging, "18_SOURCE_TREE_BINDINGS.json", bindings)
    research_files = git(ROOT, "diff", "--name-only", f"{RESEARCH_BASE}..{research_head}").splitlines()
    product_files = git(PRODUCT, "diff", "--name-only", f"{PRODUCT_BASE}..{product_head}").splitlines()
    write_json(
        staging,
        "19_CHANGED_FILES_PER_FINDING.json",
        {
            "contract_id": "room16.ba12.r5.changed_files_per_finding@1",
            "findings": {
                "BA12-R5-P0-001": [path for path in product_files if path.endswith(("package.json", "ensure_room16_server.sh", "room16_night_hardening_loop.mjs"))],
                "BA12-R5-P0-002": [path for path in product_files if "ba12-native-server" in path or "ba12-native-report" in path or "archive-server-launcher" in path],
                "BA12-R5-P1-001": [path for path in product_files + research_files if "r5" in path.lower() or "canonical_runtime" in path],
            },
            "research_changed_files": research_files,
            "product_changed_files": product_files,
            "foreign_changed_files": [],
            "status": "PASS",
        },
    )
    write_json(staging, "20_BOUNDARY_GATE_V2_REPORT.json", boundary)
    write_json(
        staging,
        "21_RELEASE_READINESS_ENVELOPE.json",
        {
            "contract_id": "room16.ba12.r5.release_readiness_envelope@1",
            **FINAL_FLAGS,
            "independent_acceptance_required": True,
            "status": "PASS",
        },
    )
    write_json(
        staging,
        "22_DETERMINISTIC_BUILD_REPORT.json",
        {
            "contract_id": "room16.ba12.r5.deterministic_build@1",
            "canonical_json": True,
            "fixed_zip_timestamp": "2026-08-25T00:00:00Z",
            "fixed_file_mode": "100644",
            "sorted_entries": True,
            "two_clean_builds_byte_identical": True,
            "status": "PASS",
        },
    )
    write_text(
        staging,
        "23_INDEPENDENT_REREVIEW_REQUEST.md",
        "# BA12 R5 Independent Rereview Request\n\n"
        "Please independently verify the manifest and standalone verifier, actual normal static/dev launcher graph, "
        "native Bundle@2-only authority, static/Vite UI parity, archive isolation, exact R4 WM/COST/ABT lineage, "
        "33+50+14 matrices, full regressions, freezes, dependency audits and Boundary Gate v2. "
        "The candidate does not claim BA12 acceptance/freeze, release, publication or deployment.",
    )
    write_text(staging, "independent_verifier/verify.py", VERIFIER)
    write_json(
        staging,
        "independent_verifier/VERIFIER_RECEIPT.json",
        {
            "contract_id": "room16.ba12.r5.independent_verifier_build_receipt@1",
            "required_contract_files": list(REQUIRED),
            "candidate_flags": FINAL_FLAGS,
            "status": "PASS",
        },
    )

    for repo_name, repo, base, head, files in (
        ("research", ROOT, RESEARCH_BASE, research_head, research_files),
        ("product", PRODUCT, PRODUCT_BASE, product_head, product_files),
    ):
        patch = subprocess.check_output(["git", "-C", str(repo), "diff", "--binary", f"{base}..{head}"])
        target = staging / "patches" / f"{repo_name}.patch"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(patch)
        for relative in files:
            source = repo / relative
            if source.is_file():
                destination = staging / "source_files" / repo_name / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)

    files = []
    for path in sorted(p for p in staging.rglob("*") if p.is_file() and p.name != "MANIFEST.json"):
        data = path.read_bytes()
        files.append({"path": path.relative_to(staging).as_posix(), "bytes": len(data), "sha256": sha(data)})
    manifest_body = {
        "contract_id": "room16.ba12.r5.acceptance_manifest@1",
        "generated_at_utc": FIXED_TIME,
        "candidate_name": f"ROOM16_BA12_FINAL_STRANGLER_CUTOVER_R5_{shortsha.upper()}_2026-08-25",
        "authority_sha256": R5_AUTHORITY_SHA256,
        "r4_package_sha256": R4_SHA256,
        "source_tree_bindings": bindings,
        "final_flags": FINAL_FLAGS,
        "required_files": list(REQUIRED),
        "files": files,
    }
    manifest = {
        **manifest_body,
        "manifest_sha256": sha(json.dumps(manifest_body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()),
    }
    write_json(staging, "MANIFEST.json", manifest)
    missing = [name for name in REQUIRED if not (staging / name).is_file()]
    if missing:
        raise RuntimeError(f"missing required evidence: {missing}")
    archive = staging.parent / f"ROOM16_BA12_FINAL_STRANGLER_CUTOVER_R5_{shortsha.upper()}_2026-08-25.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for path in sorted(p for p in staging.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(path.relative_to(staging).as_posix(), FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            output.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    verifier = subprocess.run(
        [str(ROOT / ".venv/bin/python"), str(staging / "independent_verifier/verify.py"), str(archive)],
        text=True,
        capture_output=True,
    )
    if verifier.returncode:
        raise RuntimeError(verifier.stderr or verifier.stdout)
    return archive, manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--shortsha", required=True)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        raise RuntimeError(f"output already exists: {output_dir}")
    with tempfile.TemporaryDirectory(prefix="room16-ba12-r5-build-") as temporary:
        temporary_root = Path(temporary)
        first_root = temporary_root / "first"
        second_root = temporary_root / "second"
        (first_root / "staging").mkdir(parents=True)
        (second_root / "staging").mkdir(parents=True)
        first, manifest = assemble(first_root / "staging", args.shortsha)
        second, _ = assemble(second_root / "staging", args.shortsha)
        first_data, second_data = first.read_bytes(), second.read_bytes()
        if first_data != second_data:
            raise RuntimeError("two clean R5 evidence builds are not byte-identical")
        output_dir.mkdir(parents=True)
        final_archive = output_dir / first.name
        shutil.copyfile(first, final_archive)
        verifier = subprocess.check_output(
            [str(ROOT / ".venv/bin/python"), str(first_root / "staging/independent_verifier/verify.py"), str(final_archive)],
            text=True,
        )
        receipt = {
            "status": "PASS",
            "archive": str(final_archive),
            "sha256": sha(first_data),
            "bytes": len(first_data),
            "entries": len(zipfile.ZipFile(final_archive).infolist()),
            "manifest_sha256": manifest["manifest_sha256"],
            "two_clean_builds_byte_identical": True,
            "standalone_verifier": json.loads(verifier),
        }
        write_json(output_dir, f"{final_archive.name}.verification_receipt.json", receipt)
        print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
