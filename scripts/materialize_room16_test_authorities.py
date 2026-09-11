#!/usr/bin/env python3
"""Materialize byte-bound Room16 historical authorities for hermetic tests."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path


OBJECTS = {
    "ROOM16_BA12_WHOLE_SYSTEM_ACCEPTANCE_FREEZE_EXECUTION_R1_CB3CF2FA346A_2026-08-25.zip": (
        "cb3cf2fa346ac542bba7dc0516e70109fced024484fa042054777bfa5be6431c",
        113501,
    ),
    "ROOM16_RFC0008_ACCEPTANCE_FREEZE_AND_BA12_RESUME_EXECUTION_R1_2A718E7656C6_2026-08-22.zip": (
        "2a718e7656c60588c1935d790983688bd09e5e45649c26e6ebca63342f33fb3f",
        391088,
    ),
    "ROOM16_RFC0009_ACCEPTANCE_FREEZE_AND_BA12_FINAL_RESUME_EXECUTION_R1_B523B123796E_2026-08-24.zip": (
        "b523b123796e20c7bdaf52bb175be254376e35c5d17fa171651d18bda5163ebf",
        263808,
    ),
    "ROOM16_RFC0010_ACCEPTANCE_FREEZE_AND_BA12_RESUME_EXECUTION_R1_B3C1F0A161CA_2026-08-25.zip": (
        "b3c1f0a161ca3492777807146247a314d074056bf2feaf61f55c27fe25667a1f",
        160762,
    ),
}


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _scan_zip(data: bytes, label: str, depth: int = 0) -> None:
    if depth > 8:
        raise SystemExit(f"BLOCK nested depth: {label}")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for info in archive.infolist():
            normalized = info.filename.replace("\\", "/")
            parts = Path(normalized).parts
            lower = normalized.lower()
            if normalized.startswith("/") or ".." in parts:
                raise SystemExit(f"BLOCK unsafe zip path: {label}!{info.filename}")
            base = Path(lower).name
            if base in {"signing_key_ed25519.bin", "private_key.pem", "id_ed25519"} or "/.runtime/" in "/" + lower:
                raise SystemExit(f"BLOCK private/runtime key path: {label}!{info.filename}")
            if info.is_dir():
                continue
            payload = archive.read(info)
            if Path(lower).suffix in {".pem", ".key", ".p8", ".pk8"}:
                markers = (
                    b"-----BEGIN PRIVATE KEY-----",
                    b"-----BEGIN OPENSSH PRIVATE KEY-----",
                    b"-----BEGIN ED25519 PRIVATE KEY-----",
                )
                if any(marker in payload for marker in markers):
                    raise SystemExit(f"BLOCK private key material: {label}!{info.filename}")
            if lower.endswith(".zip"):
                _scan_zip(payload, label + "!" + info.filename, depth + 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kit-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--fixture-root", type=Path)
    args = parser.parse_args()
    source = args.kit_root / "fixtures" / "historical_authorities"
    target = args.fixture_root or args.repo / "research_agent" / "tests" / "fixtures" / "historical_authorities"
    target.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, (expected, size) in OBJECTS.items():
        payload = (source / name).read_bytes()
        if len(payload) != size or _digest(payload) != expected:
            raise SystemExit(f"BLOCK fixture identity mismatch: {name}")
        _scan_zip(payload, name)
        destination = target / name
        destination.write_bytes(payload)
        rows.append({"filename": name, "sha256": expected, "bytes": size})
    receipt = {
        "contract_id": "room16.r16.materialized_historical_test_authorities@1",
        "status": "PASS",
        "fixture_root": "research_agent/tests/fixtures/historical_authorities",
        "objects": rows,
    }
    (target / "FIXTURE_RECEIPT.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
