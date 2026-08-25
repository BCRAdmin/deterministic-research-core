#!/usr/bin/env python3
"""Fail-closed Room16 causal project-boundary verifier (Gate v2)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Iterable

CONTRACT_ID = "room16.project_boundary_non_interference@2"
FOREIGN_ORIGIN = "https://github.com/BCRAdmin/materialbedarf-rechner.de.git"
ROOM16_ORIGINS = {
    "https://github.com/BCRAdmin/deterministic-research-core.git",
    "https://github.com/BCRAdmin/company-dossier-lab.git",
}


class BoundaryGateV2Error(RuntimeError):
    """Stable Gate-v2 diagnostic."""


def _canonical_sha(value: dict[str, Any], omitted: str) -> str:
    body = dict(value)
    body.pop(omitted, None)
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _git(repo: Path, *args: str) -> str:
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    result = subprocess.run(
        ["git", "--no-optional-locks", *args],
        cwd=repo,
        env=environment,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise BoundaryGateV2Error(
            f"BOUNDARY_V2_GIT_FAILED:{repo}:{' '.join(args)}:{result.stderr.strip()}"
        )
    return result.stdout.strip()


def _real(path: Path | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _overlap(left: Path, right: Path) -> bool:
    return _is_within(left, right) or _is_within(right, left)


def _status_sha(lines: list[str]) -> str:
    return hashlib.sha256(("\n".join(lines) + "\n").encode()).hexdigest()


def foreign_snapshot(foreign_root: Path) -> dict[str, Any]:
    """Capture foreign identity with Git optional locks disabled."""

    root = _real(foreign_root)
    origin = _git(root, "remote", "get-url", "origin")
    if origin != FOREIGN_ORIGIN:
        raise BoundaryGateV2Error(f"BOUNDARY_V2_FOREIGN_ORIGIN:{origin}")
    worktree_paths = [
        _real(line.removeprefix("worktree "))
        for line in _git(root, "worktree", "list", "--porcelain").splitlines()
        if line.startswith("worktree ")
    ]
    worktrees: list[dict[str, Any]] = []
    for path in worktree_paths:
        status = _git(
            path,
            "status",
            "--porcelain=v2",
            "--branch",
            "--untracked-files=all",
        ).splitlines()
        worktrees.append(
            {
                "branch": _git(path, "branch", "--show-current"),
                "git_common_dir": str(
                    _real(_git(path, "rev-parse", "--path-format=absolute", "--git-common-dir"))
                ),
                "git_dir": str(
                    _real(_git(path, "rev-parse", "--path-format=absolute", "--git-dir"))
                ),
                "head": _git(path, "rev-parse", "HEAD"),
                "path": str(path),
                "status_entry_count": len(status),
                "status_sha256": _status_sha(status),
                "tree": _git(path, "rev-parse", "HEAD^{tree}"),
            }
        )
    snapshot: dict[str, Any] = {
        "contract_id": "room16.foreign_repository_readonly_snapshot@2",
        "foreign_mutation_commands": [],
        "origin": origin,
        "readonly_audit_commands": [
            "git --no-optional-locks worktree list --porcelain",
            "git --no-optional-locks status --porcelain=v2 --branch --untracked-files=all",
            "git --no-optional-locks rev-parse HEAD",
            "git --no-optional-locks rev-parse HEAD^{tree}",
            "git --no-optional-locks rev-parse --path-format=absolute --git-dir",
            "git --no-optional-locks rev-parse --path-format=absolute --git-common-dir",
        ],
        "repository_root": str(root),
        "schema_version": 2,
        "snapshot_sha256": "",
        "worktrees": worktrees,
    }
    snapshot["snapshot_sha256"] = _canonical_sha(snapshot, "snapshot_sha256")
    return snapshot


def verify_snapshot(snapshot: dict[str, Any]) -> None:
    if (
        snapshot.get("contract_id")
        != "room16.foreign_repository_readonly_snapshot@2"
        or snapshot.get("origin") != FOREIGN_ORIGIN
        or snapshot.get("foreign_mutation_commands") != []
        or snapshot.get("snapshot_sha256")
        != _canonical_sha(snapshot, "snapshot_sha256")
    ):
        raise BoundaryGateV2Error("BOUNDARY_V2_FOREIGN_SNAPSHOT_INVALID")
    worktrees = snapshot.get("worktrees")
    if not isinstance(worktrees, list) or not worktrees:
        raise BoundaryGateV2Error("BOUNDARY_V2_FOREIGN_WORKTREES_REQUIRED")


def _foreign_delta(
    before: dict[str, Any], after: dict[str, Any]
) -> list[dict[str, Any]]:
    before_by_path = {item["path"]: item for item in before["worktrees"]}
    after_by_path = {item["path"]: item for item in after["worktrees"]}
    changes: list[dict[str, Any]] = []
    for path in sorted(set(before_by_path) | set(after_by_path)):
        left = before_by_path.get(path)
        right = after_by_path.get(path)
        if left == right:
            continue
        changes.append(
            {
                "after": right,
                "before": left,
                "path": path,
            }
        )
    return changes


def _command_targets_foreign(
    command: dict[str, Any], foreign_roots: list[Path]
) -> bool:
    cwd = _real(str(command.get("cwd", "/")))
    if any(_is_within(cwd, root) for root in foreign_roots):
        return True
    argv = command.get("argv", [])
    if not isinstance(argv, list):
        return True
    for token in argv:
        if not isinstance(token, str):
            return True
        if token.startswith("/"):
            target = _real(token)
            if any(_is_within(target, root) for root in foreign_roots):
                return True
        if any(str(root) in token for root in foreign_roots):
            return True
    return False


def _git_identity(root: Path) -> tuple[str, str]:
    origin = _git(root, "remote", "get-url", "origin")
    common_dir = str(
        _real(_git(root, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    )
    return origin, common_dir


def build_receipt(
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    room16_roots: Iterable[Path],
    command_audit: list[dict[str, Any]],
    changed_paths: dict[str, list[Path]],
    output_paths: Iterable[Path],
    foreign_repo_used_as_authority_input: bool,
) -> dict[str, Any]:
    verify_snapshot(before)
    verify_snapshot(after)
    room_roots = [_real(path) for path in room16_roots]
    origins_and_common_dirs = [_git_identity(path) for path in room_roots]
    if {origin for origin, _ in origins_and_common_dirs} != ROOM16_ORIGINS:
        raise BoundaryGateV2Error("BOUNDARY_V2_ROOM16_ORIGIN_SET_INVALID")
    room_common_dirs = [common for _, common in origins_and_common_dirs]
    foreign_roots = sorted(
        {
            _real(before["repository_root"]),
            *(_real(item["path"]) for item in before["worktrees"]),
            *(_real(item["path"]) for item in after["worktrees"]),
        },
        key=str,
    )
    foreign_common_dirs = sorted(
        {
            str(_real(item["git_common_dir"]))
            for item in [*before["worktrees"], *after["worktrees"]]
        }
    )
    common_dir_overlap = bool(set(room_common_dirs) & set(foreign_common_dirs))
    root_overlap = any(_overlap(room, foreign) for room in room_roots for foreign in foreign_roots)

    allowed_classes = {"read_only", "room16_write", "room16_test_or_verification"}
    if any(item.get("mutation_classification") not in allowed_classes for item in command_audit):
        raise BoundaryGateV2Error("BOUNDARY_V2_COMMAND_CLASSIFICATION_INVALID")
    room16_mutating_commands = [
        item for item in command_audit if item["mutation_classification"] != "read_only"
    ]
    foreign_targeting = [
        item
        for item in room16_mutating_commands
        if _command_targets_foreign(item, foreign_roots)
    ]

    resolved_changes: dict[str, list[str]] = {}
    foreign_write_paths: list[str] = []
    for change_type in ("created", "modified", "deleted"):
        paths = sorted({_real(path) for path in changed_paths.get(change_type, [])}, key=str)
        resolved_changes[change_type] = [str(path) for path in paths]
        foreign_write_paths.extend(
            str(path)
            for path in paths
            if any(_is_within(path, foreign) for foreign in foreign_roots)
        )
        if any(not any(_is_within(path, room) for room in room_roots) for path in paths):
            raise BoundaryGateV2Error(f"BOUNDARY_V2_NON_ROOM16_{change_type.upper()}_PATH")

    output_realpaths = sorted({str(_real(path)) for path in output_paths})
    output_into_foreign = any(
        _is_within(Path(path), foreign)
        for path in output_realpaths
        for foreign in foreign_roots
    )
    delta = _foreign_delta(before, after)
    receipt: dict[str, Any] = {
        "command_audit_count": len(command_audit),
        "common_dir_overlap": common_dir_overlap,
        "contract_id": CONTRACT_ID,
        "external_foreign_drift_observed": bool(delta),
        "foreign_after_snapshot_sha256": after["snapshot_sha256"],
        "foreign_before_snapshot_sha256": before["snapshot_sha256"],
        "foreign_delta_summary": delta,
        "foreign_git_common_dirs": foreign_common_dirs,
        "foreign_readonly_audit_commands": sorted(
            set(before["readonly_audit_commands"] + after["readonly_audit_commands"])
        ),
        "foreign_repo_used_as_authority_input": foreign_repo_used_as_authority_input,
        "foreign_roots": [str(path) for path in foreign_roots],
        "foreign_targeting_mutating_commands": foreign_targeting,
        "output_resolves_into_foreign_root": output_into_foreign,
        "path_root_overlap": root_overlap,
        "room16_created_paths": resolved_changes["created"],
        "room16_deleted_paths": resolved_changes["deleted"],
        "room16_foreign_mutation": bool(foreign_targeting or foreign_write_paths),
        "room16_foreign_write_paths": sorted(set(foreign_write_paths)),
        "room16_git_common_dirs": room_common_dirs,
        "room16_modified_paths": resolved_changes["modified"],
        "room16_mutating_commands": room16_mutating_commands,
        "room16_output_realpaths": output_realpaths,
        "room16_roots": [str(path) for path in room_roots],
        "schema_version": 2,
        "verdict": "PASS",
    }
    verify_receipt(receipt)
    return receipt


def verify_receipt(receipt: dict[str, Any]) -> None:
    failures = []
    if receipt.get("contract_id") != CONTRACT_ID:
        failures.append("contract_id")
    for field in (
        "common_dir_overlap",
        "output_resolves_into_foreign_root",
        "path_root_overlap",
        "room16_foreign_mutation",
        "foreign_repo_used_as_authority_input",
    ):
        if receipt.get(field) is not False:
            failures.append(field)
    for field in (
        "foreign_targeting_mutating_commands",
        "room16_foreign_write_paths",
    ):
        if receipt.get(field) != []:
            failures.append(field)
    if receipt.get("verdict") != "PASS":
        failures.append("verdict")
    if not receipt.get("room16_roots") or not receipt.get("foreign_roots"):
        failures.append("roots")
    if set(receipt.get("room16_git_common_dirs", [])) & set(
        receipt.get("foreign_git_common_dirs", [])
    ):
        failures.append("git_common_dir_overlap")
    if failures:
        raise BoundaryGateV2Error("BOUNDARY_V2_BLOCK:" + ",".join(sorted(failures)))


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BoundaryGateV2Error(f"BOUNDARY_V2_JSON_OBJECT_REQUIRED:{path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    snapshot_parser = subparsers.add_parser("snapshot")
    snapshot_parser.add_argument("--foreign-root", type=Path, required=True)
    snapshot_parser.add_argument("--output", type=Path)
    verify_parser = subparsers.add_parser("verify-receipt")
    verify_parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    if args.command == "snapshot":
        value = foreign_snapshot(args.foreign_root)
        payload = json.dumps(value, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload, encoding="utf-8")
        print(payload, end="")
        return 0
    receipt = _read_json(args.receipt)
    verify_receipt(receipt)
    print(json.dumps({"contract_id": CONTRACT_ID, "status": "PASS"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
