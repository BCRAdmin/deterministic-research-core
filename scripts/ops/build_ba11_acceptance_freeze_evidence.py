#!/usr/bin/env python3
"""Build deterministic evidence for the accepted and frozen Room16 BA11 state."""

from __future__ import annotations

import argparse
import json
import subprocess
import zipfile
from pathlib import Path
from typing import Any

from build_ba11_r5_evidence import (
    foreign_boundary,
    git,
    json_bytes,
    run_product_full,
    run_receipt,
    sha256_bytes,
    tree_binding,
)
from research_agent.canary_governance.archive import (
    build_deterministic_zip,
    build_package_identity,
)


ROOT = Path(__file__).resolve().parents[2]
ACCEPTED_BASE = "a7f83418c1473ef575467472b66934e4ff026dc8"
PRODUCT_IDENTITY = "fafcdbd3586075b5f4d0b50b3b18c22fb7a2e9e2"
HANDOFF_NAME = (
    "ROOM16_BA11_R5_INDEPENDENT_ACCEPTANCE_FREEZE_VEGA_"
    "0DD42A068BA8_2026-08-21.zip"
)
HANDOFF_SHA256 = "0dd42a068ba8be1eac0e938fdadc4fc7434c2dbaeeaa9176fef89f939654b267"
SOURCE_DATE_EPOCH = 1787270400
FREEZE_RECORD = "docs/compiler_foundation/freezes/BA11_CANARY_GOVERNANCE_FREEZE_v1.json"
ACCEPTANCE_RECORD = (
    "docs/compiler_foundation/acceptance/BA11_R5_EXTERNAL_INDEPENDENT_ACCEPTANCE.json"
)


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _collection_count(stdout: str) -> int:
    payload = next(
        json.loads(line)
        for line in reversed(stdout.splitlines())
        if line.startswith('{"contract_id": "room16.pytest_collection_manifest_source@1"')
    )
    if payload.get("pytest_exit_code") != 0:
        raise SystemExit("STOP pytest collection failed")
    return len(payload["nodeids"])


