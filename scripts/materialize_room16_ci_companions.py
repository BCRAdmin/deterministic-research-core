#!/usr/bin/env python3
"""Materialize exact read-only Room16 companion repositories for hermetic CI."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any


RESEARCH = {
    "branch": "main",
    "remote": "https://github.com/BCRAdmin/deterministic-research-core.git",
}
PRODUCT = {
    "bundle": "company-dossier-lab-ed86bb8.bundle",
    "commit": "ed86bb841aab88d878266cf8ed498eabc6fa9029",
    "tree": "a382d9c096825910b5e0e8865414ea232b95bd40",
    "branch": "bcr-report-lab-original-trading-flow",
    "remote": "https://github.com/BCRAdmin/company-dossier-lab.git",
}
FOREIGN = {
    "bundle": "materialbedarf-rechner-b8da17e.bundle",
    "commit": "b8da17ea731d014341da2a45ec86af65dce5291a",
    "tree": "ca79b2022dcba4a3257b9035d225cdc9df7451df",
    "branch": "codex/mbr-product-repair-v1-ba0",
    "remote": "https://github.com/BCRAdmin/materialbedarf-rechner.de.git",
}
RUNTIME_FIXTURE = {
    "file": "room16_phase_a_runtime_fixtures.zip",
    "sha256": "0a403a26b3093c801d0069d13d18d4f74f693d8a8c9fa79efe187b1fb8de9ea2",
}


def _run(command: list[str], *, cwd: Path | None = None) -> str:
    result = subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _clone(bundle_root: Path, target: Path, spec: dict[str, str]) -> dict[str, Any]:
    if target.exists():
        raise SystemExit(f"BLOCK companion target already exists: {target}")
    bundle = bundle_root / spec["bundle"]
    if not bundle.is_file():
        raise SystemExit(f"BLOCK companion bundle missing: {bundle}")
    _run(["git", "bundle", "verify", str(bundle)], cwd=bundle_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    _run(["git", "clone", "--quiet", str(bundle), str(target)])
    _run(["git", "checkout", "-B", spec["branch"], spec["commit"]], cwd=target)
    _run(["git", "remote", "set-url", "origin", spec["remote"]], cwd=target)
    observed = {
        "commit": _run(["git", "rev-parse", "HEAD"], cwd=target),
        "tree": _run(["git", "rev-parse", "HEAD^{tree}"], cwd=target),
        "branch": _run(["git", "branch", "--show-current"], cwd=target),
        "remote": _run(["git", "remote", "get-url", "origin"], cwd=target),
    }
    expected = {key: spec[key] for key in observed}
    if observed != expected:
        raise SystemExit(f"BLOCK companion identity mismatch: {target}")
    return {**observed, "path": str(target), "bundle": spec["bundle"]}


def _bind_research(repo: Path) -> dict[str, str]:
    commit = _run(["git", "rev-parse", "HEAD"], cwd=repo)
    tree = _run(["git", "rev-parse", "HEAD^{tree}"], cwd=repo)
    _run(["git", "checkout", "-B", RESEARCH["branch"], commit], cwd=repo)
    _run(["git", "remote", "set-url", "origin", RESEARCH["remote"]], cwd=repo)
    observed = {
        "commit": _run(["git", "rev-parse", "HEAD"], cwd=repo),
        "tree": _run(["git", "rev-parse", "HEAD^{tree}"], cwd=repo),
        "branch": _run(["git", "branch", "--show-current"], cwd=repo),
        "remote": _run(["git", "remote", "get-url", "origin"], cwd=repo),
    }
    if (
        observed["commit"] != commit
        or observed["tree"] != tree
        or observed["branch"] != RESEARCH["branch"]
        or observed["remote"] != RESEARCH["remote"]
    ):
        raise SystemExit("BLOCK research checkout identity mismatch")
    return observed


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _materialize_runtime_fixtures(repo: Path) -> dict[str, Any]:
    archive_path = (
        repo
        / "research_agent/tests/fixtures/hermetic_ci"
        / RUNTIME_FIXTURE["file"]
    )
    if not archive_path.is_file() or _sha256(archive_path) != RUNTIME_FIXTURE["sha256"]:
        raise SystemExit("BLOCK hermetic runtime fixture identity mismatch")

    targets = {
        "rfc0008": repo / ".runtime/rfc0008",
        "ba12": repo / "outputs/ba12",
        "alpha": repo.parent / "Alpha/RUNS",
    }
    counts = {prefix: 0 for prefix in targets}
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise SystemExit("BLOCK duplicate hermetic runtime fixture member")
        for info in archive.infolist():
            member = PurePosixPath(info.filename)
            if member.is_absolute() or ".." in member.parts or not member.parts:
                raise SystemExit(f"BLOCK unsafe hermetic runtime fixture member: {info.filename}")
            prefix = member.parts[0]
            if prefix not in targets:
                raise SystemExit(f"BLOCK unknown hermetic runtime fixture prefix: {prefix}")
            relative = Path(*member.parts[1:])
            destination = targets[prefix] / relative
            if info.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)
            counts[prefix] += 1
    return {
        "archive": str(archive_path),
        "archive_sha256": RUNTIME_FIXTURE["sha256"],
        "materialized_file_counts": counts,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    bundle_root = repo / "research_agent/tests/fixtures/git_identities"
    product_target = repo.parent / "company-dossier-lab"
    foreign_target = repo.parent.parent / "Utility-Websites/materialbedarf-rechner.de"

    research = _bind_research(repo)
    product = _clone(bundle_root, product_target, PRODUCT)
    foreign = _clone(bundle_root, foreign_target, FOREIGN)
    release_source = repo / "research_agent/tests/fixtures/cross_company_release_current"
    release_target = product_target / ".runtime/cross-company-release-current"
    shutil.copytree(release_source, release_target)
    runtime_fixtures = _materialize_runtime_fixtures(repo)
    print(
        json.dumps(
            {
                "contract_id": "room16.r16.hermetic_ci_companions@1",
                "status": "PASS",
                "research": research,
                "product": product,
                "foreign": foreign,
                "cross_company_release": str(release_target),
                "runtime_fixtures": runtime_fixtures,
                "git_optional_locks_required": True,
                "companion_scope": "read_only_by_contract_without_permission_mutation",
                "production_private_key_materialized": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
