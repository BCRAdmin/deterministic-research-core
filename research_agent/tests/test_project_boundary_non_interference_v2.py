from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.ops.verify_project_boundary_non_interference_v2 import (
    BoundaryGateV2Error,
    build_receipt,
    foreign_snapshot,
)


def _repo(path: Path, origin: str) -> Path:
    path.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "remote", "add", "origin", origin], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "boundary@example.invalid"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Boundary Test"], cwd=path, check=True)
    (path / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "seed.txt"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=path, check=True)
    return path


@pytest.fixture()
def repos(tmp_path: Path) -> tuple[Path, Path, Path]:
    research = _repo(
        tmp_path / "research",
        "https://github.com/BCRAdmin/deterministic-research-core.git",
    )
    product = _repo(
        tmp_path / "product",
        "https://github.com/BCRAdmin/company-dossier-lab.git",
    )
    foreign = _repo(
        tmp_path / "foreign",
        "https://github.com/BCRAdmin/materialbedarf-rechner.de.git",
    )
    return research, product, foreign


def test_external_foreign_drift_is_recorded_not_blocking(
    repos: tuple[Path, Path, Path],
) -> None:
    research, product, foreign = repos
    before = foreign_snapshot(foreign)
    (foreign / "seed.txt").write_text("external drift\n", encoding="utf-8")
    after = foreign_snapshot(foreign)
    receipt = build_receipt(
        before=before,
        after=after,
        room16_roots=[research, product],
        command_audit=[
            {
                "argv": ["pytest", "-q"],
                "cwd": str(research),
                "mutation_classification": "room16_test_or_verification",
            }
        ],
        changed_paths={"created": [], "modified": [], "deleted": []},
        output_paths=[research / "outputs" / "candidate.zip"],
        foreign_repo_used_as_authority_input=False,
    )
    assert receipt["verdict"] == "PASS"
    assert receipt["external_foreign_drift_observed"] is True
    assert receipt["room16_foreign_mutation"] is False


def test_mutating_command_targeting_foreign_blocks(
    repos: tuple[Path, Path, Path],
) -> None:
    research, product, foreign = repos
    snapshot = foreign_snapshot(foreign)
    with pytest.raises(BoundaryGateV2Error, match="BOUNDARY_V2_BLOCK"):
        build_receipt(
            before=snapshot,
            after=snapshot,
            room16_roots=[research, product],
            command_audit=[
                {
                    "argv": ["git", "add", "seed.txt"],
                    "cwd": str(foreign),
                    "mutation_classification": "room16_write",
                }
            ],
            changed_paths={"created": [], "modified": [], "deleted": []},
            output_paths=[],
            foreign_repo_used_as_authority_input=False,
        )


def test_output_resolving_into_foreign_blocks(
    repos: tuple[Path, Path, Path],
) -> None:
    research, product, foreign = repos
    snapshot = foreign_snapshot(foreign)
    with pytest.raises(BoundaryGateV2Error, match="BOUNDARY_V2_BLOCK"):
        build_receipt(
            before=snapshot,
            after=snapshot,
            room16_roots=[research, product],
            command_audit=[],
            changed_paths={"created": [], "modified": [], "deleted": []},
            output_paths=[foreign / "candidate.zip"],
            foreign_repo_used_as_authority_input=False,
        )
