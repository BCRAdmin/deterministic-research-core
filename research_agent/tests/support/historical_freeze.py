"""Run accepted Room16 freezes in isolated, identity-exact Git checkouts."""

from __future__ import annotations

import functools
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
RESEARCH_BASE_COMMIT = "113a7d6e80266657562a9066d9446838cf9dc224"
RESEARCH_REMOTE = "https://github.com/BCRAdmin/deterministic-research-core.git"
PRODUCT_COMMIT = "ed86bb841aab88d878266cf8ed498eabc6fa9029"
PRODUCT_BRANCH = "bcr-report-lab-original-trading-flow"
PRODUCT_REMOTE = "https://github.com/BCRAdmin/company-dossier-lab.git"
PRODUCT_BUNDLE = (
    ROOT
    / "research_agent/tests/fixtures/git_identities/company-dossier-lab-ed86bb8.bundle"
)
HISTORICAL_AUTHORITIES = ROOT / "research_agent/tests/fixtures/historical_authorities"
CROSS_COMPANY_RELEASE = (
    ROOT / "research_agent/tests/fixtures/cross_company_release_current"
)


def _run(command: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)


@functools.lru_cache(maxsize=1)
def verify_historical_ba12_freeze() -> dict[str, Any]:
    """Verify BA12 at its accepted identities, never against successor worktree edits."""

    with tempfile.TemporaryDirectory(prefix="room16-r16-historical-freeze-") as temporary:
        root = Path(temporary)
        research = root / "research-agent-ops"
        product = root / "company-dossier-lab"
        _run(["git", "clone", "--shared", "--quiet", str(ROOT), str(research)])
        _run(
            [
                "git",
                "fetch",
                "--quiet",
                "--force",
                str(ROOT),
                "refs/tags/*:refs/tags/*",
            ],
            cwd=research,
        )
        _run(["git", "checkout", "-B", "main", RESEARCH_BASE_COMMIT], cwd=research)
        _run(["git", "remote", "set-url", "origin", RESEARCH_REMOTE], cwd=research)
        _run(["git", "clone", "--quiet", str(PRODUCT_BUNDLE), str(product)])
        _run(["git", "checkout", "-B", PRODUCT_BRANCH, PRODUCT_COMMIT], cwd=product)
        _run(["git", "remote", "set-url", "origin", PRODUCT_REMOTE], cwd=product)
        shutil.copytree(
            CROSS_COMPANY_RELEASE,
            product / ".runtime/cross-company-release-current",
        )
        environment = os.environ.copy()
        environment["ROOM16_HISTORICAL_REGRESSION_INPUT_ROOT"] = str(
            HISTORICAL_AUTHORITIES
        )
        result = subprocess.run(
            [
                sys.executable,
                "scripts/ops/verify_ba12_whole_system_freeze.py",
                "--product-repo",
                str(product),
                "--json",
            ],
            cwd=research,
            env=environment,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise AssertionError(result.stdout or result.stderr)
        payload = json.loads(result.stdout)
        if payload.get("status") != "PASS":
            raise AssertionError(result.stdout)
        return payload
