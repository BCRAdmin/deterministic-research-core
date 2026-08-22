#!/usr/bin/env python3
"""Build deterministic evidence for the BA12 RFC-0008 native identity stop."""

from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

from verify_ba12_native_trust_stop_evidence import manifest_hash, verify_package

ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
FOREIGN = ROOT.parent.parent / "Utility-Websites/materialbedarf-rechner.de"
HANDOFF = Path(
    "/Users/BjornRosinger/Downloads/"
    "ROOM16_RFC0008_ACCEPTANCE_FREEZE_AND_BA12_RESUME_EXECUTION_R1_"
    "2A718E7656C6_2026-08-22.zip"
)
FIXED_TIME = (2026, 8, 22, 0, 0, 0)


def run(command: list[str], cwd: Path = ROOT) -> str:
    result = subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)
    if result.returncode:
        raise SystemExit(
            f"STOP evidence command failed ({result.returncode}): {' '.join(command)}\n"
            f"{result.stdout}{result.stderr}"
        )
    return result.stdout


def git(repo: Path, *args: str) -> str:
    return run(["git", "-C", str(repo), *args]).strip()


def pretty(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def archive_bytes(payloads: dict[str, bytes], manifest: dict[str, Any]) -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, payload in sorted({**payloads, "MANIFEST.json": pretty(manifest)}.items()):
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, payload)
    return output.getvalue()


def main() -> int:
    if git(ROOT, "status", "--porcelain=v1") or git(PRODUCT, "status", "--porcelain=v1"):
        raise SystemExit("STOP evidence build requires clean authorized repositories")
    probe = json.loads(
        run(
            [
                str(ROOT / ".venv/bin/python"),
                "scripts/ops/verify_ba12_rfc0008_native_trust_conflict.py",
                "--json",
            ]
        )
    )
    freeze = json.loads(
        run(
            [
                str(ROOT / ".venv/bin/python"),
                "scripts/ops/verify_rfc0008_v2_trust_freeze.py",
                "--handoff",
                str(HANDOFF),
                "--product-repo",
                str(PRODUCT),
                "--json",
            ]
        )
    )
    stop = json.loads(
        (ROOT / "docs/compiler_foundation/rfcs/BA12_R2_NATIVE_TRUST_CONFLICT_STOP.json").read_text()
    )
    foreign_status = git(FOREIGN, "status", "--short", "--branch").splitlines()
    foreign = {
        "path": str(FOREIGN),
        "head": git(FOREIGN, "rev-parse", "HEAD"),
        "tree": git(FOREIGN, "rev-parse", "HEAD^{tree}"),
        "status": foreign_status,
        "expected_preexisting_untracked": "?? ops/product-repair-v1/",
        "unchanged": "?? ops/product-repair-v1/" in foreign_status,
        "read_only": True,
    }
    bindings = {
        "research": {
            "origin": git(ROOT, "remote", "get-url", "origin"),
            "branch": git(ROOT, "branch", "--show-current"),
            "head": git(ROOT, "rev-parse", "HEAD"),
            "tree": git(ROOT, "rev-parse", "HEAD^{tree}"),
            "remote_drift": git(ROOT, "rev-list", "--left-right", "--count", "origin/main...HEAD"),
        },
        "product": {
            "origin": git(PRODUCT, "remote", "get-url", "origin"),
            "branch": git(PRODUCT, "branch", "--show-current"),
            "head": git(PRODUCT, "rev-parse", "HEAD"),
            "tree": git(PRODUCT, "rev-parse", "HEAD^{tree}"),
            "remote_drift": git(
                PRODUCT,
                "rev-list",
                "--left-right",
                "--count",
                "origin/bcr-report-lab-original-trading-flow...HEAD",
            ),
        },
    }
    payloads = {
        "00_STOP_VERDICT.md": (
            "# BA12 R2 Native Trust Stop\n\n"
            "Verdict: **STOPPED — RFC trigger required**.\n\n"
            "A truthful `source_native` CompilerIdentityV2 is rejected by the frozen "
            "RFC-0008 trust policy with `RFC8_TRUST_POLICY_MISMATCH`. Stop Conditions "
            "2, 6, 7 and 8 apply. No trust weakening, BA12 freeze, release, publication "
            "or deployment was performed.\n"
        ).encode(),
        "01_MACHINE_STOP_EVIDENCE.json": pretty(stop),
        "02_NATIVE_TRUST_PROBE_RECEIPT.json": pretty(probe),
        "03_RFC0008_FREEZE_VERIFIER_RECEIPT.json": pretty(freeze),
        "04_RFC_0007.md": (
            ROOT / "docs/compiler_foundation/rfcs/RFC-0007_BA12_FINAL_STRANGLER_CUTOVER.md"
        ).read_bytes(),
        "05_RFC0008_FREEZE_RECORD.json": (
            ROOT
            / "docs/compiler_foundation/freezes/"
            "RFC0008_COMPILER_ARTIFACT_BUNDLE_V2_TRUST_FREEZE_v1.json"
        ).read_bytes(),
        "06_SOURCE_TREE_BINDINGS.json": pretty(bindings),
        "07_FOREIGN_REPOSITORY_BOUNDARY.json": pretty(foreign),
        "08_REQUIRED_RFC_DECISION.md": (
            "# Required RFC Decision\n\n"
            "Independently define and accept a signed source-native CompilerIdentityV2 "
            "policy generation or successor trust root. The current migration trust "
            "boundary must remain immutable and Product must not choose or weaken the root.\n"
        ).encode(),
    }
    changed = [
        "docs/compiler_foundation/rfcs/BA12_R2_NATIVE_TRUST_CONFLICT_STOP.json",
        "docs/compiler_foundation/rfcs/RFC-0007_BA12_FINAL_STRANGLER_CUTOVER.md",
        "research_agent/tests/test_ba12_native_trust_stop.py",
        "scripts/ops/verify_ba12_rfc0008_native_trust_conflict.py",
    ]
    for relative in changed:
        payloads[f"changed_sources/research/{relative}"] = (ROOT / relative).read_bytes()
    manifest = {
        "contract_id": "room16.ba12.native_trust_stop_evidence@1",
        "schema_version": 1,
        "generated_date": "2026-08-22",
        "research_head": bindings["research"]["head"],
        "product_head": bindings["product"]["head"],
        "status": "STOPPED_RFC_TRIGGER_REQUIRED",
        "payloads": [
            {"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in sorted(payloads.items())
        ],
        "manifest_sha256": "",
    }
    manifest["manifest_sha256"] = manifest_hash(manifest)
    first = archive_bytes(payloads, manifest)
    second = archive_bytes(payloads, manifest)
    if first != second:
        raise SystemExit("STOP evidence archive is not deterministic")
    output = ROOT / "outputs/release" / (
        "ROOM16_BA12_R2_NATIVE_TRUST_STOP_RFC_TRIGGER_"
        f"{bindings['research']['head'][:12].upper()}_2026-08-22.zip"
    )
    output.write_bytes(first)
    verification = verify_package(output)
    receipt = output.with_suffix(".verification_receipt.json")
    receipt.write_bytes(pretty(verification))
    print(
        json.dumps(
            {
                **verification,
                "output": str(output),
                "receipt": str(receipt),
                "byte_identical_builds": True,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
