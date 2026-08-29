#!/usr/bin/env python3
"""Fail-closed verifier for the independently accepted Room16 BA11 freeze."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECORD = ROOT / "docs/compiler_foundation/freezes/BA11_CANARY_GOVERNANCE_FREEZE_v1.json"
DEFAULT_ACCEPTANCE = (
    ROOT / "docs/compiler_foundation/acceptance/BA11_R5_EXTERNAL_INDEPENDENT_ACCEPTANCE.json"
)
HISTORICAL_INPUT_ROOT = Path(
    os.environ.get("ROOM16_HISTORICAL_REGRESSION_INPUT_ROOT", "/Users/BjornRosinger/Downloads")
)
DEFAULT_HANDOFF = HISTORICAL_INPUT_ROOT / (
    "ROOM16_BA11_R5_INDEPENDENT_ACCEPTANCE_FREEZE_VEGA_0DD42A068BA8_2026-08-21.zip"
)


class BA11FreezeError(RuntimeError):
    """Raised when a freeze dependency cannot be verified."""


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BA11FreezeError(f"json_object_required:{path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def freeze_sha256(record: dict[str, Any]) -> str:
    body = dict(record)
    body.pop("freeze_sha256", None)
    domain = str(record["freeze_hash_domain"]).encode("utf-8")
    return hashlib.sha256(domain + b"\0" + _canonical_bytes(body)).hexdigest()


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _is_ancestor(repo: Path, ancestor: str) -> bool:
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, "HEAD"],
        cwd=repo,
        capture_output=True,
    ).returncode == 0


def _run_json(command: list[str], cwd: Path) -> dict[str, Any]:
    process = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if process.returncode != 0:
        raise BA11FreezeError(
            f"command_failed:{' '.join(command)}:{process.stdout}:{process.stderr}"
        )
    try:
        result = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise BA11FreezeError(f"command_json_invalid:{' '.join(command)}") from exc
    if not isinstance(result, dict) or result.get("status") != "PASS":
        raise BA11FreezeError(f"command_status_not_pass:{' '.join(command)}")
    return result


def _runtime_task_diff(record: dict[str, Any]) -> tuple[list[str], list[str]]:
    protection = record["runtime_protection"]
    base = protection["accepted_evidence_commit"]
    pathspec = protection["pathspec"]
    committed = _git(ROOT, "diff", "--name-only", f"{base}..HEAD", "--", pathspec)
    worktree = _git(
        ROOT, "status", "--porcelain", "--untracked-files=all", "--", pathspec
    )
    return committed.splitlines() if committed else [], worktree.splitlines() if worktree else []


def _verify_r5(record: dict[str, Any]) -> dict[str, Any]:
    source = record["source_r5"]
    return _run_json(
        [
            sys.executable,
            source["verifier_path"],
            source["package_path"],
            "--sidecar",
            source["sidecar_path"],
            "--identity",
            source["identity_path"],
        ],
        ROOT,
    )


def _verify_ba10(record: dict[str, Any], product_repo: Path) -> dict[str, Any]:
    return _run_json(
        [
            sys.executable,
            record["ba10_freeze"]["verifier_path"],
            "--product-repo",
            str(product_repo),
            "--json",
        ],
        ROOT,
    )


def verify(
    record_path: Path,
    acceptance_path: Path,
    handoff_path: Path,
    product_repo: Path,
) -> dict[str, Any]:
    record = _json(record_path)
    acceptance = _json(acceptance_path)
    checks: dict[str, bool] = {}

    checks["freeze_contract"] = (
        record.get("contract_id") == "room16.ba11.canary_governance_freeze"
        and record.get("schema_version") == 1
        and record.get("status") == "accepted_frozen"
        and record.get("authority_owner") == "research"
        and record.get("runtime_change_policy")
        == "new_rfc_and_independent_review_required"
    )
    checks["freeze_self_hash"] = record.get("freeze_sha256") == freeze_sha256(record)

    expected_acceptance = record["independent_acceptance"]
    checks["independent_acceptance_file"] = (
        _sha256(acceptance_path) == expected_acceptance["file_sha256"]
        and acceptance.get("contract_id")
        == "room16.ba11_r5.external_independent_acceptance@1"
        and acceptance.get("verdict") == "ACCEPTED"
        and acceptance.get("remaining_blocking_findings") == 0
        and acceptance.get("acceptance_receipt_sha256")
        == record["independent_acceptance_receipt_sha256"]
    )
    bindings = acceptance["git_bindings"]
    checks["acceptance_git_bindings"] = all(
        bindings.get(key) == record[key]
        for key in (
            "research_implementation_commit",
            "research_implementation_tree",
            "research_evidence_commit",
            "research_evidence_tree",
            "product_commit",
            "product_tree",
        )
    )

    checks["acceptance_handoff"] = (
        handoff_path.is_file()
        and _sha256(handoff_path) == record["acceptance_handoff"]["sha256"]
        and handoff_path.stat().st_size == record["acceptance_handoff"]["bytes"]
    )
    if checks["acceptance_handoff"]:
        with zipfile.ZipFile(handoff_path) as archive:
            checks["acceptance_handoff_zip"] = (
                archive.testzip() is None
                and len(archive.namelist()) == record["acceptance_handoff"]["zip_entries"]
            )
    else:
        checks["acceptance_handoff_zip"] = False

    source = record["source_r5"]
    source_path = ROOT / source["package_path"]
    checks["source_r5_file"] = (
        source_path.is_file()
        and _sha256(source_path) == record["source_r5_package_sha256"]
        and source_path.stat().st_size == source["bytes"]
    )
    r5_result = _verify_r5(record)
    checks["source_r5_verifier"] = (
        r5_result.get("archive_sha256") == record["source_r5_package_sha256"]
        and r5_result.get("manifest_sha256") == record["source_r5_manifest_sha256"]
        and r5_result.get("member_count") == source["zip_entries"]
        and r5_result.get("acceptance_row_count") == 18
        and r5_result.get("deterministic_rebuild") is True
    )

    research = record["research"]
    checks["research_remote_and_branch"] = (
        _git(ROOT, "remote", "get-url", "origin") == research["remote"]
        and _git(ROOT, "branch", "--show-current") == research["branch"]
    )
    checks["research_implementation_identity"] = (
        _git(ROOT, "rev-parse", f"{research['implementation_commit']}^{{tree}}")
        == research["implementation_tree"]
        and _is_ancestor(ROOT, research["implementation_commit"])
    )
    checks["research_evidence_identity"] = (
        _git(ROOT, "rev-parse", f"{research['evidence_commit']}^{{tree}}")
        == research["evidence_tree"]
        and _is_ancestor(ROOT, research["evidence_commit"])
    )

    product = record["product"]
    checks["product_remote_and_branch"] = (
        _git(product_repo, "remote", "get-url", "origin") == product["remote"]
        and _git(product_repo, "branch", "--show-current") == product["branch"]
    )
    checks["product_identity"] = (
        _git(product_repo, "rev-parse", f"{product['commit']}^{{tree}}")
        == product["tree"]
        and _is_ancestor(product_repo, product["commit"])
    )

    catalog = ROOT / record["contract_catalog"]["path"]
    checks["contract_catalog"] = (
        _sha256(catalog) == record["contract_catalog_sha256"]
        == record["contract_catalog"]["sha256"]
    )
    ba10_record = _json(ROOT / record["ba10_freeze"]["record_path"])
    ba10_result = _verify_ba10(record, product_repo)
    checks["ba10_freeze"] = (
        ba10_record.get("freeze_lock_sha256") == record["ba10_freeze_lock_sha256"]
        and ba10_result.get("freeze_lock_sha256") == record["ba10_freeze_lock_sha256"]
        and ba10_result.get("ba10_frozen") is True
    )

    committed_runtime, worktree_runtime = _runtime_task_diff(record)
    checks["ba11_runtime_unchanged_by_freeze"] = not committed_runtime and not worktree_runtime
    checks["final_status"] = (
        record.get("ba11_implementation_ready") is True
        and record.get("ba11_frozen") is True
        and record.get("ba12_authorized") is False
        and record.get("release_authorized") is False
        and record.get("publication_authorized") is False
    )

    failed = sorted(name for name, value in checks.items() if not value)
    return {
        "contract_id": "room16.ba11.canary_governance_freeze_verification",
        "schema_version": 1,
        "status": "PASS" if not failed else "FAIL",
        "freeze_sha256": record.get("freeze_sha256"),
        "checks": checks,
        "failed_checks": failed,
        "runtime_committed_diff": committed_runtime,
        "runtime_worktree_diff": worktree_runtime,
        "independent_rereview": "ACCEPTED" if not failed else "UNVERIFIED",
        "ba11_implementation_ready": not failed,
        "ba11_frozen": not failed,
        "ba12_authorized": False,
        "release_authorized": False,
        "publication_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", type=Path, default=DEFAULT_RECORD)
    parser.add_argument("--acceptance", type=Path, default=DEFAULT_ACCEPTANCE)
    parser.add_argument("--handoff", type=Path, default=DEFAULT_HANDOFF)
    parser.add_argument(
        "--product-repo", type=Path, default=ROOT.parent / "company-dossier-lab"
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = verify(
            args.record.resolve(),
            args.acceptance.resolve(),
            args.handoff.resolve(),
            args.product_repo.resolve(),
        )
    except (
        BA11FreezeError,
        KeyError,
        OSError,
        ValueError,
        zipfile.BadZipFile,
        subprocess.CalledProcessError,
    ) as exc:
        result = {
            "contract_id": "room16.ba11.canary_governance_freeze_verification",
            "schema_version": 1,
            "status": "FAIL",
            "error": str(exc),
            "ba11_implementation_ready": False,
            "ba11_frozen": False,
            "ba12_authorized": False,
            "release_authorized": False,
            "publication_authorized": False,
        }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(result["status"])
        for name, passed in result.get("checks", {}).items():
            print(f"{'PASS' if passed else 'FAIL'} {name}")
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