def _changed_files(base: str) -> list[dict[str, Any]]:
    names = git(ROOT, "diff", "--name-only", f"{base}..HEAD").splitlines()
    rows = []
    for name in names:
        path = ROOT / name
        if not path.is_file() or name.startswith("outputs/release/"):
            continue
        rows.append(
            {
                "repo": "research",
                "path": name,
                "bytes": path.stat().st_size,
                "sha256": sha256_bytes(path.read_bytes()),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--product-repo", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    handoff = args.handoff.resolve()
    product_repo = args.product_repo.resolve()

    if handoff.name != HANDOFF_NAME or sha256_bytes(handoff.read_bytes()) != HANDOFF_SHA256:
        raise SystemExit("STOP acceptance/freeze handoff identity mismatch")
    if git(ROOT, "status", "--porcelain") or git(product_repo, "status", "--porcelain"):
        raise SystemExit("STOP both authorized worktrees must be clean")
    research_binding = tree_binding(ROOT)
    product_binding = tree_binding(product_repo)
    if research_binding["origin"] != "https://github.com/BCRAdmin/deterministic-research-core.git":
        raise SystemExit("STOP Research origin mismatch")
    if product_binding["origin"] != "https://github.com/BCRAdmin/company-dossier-lab.git":
        raise SystemExit("STOP Product origin mismatch")
    if product_binding["head"] != PRODUCT_IDENTITY:
        raise SystemExit("STOP Product identity mismatch")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", ACCEPTED_BASE, "HEAD"], cwd=ROOT
    ).returncode:
        raise SystemExit("STOP accepted R5 evidence is not an ancestor")

    with zipfile.ZipFile(handoff) as archive:
        if archive.testzip() or len(archive.namelist()) != 11:
            raise SystemExit("STOP acceptance/freeze handoff ZIP mismatch")
        external_acceptance = archive.read("01_EXTERNAL_INDEPENDENT_ACCEPTANCE.json")
        status_transition = archive.read("03_STATUS_TRANSITION.json")
        next_phase = archive.read("07_NEXT_PHASE_BOUNDARY.md")
    if external_acceptance != (ROOT / ACCEPTANCE_RECORD).read_bytes():
        raise SystemExit("STOP canonical acceptance is not byte-identical")

    foreign_before = foreign_boundary()
    r5_test = "research_agent/tests/test_canary_governance_r5.py"
    r4_test = "research_agent/tests/test_canary_governance_r4.py"
    app_root = product_repo / "room16-app"
    receipts = [
        run_receipt(
            "freeze_verifier",
            [
                ".venv/bin/python",
                "scripts/ops/verify_ba11_canary_governance_freeze.py",
                "--product-repo",
                str(product_repo),
                "--handoff",
                str(handoff),
                "--json",
            ],
            ROOT,
            research_binding,
            product_repo,
        ),
        run_receipt(
            "freeze_tests",
            [
                ".venv/bin/python",
                "-m",
                "pytest",
                "-q",
                "research_agent/tests/test_ba11_canary_governance_freeze.py",
            ],
            ROOT,
            research_binding,
            product_repo,
        ),
        run_receipt(
            "r5_collect",
            [".venv/bin/python", "scripts/ops/collect_pytest_nodeids.py", r5_test],
            ROOT,
            research_binding,
            product_repo,
        ),
        run_receipt(
            "r5_targeted",
            [".venv/bin/python", "-m", "pytest", "-q", r5_test],
            ROOT,
            research_binding,
            product_repo,
        ),
        run_receipt(
            "r4_collect",
            [".venv/bin/python", "scripts/ops/collect_pytest_nodeids.py", r4_test],
            ROOT,
            research_binding,
            product_repo,
        ),
        run_receipt(
            "r4_targeted",
            [".venv/bin/python", "-m", "pytest", "-q", r4_test],
            ROOT,
            research_binding,
            product_repo,
        ),
        run_receipt(
            "research_full",
            [".venv/bin/python", "-m", "pytest", "-q"],
            ROOT,
            research_binding,
            product_repo,
        ),
        run_receipt(
            "research_ruff",
            [".venv/bin/ruff", "check", "."],
            ROOT,
            research_binding,
            product_repo,
        ),
        run_receipt(
            "ba10_freeze",
            [
                ".venv/bin/python",
                "scripts/ops/verify_ba10_artifact_abi_renderer_freeze.py",
                "--product-repo",
                str(product_repo),
                "--json",
            ],
            ROOT,
            research_binding,
            product_repo,
        ),
        run_receipt(
            "product_pytest",
            [".venv/bin/python", "-m", "pytest", "-q"],
            product_repo,
            product_binding,
            product_repo,
            env={"PYTHONPATH": "."},
        ),
        run_receipt(
            "product_hardening",
            [
                "node",
                "scripts/room16_night_hardening_loop.mjs",
                "--cycles",
                "1",
                "--interval-ms",
                "0",
                "--retain-cycles",
                "20",
                "--no-screenshots",
            ],
            app_root,
            product_binding,
            product_repo,
        ),
    ]
    receipts.append(run_product_full(app_root, product_binding, product_repo))
    if any(row["exit_code"] for row in receipts):
        raise SystemExit(
            f"STOP failed receipts: {[row['receipt_id'] for row in receipts if row['exit_code']]}"
        )
    by_id = {row["receipt_id"]: row for row in receipts}
    r5_count = _collection_count(by_id["r5_collect"]["raw_stdout"])
    r4_count = _collection_count(by_id["r4_collect"]["raw_stdout"])
    if r5_count != 18 or r4_count != 54:
        raise SystemExit(f"STOP exact test count mismatch: R5={r5_count}, R4={r4_count}")

    freeze_result = json.loads(by_id["freeze_verifier"]["raw_stdout"])
    ba10_result = json.loads(by_id["ba10_freeze"]["raw_stdout"])
    if freeze_result.get("status") != "PASS" or ba10_result.get("status") != "PASS":
        raise SystemExit("STOP freeze verification result mismatch")

    changed = _changed_files(ACCEPTED_BASE)
    runtime_changes = [
        row for row in changed if row["path"].startswith("research_agent/canary_governance/")
    ]
    if runtime_changes:
        raise SystemExit("STOP acceptance/freeze task changed BA11 runtime")
    foreign_after = foreign_boundary()
    if foreign_before != foreign_after:
        raise SystemExit("STOP foreign worktree changed during Room16 verification")

    r5_acceptance = _json(ROOT / ACCEPTANCE_RECORD)
    freeze_record = _json(ROOT / FREEZE_RECORD)
    members: dict[str, bytes] = {
        "00_BA11_ACCEPTANCE_VERDICT.md": (
            "# BA11 Independent Acceptance and Freeze Verdict\n\n"
            "Independent R5 rereview: `ACCEPTED`. BA11 implementation-ready and frozen: "
            "`true`. BA12, release, publication, deploy, and runtime changes remain "
            "unauthorized.\n"
        ).encode(),
        "01_EXTERNAL_INDEPENDENT_ACCEPTANCE.json": external_acceptance,
        "02_BA11_FREEZE_RECORD.json": json_bytes(freeze_record),
        "03_STATUS_TRANSITION.json": status_transition,
        "04_FREEZE_VERIFIER_RECEIPT.json": json_bytes(freeze_result),
        "05_R5_PACKAGE_BINDING.json": json_bytes(
            {
                "status": "PASS",
                "source_r5": r5_acceptance["source_r5"],
                "acceptance_receipt_sha256": r5_acceptance["acceptance_receipt_sha256"],
                "research_implementation_commit": freeze_record[
                    "research_implementation_commit"
                ],
                "research_evidence_commit": freeze_record["research_evidence_commit"],
            }
        ),
        "06_BA10_FREEZE_RECEIPT.json": json_bytes(
            {"command_receipt": by_id["ba10_freeze"], "parsed_result": ba10_result}
        ),
        "07_FINAL_REGRESSION_RECEIPTS.json": json_bytes(
            {
                "status": "PASS",
                "r5_exact_test_count": r5_count,
                "r4_exact_test_count": r4_count,
                "receipts": receipts,
            }
        ),
        "08_SOURCE_TREE_BINDINGS.json": json_bytes(
            {
                "research": research_binding,
                "product": product_binding,
                "accepted_r5_evidence_commit": ACCEPTED_BASE,
            }
        ),
        "09_CHANGED_FILES.json": json_bytes(
            {
                "task_base": ACCEPTED_BASE,
                "files": changed,
                "ba11_runtime_files_changed": [],
                "product_files_changed": [],
            }
        ),
        "10_FOREIGN_WORKTREE_BOUNDARY_REPORT.json": json_bytes(
            {
                **foreign_after,
                "preflight_sha256": sha256_bytes(json_bytes(foreign_before)),
                "postflight_sha256": sha256_bytes(json_bytes(foreign_after)),
                "unchanged": True,
            }
        ),
        "11_NEXT_PHASE_GATE.md": next_phase
        + b"\nFinal freeze result: BA11 accepted/frozen; BA12 remains operator-gated.\n",
    }
    first_zip, first_manifest = build_deterministic_zip(
        members, source_date_epoch=SOURCE_DATE_EPOCH
    )
    second_zip, second_manifest = build_deterministic_zip(
        members, source_date_epoch=SOURCE_DATE_EPOCH
    )
    if first_zip != second_zip or first_manifest != second_manifest:
        raise SystemExit("STOP deterministic evidence assemblies differ")

    filename = (
        f"ROOM16_BA11_INDEPENDENT_ACCEPTANCE_FREEZE_"
        f"{research_binding['head'][:12].upper()}_2026-08-21.zip"
    )
    identity, sidecar = build_package_identity(
        first_zip,
        package_filename=filename,
        manifest_sha256=first_manifest["manifest_sha256"],
    )
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    stage = output / filename.removesuffix(".zip")
    stage.mkdir(parents=True, exist_ok=True)
    for name, value in {**members, "MANIFEST.json": json_bytes(first_manifest)}.items():
        path = stage / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    (output / filename).write_bytes(first_zip)
    (output / f"{filename}.sha256").write_bytes(sidecar)
    (output / f"{filename}.identity.json").write_bytes(
        json_bytes(identity.model_dump(mode="json"))
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "package": str(output / filename),
                "package_bytes": len(first_zip),
                "package_sha256": identity.package_sha256,
                "manifest_sha256": first_manifest["manifest_sha256"],
                "member_count": len(members) + 1,
                "r5_exact_tests": r5_count,
                "r4_exact_tests": r4_count,
                "ba11_runtime_files_changed": 0,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
