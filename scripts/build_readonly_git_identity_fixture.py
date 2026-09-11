#!/usr/bin/env python3
"""Build a read-only Git bundle bound to an exact commit and tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def _run(args: list[str], cwd: Path) -> str:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=True).stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--expected-tree", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-tag", action="append", default=[])
    args = parser.parse_args()
    commit = _run(["git", "rev-parse", f"{args.commit}^{{commit}}"], args.repo)
    tree = _run(["git", "rev-parse", f"{commit}^{{tree}}"], args.repo)
    if commit != args.commit or tree != args.expected_tree:
        raise SystemExit(f"BLOCK identity mismatch commit={commit} tree={tree}")
    refs = _run(["git", "for-each-ref", "--format=%(refname)", "--points-at", commit], args.repo).splitlines()
    refs = [ref for ref in refs if ref.startswith("refs/heads/") or ref.startswith("refs/tags/")]
    if not refs:
        raise SystemExit(f"BLOCK no local branch/tag points at exact commit: {commit}")
    source_ref = sorted(refs)[0]
    bundle_refs = [source_ref]
    for tag in args.include_tag:
        tag_ref = f"refs/tags/{tag}"
        resolved = _run(["git", "rev-parse", "--verify", tag_ref], args.repo)
        if not resolved:
            raise SystemExit(f"BLOCK missing required tag: {tag}")
        bundle_refs.append(tag_ref)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "bundle", "create", str(args.output), *bundle_refs], cwd=args.repo, check=True)
    verify = subprocess.run(["git", "bundle", "verify", str(args.output)], cwd=args.repo, text=True, capture_output=True)
    if verify.returncode:
        raise SystemExit("BLOCK git bundle verification failed: " + verify.stderr)
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    receipt = {
        "contract_id": "room16.r16.readonly_git_identity_fixture@1",
        "commit": commit,
        "tree": tree,
        "source_ref": source_ref,
        "included_refs": bundle_refs,
        "bundle": args.output.name,
        "sha256": digest,
        "bytes": args.output.stat().st_size,
        "status": "PASS",
    }
    Path(str(args.output) + ".receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
