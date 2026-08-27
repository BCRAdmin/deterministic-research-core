#!/usr/bin/env python3
"""Fresh-process offline replay of an Alpha Energy live run."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path


EXPECTED_ORIGIN = "https://github.com/BCRAdmin/deterministic-research-core.git"


def _configured_research_root() -> Path:
    try:
        index = sys.argv.index("--research-root")
        configured = Path(sys.argv[index + 1]).expanduser().resolve()
    except (ValueError, IndexError):
        raise SystemExit("--research-root is required") from None
    top = Path(
        subprocess.check_output(
            ["git", "-C", str(configured), "rev-parse", "--show-toplevel"], text=True
        ).strip()
    ).resolve()
    origin = subprocess.check_output(
        ["git", "-C", str(top), "remote", "get-url", "origin"], text=True
    ).strip()
    if top != configured or origin != EXPECTED_ORIGIN:
        raise SystemExit("configured research root identity mismatch")
    sys.path.insert(0, str(top))
    return top


ROOT = _configured_research_root()

from research_agent.alpha_energy.compiler import build_alpha_energy_bundle  # noqa: E402
from research_agent.ba12_live_source import (  # noqa: E402
    LiveCaptureExecutor,
    recover_bridge,
    verify_live_bridge,
)
from research_agent.ba12_live_source.recovery import load_closed_run  # noqa: E402
from research_agent.semantic_compiler.source_frontend.contracts import (  # noqa: E402
    CompileRequestIR,
    SourceAcquisitionIR,
)


def _git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--research-root", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    args = parser.parse_args()
    context = json.loads((args.run_root / "run_context.json").read_text())
    request = CompileRequestIR.model_validate(context["request"])
    plan = SourceAcquisitionIR.model_validate(context["plan"])
    executor = LiveCaptureExecutor(Path(context["live_root"]))
    started = time.monotonic()
    recovered = load_closed_run(executor=executor, closure_sha256=context["closure_sha256"])
    snapshot_root = args.run_root / "runtime/replay_snapshot"
    replay = recover_bridge(
        request=request,
        plan=plan,
        executor=executor,
        snapshot_root=snapshot_root,
        staged_at_utc=context["authority_time"],
    )
    records = tuple(
        executor.load_successful_record(
            request_sha256=request.request_sha256,
            acquisition_id=item.acquisition_id,
            attempt_id=item.attempt_id,
        )
        for item in recovered.attempts
    )
    bridge_verification = verify_live_bridge(
        records=records,
        result=replay,
        capture_store_root=executor.capture_store.root,
    )
    compiled = build_alpha_energy_bundle(
        snapshot=replay.snapshot,
        snapshot_root=snapshot_root,
        output_root=args.run_root / "runtime/replay_bundle",
        research_commit=_git("rev-parse", "HEAD"),
        research_tree=_git("rev-parse", "HEAD^{tree}"),
        monotonic_counter=int(context["monotonic_counter"]),
    )
    live_bundle = Path(context["bundle_root"])
    live_manifest = json.loads((live_bundle / "BUNDLE_MANIFEST.json").read_text())
    live_receipt = json.loads((live_bundle / "RECEIPT.json").read_text())
    semantic_equal = (
        replay.snapshot.snapshot_sha256 == recovered.snapshot.snapshot_sha256
        and compiled.manifest["bundle_sha256"] == live_manifest["bundle_sha256"]
        and compiled.receipt["receipt_sha256"] == live_receipt["receipt_sha256"]
        and _tree_hash(compiled.bundle_root) == _tree_hash(live_bundle)
    )
    report = {
        "status": "PASS" if semantic_equal else "FAIL",
        "fresh_process": True,
        "network_provider_calls": 0,
        "replay_input": "durable_capture_authority_only",
        "closure_sha256": recovered.closure.closure_sha256,
        "live_snapshot_sha256": recovered.snapshot.snapshot_sha256,
        "replay_snapshot_sha256": replay.snapshot.snapshot_sha256,
        "live_bundle_sha256": live_manifest["bundle_sha256"],
        "replay_bundle_sha256": compiled.manifest["bundle_sha256"],
        "live_receipt_sha256": live_receipt["receipt_sha256"],
        "replay_receipt_sha256": compiled.receipt["receipt_sha256"],
        "live_bundle_tree_sha256": _tree_hash(live_bundle),
        "replay_bundle_tree_sha256": _tree_hash(compiled.bundle_root),
        "semantic_truth_identical": semantic_equal,
        "bridge_verification": bridge_verification,
        "recovery_seconds": round(time.monotonic() - started, 6),
    }
    output = args.run_root / "evidence/08_LIVE_VS_REPLAY_REPORT.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    return 0 if semantic_equal else 1


if __name__ == "__main__":
    raise SystemExit(main())
