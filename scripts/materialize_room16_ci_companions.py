#!/usr/bin/env python3
"""Materialize exact read-only Room16 companion repositories for hermetic CI."""

from __future__ import annotations

import argparse
import json
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Any


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


def _make_read_only(root: Path) -> None:
    for path in [root, *root.rglob("*")]:
        if path.is_symlink():
            continue
        mode = path.stat().st_mode
        path.chmod(mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    bundle_root = repo / "research_agent/tests/fixtures/git_identities"
    product_target = repo.parent / "company-dossier-lab"
    foreign_target = repo.parent.parent / "Utility-Websites/materialbedarf-rechner.de"

    product = _clone(bundle_root, product_target, PRODUCT)
    foreign = _clone(bundle_root, foreign_target, FOREIGN)
    release_source = repo / "research_agent/tests/fixtures/cross_company_release_current"
    release_target = product_target / ".runtime/cross-company-release-current"
    shutil.copytree(release_source, release_target)
    _make_read_only(product_target)
    _make_read_only(foreign_target)
    print(
        json.dumps(
            {
                "contract_id": "room16.r16.hermetic_ci_companions@1",
                "status": "PASS",
                "product": product,
                "foreign": foreign,
                "cross_company_release": str(release_target),
                "git_optional_locks_required": True,
                "production_private_key_materialized": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
