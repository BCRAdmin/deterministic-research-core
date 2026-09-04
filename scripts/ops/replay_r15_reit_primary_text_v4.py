#!/usr/bin/env python3
"""Replay REIT-v4 parsing against the real exposed R15 SEC corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from research_agent.alpha_reit.primary_text_v4 import (
    PARSER_CONTRACT_SHA256,
    canonical_sha256,
    parse_primary_text_candidates_v4,
    select_reported_ffo_v4,
)

EXPECTED_R15_COMPACT_SHA256 = (
    "71c4ec48c3b69a156d2a5e89bb88a191e2691d0e4e7f34244169a3c91507c8cc"
)
AS_OF = "2026-09-04"
EXPECTED_SELECTED: dict[str, tuple[str, str] | None] = {
    "RLJ": ("FFO", "72672000"),
    "NXDT": ("FFO attributable to common shareholders", "3411000"),
    "MRP": None,
    "AAT": ("FFO attributable to common stock and units", "39286000"),
    "GNL": (
        "FFO (as defined by NAREIT) attributable to common stockholders",
        "13934000",
    ),
    "BRT": (
        "NAREIT Funds from operations attributable to common stockholders",
        "5505000",
    ),
    "FCPT": ("FFO (as defined by NAREIT)", "46108000"),
    "RHP": ("FFO available to common stockholders and unit holders", "167229000"),
    "CTO": ("Funds From Operations Attributable to Common Stockholders", "19137000"),
    "NTST": ("FFO", "34577000"),
    "ESS": (
        "Funds from operations attributable to common stockholders and unitholders",
        "220556000",
    ),
    "AHR": ("NAREIT FFO attributable to controlling interest", "97976000"),
}


def _safe_names(archive: zipfile.ZipFile) -> list[str]:
    names = archive.namelist()
    if len(names) != len(set(names)):
        raise ValueError("R15_ZIP_DUPLICATE_MEMBER")
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"R15_ZIP_UNSAFE_MEMBER:{name}")
    return names


def _case_prefixes(names: Iterable[str]) -> list[str]:
    prefixes = {
        "/".join(PurePosixPath(name).parts[:2])
        for name in names
        if len(PurePosixPath(name).parts) >= 3
        and PurePosixPath(name).parts[0] == "epoch2_cases"
        and PurePosixPath(name).parts[1][:2].isdigit()
    }
    return sorted(prefixes)


def replay_archive(compact: Path) -> dict[str, Any]:
    zip_sha = hashlib.sha256(compact.read_bytes()).hexdigest()
    if zip_sha != EXPECTED_R15_COMPACT_SHA256:
        raise ValueError(f"R15_COMPACT_IDENTITY_MISMATCH:{zip_sha}")

    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(compact) as archive, tempfile.TemporaryDirectory(
        prefix="room16-r15-v4-replay-"
    ) as temp_dir:
        prefixes = _case_prefixes(_safe_names(archive))
        if len(prefixes) != 12:
            raise ValueError(f"R15_CASE_CARDINALITY:{len(prefixes)}")

        for prefix in prefixes:
            ticker = PurePosixPath(prefix).name.split("_", 1)[1]
            discovery = json.loads(
                archive.read(
                    f"{prefix}/primary_text/DISCOVERED_SOURCE_SET_RECEIPT.json"
                )
            )
            candidates: list[dict[str, Any]] = []
            rejections: list[dict[str, Any]] = []
            document_hashes: list[str] = []
            for index, filing in enumerate(discovery["documents"]):
                accession = str(filing["accession"]).replace("-", "")
                name = str(filing["document_name"])
                member = (
                    f"{prefix}/primary_text/captures/sec_documents/"
                    f"{accession}/{name}"
                )
                payload = archive.read(member)
                artifact_sha = hashlib.sha256(payload).hexdigest()
                document_hashes.append(artifact_sha)
                local = Path(temp_dir) / f"{ticker}-{index:02d}{Path(name).suffix or '.html'}"
                local.write_bytes(payload)
                parsed = parse_primary_text_candidates_v4(
                    local,
                    ticker=ticker,
                    cik=str(discovery["cik"]),
                    filing=filing,
                    source_artifact_sha256=artifact_sha,
                    source_snapshot_sha256=discovery["submissions_sha256"],
                )
                candidates.extend(parsed["candidates"])
                rejections.extend(parsed["rejected_rows"])

            selection = select_reported_ffo_v4(candidates, as_of=AS_OF)
            projection = selection["selected_projection"]
            expected = EXPECTED_SELECTED[ticker]
            if expected is None:
                if projection is not None:
                    raise ValueError(f"R15_V4_EXPECTED_UNSUPPORTED:{ticker}")
            elif projection is None or (
                projection["reported_label"], projection["numeric_value"]
            ) != expected:
                raise ValueError(f"R15_V4_SELECTION_DRIFT:{ticker}:{projection!r}")

            if ticker == "BRT":
                bad = "NAREIT Funds from operations per diluted common share"
                if projection is None or projection["reported_label"] == bad:
                    raise ValueError("BRT_PER_SHARE_FALSE_POSITIVE")
                if not any(
                    row.get("reported_label") == bad
                    and row.get("reason")
                    in {"PER_SHARE_NOT_ABSOLUTE_FFO", "PER_SHARE_TABLE_CONTEXT"}
                    for row in rejections
                ):
                    raise ValueError("BRT_PER_SHARE_REJECTION_NOT_PROVEN")
            if ticker == "ESS":
                bad = "Gains not included in FFO"
                if projection is None or projection["reported_label"] == bad:
                    raise ValueError("ESS_COMPONENT_FALSE_POSITIVE")
                if not any(
                    row.get("reported_label") == bad
                    and row.get("reason") == "FFO_COMPONENT_OR_NON_MEASURE"
                    for row in rejections
                ):
                    raise ValueError("ESS_COMPONENT_REJECTION_NOT_PROVEN")

            counts = Counter(row["reason"] for row in rejections)
            rows.append(
                {
                    "ticker": ticker,
                    "candidate_count": len(candidates),
                    "rejected_row_count": len(rejections),
                    "rejection_counts": dict(sorted(counts.items())),
                    "selected_projection": projection,
                    "selection_receipt_sha256": selection["receipt"]["receipt_sha256"],
                    "document_artifact_sha256": document_hashes,
                }
            )

    body = {
        "contract_id": "room16.reit.v4.r15_real_corpus_replay@1",
        "status": "PASS",
        "r15_compact_sha256": zip_sha,
        "parser_contract_sha256": PARSER_CONTRACT_SHA256,
        "as_of": AS_OF,
        "case_count": len(rows),
        "selected_absolute_ffo_count": sum(
            row["selected_projection"] is not None for row in rows
        ),
        "unsupported_count": sum(row["selected_projection"] is None for row in rows),
        "critical_regressions": {
            "BRT_per_share_rejected": True,
            "BRT_absolute_ffo_selected": True,
            "ESS_adjustment_row_rejected": True,
            "ESS_absolute_ffo_selected": True,
        },
        "cases": rows,
    }
    return {**body, "replay_sha256": canonical_sha256(body)}


def _default_compact(repo: Path) -> Path | None:
    matches = list(
        repo.glob(
            "outputs/release/ROOM16_R15_REIT_V3_PRIMARY_TEXT_CLEAN_VALIDATION_*_UPLOAD_COMPACT.zip"
        )
    )
    exact = [
        path
        for path in matches
        if hashlib.sha256(path.read_bytes()).hexdigest() == EXPECTED_R15_COMPACT_SHA256
    ]
    return sorted(exact)[-1] if exact else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--r15-compact", type=Path)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    compact = args.r15_compact or _default_compact(args.repo.resolve())
    if compact is None:
        raise SystemExit("R15 compact not found; pass --r15-compact")
    result = replay_archive(compact.resolve())
    rendered = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
