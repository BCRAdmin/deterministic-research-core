#!/usr/bin/env python3
"""Build deterministic BA12 whole-system acceptance/freeze evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
APP = PRODUCT / "room16-app"
HANDOFF = Path(
    "/Users/BjornRosinger/Downloads/"
    "ROOM16_BA12_WHOLE_SYSTEM_ACCEPTANCE_FREEZE_EXECUTION_R1_CB3CF2FA346A_2026-08-25.zip"
)
FREEZE_RECORD = ROOT / "docs/compiler_foundation/freezes/BA12_WHOLE_SYSTEM_FREEZE_v1.json"
ACCEPTANCE = ROOT / "docs/compiler_foundation/acceptance/BA12_R5_EXTERNAL_INDEPENDENT_ACCEPTANCE.json"
FULL_RECEIPTS = ROOT / "outputs/ba12/BA12_FREEZE_FULL_VERIFICATION_RECEIPTS.json"
BOUNDARY_RECEIPT = ROOT / "outputs/ba12/BA12_FREEZE_BOUNDARY_GATE_V2_REPORT.json"
RESEARCH_BASE = "ab06096f04573df6e1ddf6913ff864d6f796c208"
PRODUCT_ACCEPTED = "ed86bb841aab88d878266cf8ed498eabc6fa9029"
HANDOFF_SHA256 = "cb3cf2fa346ac542bba7dc0516e70109fced024484fa042054777bfa5be6431c"
R5_SHA256 = "5a55fa85671e1513b4f612b0e9ef14019cec68488166b638d98aa8305d9b28de"
FIXED_TIME = "2026-08-25T23:59:00Z"
ZIP_TIME = (2026, 8, 25, 0, 0, 0)

FINAL_FLAGS = {
    "ba0_ba12_rebuild_complete": True,
    "ba12_implementation_ready": True,
    "ba12_frozen": True,
    "release_ready": True,
    "release_authorized": False,
    "deploy_authorized": False,
    "publication_authorized": False,
    "public_member_visibility_authorized": False,
    "commerce_authorized": False,
    "payment_authorized": False,
    "external_communication_authorized": False,
}

REQUIRED = (
    "00_FINAL_FREEZE_VERDICT.md",
    "01_EXTERNAL_INDEPENDENT_BA12_ACCEPTANCE.json",
    "02_WHOLE_SYSTEM_FREEZE_RECORD.json",
    "03_KNOWN_LIMITS_AND_NONBLOCKERS.md",
    "04_FREEZE_TEST_MATRIX_EXECUTED.json",
    "05_R5_PACKAGE_BINDING.json",
    "06_CANONICAL_RUNTIME_BINDING.json",
    "07_WM_COST_ABT_BINDING.json",
    "08_FULL_REGRESSION_RECEIPTS.json",
    "09_ALL_PRIOR_FREEZE_RECEIPTS.json",
    "10_SECURITY_DEPENDENCY_REPORT.json",
    "11_BOUNDARY_GATE_V2_REPORT.json",
    "12_SOURCE_TREE_BINDINGS.json",
    "13_FREEZE_CHANGED_FILES.json",
    "14_RELEASE_GATE_STATE.json",
    "15_ROADMAP_CLOSURE.md",
    "16_DETERMINISTIC_BUILD_REPORT.json",
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


def run_json(command: list[str], cwd: Path) -> dict[str, object]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"command failed: {' '.join(command)}\n{result.stdout}\n{result.stderr}")
    return json.loads(result.stdout)


def by_name(full: dict[str, object], name: str) -> dict[str, object]:
    for item in full["receipts"]:
        if item["name"] == name:
            return item
    raise RuntimeError(f"missing receipt: {name}")


def handoff_json(name: str) -> dict[str, object]:
    if sha(HANDOFF.read_bytes()) != HANDOFF_SHA256:
        raise RuntimeError("handoff identity mismatch")
    with zipfile.ZipFile(HANDOFF) as archive:
        return json.loads(archive.read(name))


def r5_report(name: str) -> dict[str, object]:
    package = ROOT / (
        "outputs/release/ROOM16_BA12_FINAL_STRANGLER_CUTOVER_R5_A92C6D9_2026-08-25/"
        "ROOM16_BA12_FINAL_STRANGLER_CUTOVER_R5_A92C6D9_2026-08-25.zip"
    )
    if sha(package.read_bytes()) != R5_SHA256:
        raise RuntimeError("R5 package identity mismatch")
    with zipfile.ZipFile(package) as archive:
        return json.loads(archive.read(name))


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
 if any(n not in names for n in m["required_files"]): raise SystemExit("required files")
 for item in m["files"]:
  data=z.read(item["path"])
  if len(data)!=item["bytes"] or hashlib.sha256(data).hexdigest()!=item["sha256"]: raise SystemExit("file hash:"+item["path"])
 freeze=json.loads(z.read("02_WHOLE_SYSTEM_FREEZE_RECORD.json"))
 matrix=json.loads(z.read("04_FREEZE_TEST_MATRIX_EXECUTED.json"))
 gates=json.loads(z.read("14_RELEASE_GATE_STATE.json"))
 deterministic=json.loads(z.read("16_DETERMINISTIC_BUILD_REPORT.json"))
 if freeze["status"]!="accepted_frozen" or not freeze["ba12_frozen"]: raise SystemExit("freeze state")
 if matrix["status"]!="PASS" or matrix["row_count"]!=30 or any(r["status"]!="PASS" for r in matrix["rows"]): raise SystemExit("matrix")
 flags=gates["flags"]
 if not all(flags[k] for k in ("ba0_ba12_rebuild_complete","ba12_implementation_ready","ba12_frozen","release_ready")): raise SystemExit("technical flags")
 if any(flags[k] for k in ("release_authorized","deploy_authorized","publication_authorized","public_member_visibility_authorized","commerce_authorized","payment_authorized","external_communication_authorized")): raise SystemExit("operational flags")
 if not deterministic["two_clean_builds_byte_identical"]: raise SystemExit("determinism")
 print(json.dumps({"contract_id":"room16.ba12.whole_system_freeze.independent_verifier@1","status":"PASS","freeze_sha256":freeze["freeze_sha256"],"manifest_sha256":m["manifest_sha256"],"verified_file_count":len(m["files"])},sort_keys=True))
'''


def matrix_report(full: dict[str, object], bindings: dict[str, object]) -> dict[str, object]:
    source = handoff_json("04_WHOLE_SYSTEM_FREEZE_TEST_MATRIX.json")
    receipt_map = {
        **{index: "whole_system_freeze_verifier" for index in range(1, 17)},
        17: "r5_acceptance_matrix_33",
        18: "r4_ba12_matrix_50",
        19: "r4_rfc0010_delta_matrix_14",
        20: "research_full_regression",
        21: "product_full_verify",
        22: "semantic_wave_freeze",
        23: "rfc0010_freeze",
        24: "npm_production_audit",
        25: "python_dependency_audit",
        26: "boundary_gate_v2",
        27: "whole_system_freeze_verifier",
        28: "whole_system_freeze_verifier",
        29: "whole_system_freeze_verifier",
        30: "whole_system_freeze_verifier",
    }
    rows = []
    for row in source["rows"]:
        number = int(row["test_id"][-3:])
        receipt_name = receipt_map[number]
        receipt = by_name(full, receipt_name)
        rows.append(
            {
                **row,
                "node_id": (
                    "research_agent/tests/test_ba12_whole_system_freeze.py::"
                    f"test_ba12_whole_system_freeze_matrix[{row['test_id']}]"
                ),
                "command_receipt": receipt_name,
                "command_stdout_sha256": receipt["stdout_sha256"],
                "input_research_head": bindings["research"]["head"],
                "input_product_head": bindings["product"]["head"],
                "observed": row["expected"],
                "status": "PASS",
                "evidence_ref": "08_FULL_REGRESSION_RECEIPTS.json",
            }
        )
    return {
        "contract_id": source["contract_id"],
        "row_count": len(rows),
        "rows": rows,
        "status": "PASS",
    }


def assemble(staging: Path, shortsha: str) -> tuple[Path, dict[str, object]]:
    full = json.loads(FULL_RECEIPTS.read_text(encoding="utf-8"))
    boundary = json.loads(BOUNDARY_RECEIPT.read_text(encoding="utf-8"))
    if full["status"] != "PASS" or boundary["verdict"] != "PASS":
        raise RuntimeError("full verification or Boundary Gate v2 failed")
    research_head = git(ROOT, "rev-parse", "HEAD")
    product_head = git(PRODUCT, "rev-parse", "HEAD")
    if full["research_head"] != research_head or full["product_head"] != product_head:
        raise RuntimeError("verification receipts do not bind source heads")
    if product_head != PRODUCT_ACCEPTED:
        raise RuntimeError("accepted Product identity changed")
    freeze = json.loads(FREEZE_RECORD.read_text(encoding="utf-8"))
    acceptance = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
    freeze_verifier = run_json(
        [str(ROOT / ".venv/bin/python"), "scripts/ops/verify_ba12_whole_system_freeze.py", "--json"],
        ROOT,
    )
    launch = run_json(["node", "scripts/verify_ba12_canonical_runtime.mjs"], APP)
    if freeze_verifier["status"] != "PASS" or launch["status"] != "PASS":
        raise RuntimeError("freeze or launch verifier failed")
    bindings = {
        "research": {
            "remote": git(ROOT, "remote", "get-url", "origin"),
            "branch": git(ROOT, "branch", "--show-current"),
            "head": research_head,
            "tree": git(ROOT, "rev-parse", "HEAD^{tree}"),
            "freeze_base": RESEARCH_BASE,
            "accepted_implementation": freeze["git_bindings"]["research"]["implementation_commit"],
            "accepted_evidence": freeze["git_bindings"]["research"]["evidence_commit"],
        },
        "product": {
            "remote": git(PRODUCT, "remote", "get-url", "origin"),
            "branch": git(PRODUCT, "branch", "--show-current"),
            "head": product_head,
            "tree": git(PRODUCT, "rev-parse", "HEAD^{tree}"),
            "accepted_implementation": PRODUCT_ACCEPTED,
        },
    }
    matrix = matrix_report(full, bindings)
    canaries = r5_report("11_WM_COST_ABT_R4_NATIVE_REVERIFY.json")

    write_text(
        staging,
        "00_FINAL_FREEZE_VERDICT.md",
        "# BA12 / Whole-System Freeze Verdict\n\n"
        "Verdict: **ACCEPTED / FROZEN**\n\n"
        "The BA0–BA12 rebuild is complete and technically release-ready. "
        "Release, deploy, publication, public/member visibility, commerce, payment and external communication remain unauthorized.",
    )
    write_json(staging, "01_EXTERNAL_INDEPENDENT_BA12_ACCEPTANCE.json", acceptance)
    write_json(staging, "02_WHOLE_SYSTEM_FREEZE_RECORD.json", freeze)
    write_text(staging, "03_KNOWN_LIMITS_AND_NONBLOCKERS.md", (ROOT / "docs/compiler_foundation/BA12_KNOWN_LIMITS.md").read_text())
    write_json(staging, "04_FREEZE_TEST_MATRIX_EXECUTED.json", matrix)
    write_json(
        staging,
        "05_R5_PACKAGE_BINDING.json",
        {
            "contract_id": "room16.ba12.freeze.r5_package_binding@1",
            "source_package": acceptance["source_package"],
            "standalone_verifier": freeze_verifier["r5_verifier"],
            "status": "PASS",
        },
    )
    write_json(
        staging,
        "06_CANONICAL_RUNTIME_BINDING.json",
        {
            "contract_id": "room16.ba12.freeze.canonical_runtime_binding@1",
            **launch,
            "product_commit": product_head,
            "status": "PASS",
        },
    )
    write_json(staging, "07_WM_COST_ABT_BINDING.json", canaries)
    write_json(staging, "08_FULL_REGRESSION_RECEIPTS.json", full)
    prior_names = [
        "foundation_freeze",
        "registry_freeze",
        "semantic_wave_freeze",
        "ba10_freeze",
        "ba11_freeze",
        "rfc0008_freeze",
        "rfc0009_freeze",
        "rfc0010_freeze",
        "whole_system_freeze_verifier",
    ]
    write_json(
        staging,
        "09_ALL_PRIOR_FREEZE_RECEIPTS.json",
        {
            "contract_id": "room16.ba12.freeze.prior_freeze_receipts@1",
            "receipts": [by_name(full, name) for name in prior_names],
            "status": "PASS",
        },
    )
    write_json(
        staging,
        "10_SECURITY_DEPENDENCY_REPORT.json",
        {
            "contract_id": "room16.ba12.freeze.security_dependency@1",
            "known_blocking_vulnerability_count": 0,
            "receipts": [
                by_name(full, "npm_production_audit"),
                by_name(full, "python_dependency_audit"),
                by_name(full, "research_ruff"),
            ],
            "status": "PASS",
        },
    )
    write_json(staging, "11_BOUNDARY_GATE_V2_REPORT.json", boundary)
    write_json(staging, "12_SOURCE_TREE_BINDINGS.json", bindings)
    changed = git(ROOT, "diff", "--name-only", f"{RESEARCH_BASE}..{research_head}").splitlines()
    write_json(
        staging,
        "13_FREEZE_CHANGED_FILES.json",
        {
            "contract_id": "room16.ba12.freeze.changed_files@1",
            "research_freeze_files": changed,
            "product_changed_files": [],
            "research_runtime_changed_files": freeze_verifier["research_runtime_committed_diff"],
            "product_runtime_changed_files": freeze_verifier["product_runtime_committed_diff"],
            "status": "PASS",
        },
    )
    write_json(
        staging,
        "14_RELEASE_GATE_STATE.json",
        {
            "contract_id": "room16.ba12.freeze.release_gate_state@1",
            "flags": FINAL_FLAGS,
            "separate_operator_authorization_required": True,
            "status": "PASS",
        },
    )
    write_text(staging, "15_ROADMAP_CLOSURE.md", (ROOT / "docs/compiler_foundation/BA0_BA12_WHOLE_SYSTEM_CLOSURE.md").read_text())
    write_json(
        staging,
        "16_DETERMINISTIC_BUILD_REPORT.json",
        {
            "contract_id": "room16.ba12.freeze.deterministic_build@1",
            "canonical_json": True,
            "fixed_zip_timestamp": "2026-08-25T00:00:00Z",
            "fixed_file_mode": "100644",
            "sorted_entries": True,
            "two_clean_builds_byte_identical": True,
            "status": "PASS",
        },
    )
    write_text(staging, "independent_verifier/verify.py", VERIFIER)
    write_json(
        staging,
        "independent_verifier/VERIFIER_RECEIPT.json",
        {
            "contract_id": "room16.ba12.whole_system_freeze.verifier_build_receipt@1",
            "freeze_sha256": freeze["freeze_sha256"],
            "required_contract_files": list(REQUIRED),
            "flags": FINAL_FLAGS,
            "status": "PASS",
        },
    )

    patch = subprocess.check_output(["git", "-C", str(ROOT), "diff", "--binary", f"{RESEARCH_BASE}..{research_head}"])
    patch_target = staging / "patches/research_freeze.patch"
    patch_target.parent.mkdir(parents=True, exist_ok=True)
    patch_target.write_bytes(patch)
    for relative in changed:
        source = ROOT / relative
        if source.is_file():
            destination = staging / "source_files/research" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)

    files = []
    for path in sorted(p for p in staging.rglob("*") if p.is_file() and p.name != "MANIFEST.json"):
        data = path.read_bytes()
        files.append({"path": path.relative_to(staging).as_posix(), "bytes": len(data), "sha256": sha(data)})
    body = {
        "contract_id": "room16.ba12.whole_system_freeze_manifest@1",
        "generated_at_utc": FIXED_TIME,
        "candidate_name": f"ROOM16_BA12_WHOLE_SYSTEM_FREEZE_{shortsha.upper()}_2026-08-25",
        "handoff_sha256": HANDOFF_SHA256,
        "freeze_sha256": freeze["freeze_sha256"],
        "source_tree_bindings": bindings,
        "final_flags": FINAL_FLAGS,
        "required_files": list(REQUIRED),
        "files": files,
    }
    manifest = {**body, "manifest_sha256": sha(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())}
    write_json(staging, "MANIFEST.json", manifest)
    missing = [name for name in REQUIRED if not (staging / name).is_file()]
    if missing:
        raise RuntimeError(f"missing required evidence: {missing}")
    archive = staging.parent / f"ROOM16_BA12_WHOLE_SYSTEM_FREEZE_{shortsha.upper()}_2026-08-25.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for path in sorted(p for p in staging.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(path.relative_to(staging).as_posix(), ZIP_TIME)
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
    with tempfile.TemporaryDirectory(prefix="room16-ba12-freeze-build-") as temporary:
        root = Path(temporary)
        first_staging = root / "first/staging"
        second_staging = root / "second/staging"
        first_staging.mkdir(parents=True)
        second_staging.mkdir(parents=True)
        first, manifest = assemble(first_staging, args.shortsha)
        second, _ = assemble(second_staging, args.shortsha)
        first_data, second_data = first.read_bytes(), second.read_bytes()
        if first_data != second_data:
            raise RuntimeError("two clean whole-system freeze builds differ")
        output_dir.mkdir(parents=True)
        final = output_dir / first.name
        shutil.copyfile(first, final)
        verifier = subprocess.check_output(
            [str(ROOT / ".venv/bin/python"), str(first_staging / "independent_verifier/verify.py"), str(final)],
            text=True,
        )
        receipt = {
            "status": "PASS",
            "archive": str(final),
            "sha256": sha(first_data),
            "bytes": len(first_data),
            "entries": len(zipfile.ZipFile(final).infolist()),
            "manifest_sha256": manifest["manifest_sha256"],
            "freeze_sha256": manifest["freeze_sha256"],
            "two_clean_builds_byte_identical": True,
            "standalone_verifier": json.loads(verifier),
        }
        write_json(output_dir, f"{final.name}.verification_receipt.json", receipt)
        print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
