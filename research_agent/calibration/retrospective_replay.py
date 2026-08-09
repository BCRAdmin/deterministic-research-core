from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

from research_agent.calibration.valuation_calibration import (
    VALUATION_REPLAY_SCHEMA,
    RetrospectiveReplayArtifact,
    ValuationCalibrationReplayManifest,
    ValuationCalibrationSnapshot,
    file_sha256,
)
from research_agent.research_core.ingestion.source_registry import (
    SourceRegistry,
    SourceRegistryEntry,
    save_source_registry,
)
from research_agent.research_core.models.report_config import ReportConfig
from research_agent.run_pipeline import run_research_pipeline


REQUIRED_REPLAY_ARTIFACTS = {
    "raw_companyfacts",
    "raw_prices",
    "cik_records",
    "sanitized_companyfacts",
    "sanitized_prices",
    "authority_manifest",
    "fact_ledger",
    "base_valuation_snapshot",
}


def sanitize_companyfacts_as_of(
    payload: dict[str, Any], as_of_date: str
) -> tuple[dict[str, Any], dict[str, int]]:
    cutoff = date.fromisoformat(as_of_date)
    sanitized = json.loads(json.dumps(payload))
    kept = 0
    removed_future = 0
    removed_undated = 0
    facts = sanitized.get("facts") or {}
    if not isinstance(facts, dict):
        raise ValueError("SEC CompanyFacts payload has no facts object")
    for taxonomy in facts.values():
        if not isinstance(taxonomy, dict):
            continue
        for concept in taxonomy.values():
            if not isinstance(concept, dict):
                continue
            units = concept.get("units") or {}
            if not isinstance(units, dict):
                continue
            for unit, rows in list(units.items()):
                if not isinstance(rows, list):
                    units[unit] = []
                    continue
                filtered: list[dict[str, Any]] = []
                for row in rows:
                    if not isinstance(row, dict):
                        removed_undated += 1
                        continue
                    filed = row.get("filed")
                    try:
                        filed_date = date.fromisoformat(str(filed or ""))
                    except ValueError:
                        removed_undated += 1
                        continue
                    if filed_date > cutoff:
                        removed_future += 1
                        continue
                    filtered.append(row)
                    kept += 1
                units[unit] = filtered
    return sanitized, {
        "companyfacts_rows_kept": kept,
        "companyfacts_future_rows_removed": removed_future,
        "companyfacts_undated_rows_removed": removed_undated,
    }


def sanitize_price_csv_as_of(
    source_path: Union[str, Path], target_path: Union[str, Path], as_of_date: str
) -> dict[str, int]:
    cutoff = date.fromisoformat(as_of_date)
    source = Path(source_path)
    target = Path(target_path)
    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "date" not in reader.fieldnames:
            raise ValueError("price CSV must contain a date column")
        rows: list[dict[str, str]] = []
        removed_future = 0
        for row in reader:
            try:
                row_date = date.fromisoformat(str(row.get("date") or ""))
            except ValueError as exc:
                raise ValueError("price CSV contains an invalid date") from exc
            if row_date > cutoff:
                removed_future += 1
                continue
            rows.append(row)
    if not rows:
        raise ValueError("price CSV contains no observations on or before replay cutoff")
    rows.sort(key=lambda row: str(row["date"]))
    if len({row["date"] for row in rows}) != len(rows):
        raise ValueError("price CSV contains duplicate dates")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=reader.fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return {
        "price_rows_kept": len(rows),
        "price_future_rows_removed": removed_future,
    }


def calculate_replay_manifest_sha256(
    manifest: ValuationCalibrationReplayManifest,
) -> str:
    payload = manifest.model_dump(mode="json")
    payload.pop("replay_manifest_sha256", None)
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def verify_replay_manifest(
    manifest_path: Union[str, Path],
) -> tuple[bool, list[str], Optional[ValuationCalibrationReplayManifest]]:
    path = Path(manifest_path).resolve()
    try:
        manifest = ValuationCalibrationReplayManifest(
            **json.loads(path.read_text(encoding="utf-8"))
        )
    except (OSError, ValueError, TypeError) as error:
        return False, [f"replay_manifest_invalid:{error}"], None
    reasons: list[str] = []
    if manifest.schema_id != VALUATION_REPLAY_SCHEMA:
        reasons.append("replay_schema_invalid")
    if not _aware_timestamp(manifest.generated_at):
        reasons.append("replay_generated_at_invalid")
    if not _git_sha(manifest.pipeline_commit_sha):
        reasons.append("replay_pipeline_commit_invalid")
    if manifest.source_cutoff_passed is not True:
        reasons.append("replay_source_cutoff_not_passed")
    if set(manifest.artifacts) != REQUIRED_REPLAY_ARTIFACTS:
        reasons.append("replay_artifact_set_invalid")
    root = path.parent.resolve()
    for name, binding in manifest.artifacts.items():
        artifact = (root / binding.path).resolve()
        try:
            artifact.relative_to(root)
        except ValueError:
            reasons.append(f"replay_artifact_path_escape:{name}")
            continue
        if not artifact.is_file():
            reasons.append(f"replay_artifact_missing:{name}")
        elif file_sha256(artifact) != binding.sha256:
            reasons.append(f"replay_artifact_hash_mismatch:{name}")
    if manifest.replay_manifest_sha256 != calculate_replay_manifest_sha256(manifest):
        reasons.append("replay_manifest_hash_mismatch")
    if not reasons:
        reasons.extend(_semantic_replay_reasons(root, manifest))
    return not reasons, sorted(set(reasons)), manifest


def promote_retrospective_snapshot(
    base_snapshot: ValuationCalibrationSnapshot,
    manifest_path: Union[str, Path],
) -> ValuationCalibrationSnapshot:
    valid, reasons, manifest = verify_replay_manifest(manifest_path)
    if manifest is None:
        manifest_hash = None
        replay_id = "invalid"
    else:
        manifest_hash = file_sha256(manifest_path)
        replay_id = manifest.replay_id
        if manifest.ticker != base_snapshot.ticker:
            reasons.append("replay_snapshot_ticker_mismatch")
        if manifest.as_of_date != base_snapshot.as_of_date:
            reasons.append("replay_snapshot_date_mismatch")
    identity = {
        "base_snapshot_id": base_snapshot.snapshot_id,
        "replay_id": replay_id,
        "replay_manifest_sha256": manifest_hash,
    }
    snapshot_id = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    )
    combined_reasons = sorted(set([*base_snapshot.exclusion_reasons, *reasons]))
    return base_snapshot.model_copy(
        update={
            "snapshot_id": snapshot_id,
            "capture_mode": "retrospective_replay",
            "base_snapshot_id": base_snapshot.snapshot_id,
            "retrospective_replay_manifest_sha256": manifest_hash,
            "eligible": bool(base_snapshot.eligible and valid and not combined_reasons),
            "exclusion_reasons": combined_reasons,
        }
    )


def build_retrospective_replay(
    *,
    ticker: str,
    as_of_date: str,
    raw_companyfacts_path: Union[str, Path],
    raw_prices_path: Union[str, Path],
    cik_records_path: Union[str, Path],
    replay_root: Union[str, Path],
) -> dict[str, Any]:
    symbol = ticker.strip().upper()
    cutoff = date.fromisoformat(as_of_date)
    if cutoff >= date.today():
        raise ValueError("retrospective replay date must be before today")
    commit_sha = _git_commit(Path(__file__).resolve().parents[2])
    replay_seed = {
        "ticker": symbol,
        "as_of_date": as_of_date,
        "pipeline_commit_sha": commit_sha,
        "raw_companyfacts_sha256": file_sha256(raw_companyfacts_path),
        "raw_prices_sha256": file_sha256(raw_prices_path),
    }
    replay_id = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(replay_seed, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    )
    root = (
        Path(replay_root).resolve() / symbol / as_of_date / replay_id.removeprefix("sha256:")[:16]
    )
    if root.exists():
        manifest_path = root / "retrospective_replay_manifest.json"
        promoted_path = (
            root / "outputs" / symbol / as_of_date / "valuation_calibration_replay_snapshot.json"
        )
        valid, reasons, _ = verify_replay_manifest(manifest_path)
        if not valid or not promoted_path.is_file():
            raise ValueError(
                "existing retrospective replay is incomplete or invalid: "
                + ", ".join(reasons or ["replay_snapshot_missing"])
            )
        promoted = ValuationCalibrationSnapshot(
            **json.loads(promoted_path.read_text(encoding="utf-8"))
        )
        return _replay_result(
            symbol=symbol,
            as_of_date=as_of_date,
            manifest_path=manifest_path,
            promoted_path=promoted_path,
            promoted=promoted,
            cutoff_counts={
                key: int(value)
                for key, value in json.loads(manifest_path.read_text(encoding="utf-8"))[
                    "cutoff_counts"
                ].items()
            },
        )
    inputs = root / "inputs"
    sanitized = root / "sanitized"
    packets = root / "packets"
    outputs = root / "outputs"
    for directory in (inputs, sanitized, packets, outputs):
        directory.mkdir(parents=True, exist_ok=True)

    raw_companyfacts = inputs / "raw_companyfacts.json"
    raw_prices = inputs / "raw_prices.csv"
    copied_cik_records = inputs / "cik_records.json"
    shutil.copyfile(raw_companyfacts_path, raw_companyfacts)
    shutil.copyfile(raw_prices_path, raw_prices)
    shutil.copyfile(cik_records_path, copied_cik_records)

    companyfacts_payload = json.loads(raw_companyfacts.read_text(encoding="utf-8"))
    sanitized_companyfacts_payload, companyfacts_counts = sanitize_companyfacts_as_of(
        companyfacts_payload, as_of_date
    )
    sanitized_companyfacts = sanitized / f"{symbol}.json"
    _write_json(sanitized_companyfacts, sanitized_companyfacts_payload)
    sanitized_prices = sanitized / f"{symbol}.csv"
    price_counts = sanitize_price_csv_as_of(raw_prices, sanitized_prices, as_of_date)
    cutoff_counts = {**companyfacts_counts, **price_counts}

    price_dates = _price_dates(sanitized_prices)
    source_registry_path = packets / f"{symbol}_{as_of_date}_source_registry.json"
    retrieved_at = datetime.now(timezone.utc).isoformat()
    save_source_registry(
        SourceRegistry(
            registry_id=f"{symbol}_{as_of_date}",
            sources=[
                SourceRegistryEntry(
                    source_id=f"{symbol}_RETROSPECTIVE_OHLCV",
                    ticker=symbol,
                    source_type="exchange_ohlcv",
                    authority_rank=2,
                    url=None,
                    retrieved_at=retrieved_at,
                    used_for=["price", "volume", "technical_indicators"],
                    owner="hash-bound replay input",
                    source_tier="market_authority",
                    freshness_status="historical_replay",
                )
            ],
        ),
        source_registry_path,
    )
    config = ReportConfig(
        ticker=symbol,
        as_of_date=as_of_date,
        source_mode="source_ingestion_mode",
        batch_mode="historical_guardrail_test",
        freshness_reference_date=as_of_date,
        output_dir=str(outputs),
        packet_dir=str(packets),
        price_csv_dir=str(sanitized),
        price_start_date=price_dates[0],
        price_source_id=f"{symbol}_RETROSPECTIVE_OHLCV",
        price_source_type="exchange_ohlcv",
        price_retrieved_at=retrieved_at,
        cik_records_path=str(copied_cik_records),
        sec_companyfacts_path=str(sanitized_companyfacts),
    )
    run_research_pipeline(symbol, as_of_date, config)
    report_root = outputs / symbol / as_of_date
    authority_manifest = report_root / "authority_bundle" / "authority_manifest.json"
    fact_ledger = report_root / "fact_ledger.json"
    base_snapshot_path = report_root / "valuation_calibration_snapshot.json"
    base_snapshot = ValuationCalibrationSnapshot(
        **json.loads(base_snapshot_path.read_text(encoding="utf-8"))
    )

    artifact_paths = {
        "raw_companyfacts": raw_companyfacts,
        "raw_prices": raw_prices,
        "cik_records": copied_cik_records,
        "sanitized_companyfacts": sanitized_companyfacts,
        "sanitized_prices": sanitized_prices,
        "authority_manifest": authority_manifest,
        "fact_ledger": fact_ledger,
        "base_valuation_snapshot": base_snapshot_path,
    }
    manifest = ValuationCalibrationReplayManifest(
        replay_id=replay_id,
        ticker=symbol,
        as_of_date=as_of_date,
        generated_at=retrieved_at,
        publication_allowed=False,
        pipeline_commit_sha=commit_sha,
        source_cutoff_passed=True,
        cutoff_counts=cutoff_counts,
        artifacts={
            name: RetrospectiveReplayArtifact(
                path=str(path.relative_to(root)), sha256=file_sha256(path)
            )
            for name, path in artifact_paths.items()
        },
    )
    manifest.replay_manifest_sha256 = calculate_replay_manifest_sha256(manifest)
    manifest_path = root / "retrospective_replay_manifest.json"
    _write_json(manifest_path, manifest.model_dump(mode="json"))
    promoted = promote_retrospective_snapshot(base_snapshot, manifest_path)
    promoted_path = report_root / "valuation_calibration_replay_snapshot.json"
    _write_json(promoted_path, promoted.model_dump(mode="json"))
    return _replay_result(
        symbol=symbol,
        as_of_date=as_of_date,
        manifest_path=manifest_path,
        promoted_path=promoted_path,
        promoted=promoted,
        cutoff_counts=cutoff_counts,
    )


def _replay_result(
    *,
    symbol: str,
    as_of_date: str,
    manifest_path: Path,
    promoted_path: Path,
    promoted: ValuationCalibrationSnapshot,
    cutoff_counts: dict[str, int],
) -> dict[str, Any]:
    return {
        "status": "replay_ready" if promoted.eligible else "replay_ineligible",
        "ticker": symbol,
        "as_of_date": as_of_date,
        "publication_allowed": False,
        "replay_manifest_path": str(manifest_path),
        "replay_snapshot_path": str(promoted_path),
        "replay_snapshot_id": promoted.snapshot_id,
        "eligible": promoted.eligible,
        "exclusion_reasons": promoted.exclusion_reasons,
        "cutoff_counts": cutoff_counts,
    }


def _semantic_replay_reasons(root: Path, manifest: ValuationCalibrationReplayManifest) -> list[str]:
    reasons: list[str] = []
    cutoff = date.fromisoformat(manifest.as_of_date)
    artifacts = manifest.artifacts
    companyfacts_path = (root / artifacts["sanitized_companyfacts"].path).resolve()
    payload = json.loads(companyfacts_path.read_text(encoding="utf-8"))
    for row in _companyfacts_rows(payload):
        try:
            if date.fromisoformat(str(row.get("filed") or "")) > cutoff:
                reasons.append("replay_companyfacts_after_cutoff")
        except ValueError:
            reasons.append("replay_companyfacts_filing_date_invalid")
    prices_path = (root / artifacts["sanitized_prices"].path).resolve()
    dates = _price_dates(prices_path)
    if any(date.fromisoformat(day) > cutoff for day in dates):
        reasons.append("replay_price_after_cutoff")
    authority_path = (root / artifacts["authority_manifest"].path).resolve()
    authority = json.loads(authority_path.read_text(encoding="utf-8"))
    if authority.get("ticker") != manifest.ticker:
        reasons.append("replay_authority_ticker_mismatch")
    if authority.get("as_of_date") != manifest.as_of_date:
        reasons.append("replay_authority_date_mismatch")
    if authority.get("analysis_allowed") is not True:
        reasons.append("replay_authority_not_approved")
    snapshot_path = (root / artifacts["base_valuation_snapshot"].path).resolve()
    snapshot = ValuationCalibrationSnapshot(**json.loads(snapshot_path.read_text(encoding="utf-8")))
    if snapshot.ticker != manifest.ticker or snapshot.as_of_date != manifest.as_of_date:
        reasons.append("replay_base_snapshot_identity_mismatch")
    ledger_path = (root / artifacts["fact_ledger"].path).resolve()
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    for claim in ledger.get("claims") or []:
        claim_asof = claim.get("asof")
        try:
            if claim_asof and date.fromisoformat(str(claim_asof)[:10]) > cutoff:
                reasons.append("replay_fact_claim_after_cutoff")
        except ValueError:
            reasons.append("replay_fact_claim_date_invalid")
    return reasons


def _companyfacts_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for taxonomy in (payload.get("facts") or {}).values():
        for concept in (taxonomy or {}).values():
            for unit_rows in (concept.get("units") or {}).values():
                rows.extend(row for row in unit_rows if isinstance(row, dict))
    return rows


def _price_dates(path: Union[str, Path]) -> list[str]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    dates = [str(row.get("date") or "") for row in rows]
    if not dates or any(not day for day in dates):
        raise ValueError("price CSV has no complete date series")
    return sorted(dates)


def _aware_timestamp(value: str) -> bool:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False


def _git_sha(value: str) -> bool:
    return len(value) == 40 and all(character in "0123456789abcdef" for character in value.lower())


def _git_commit(repo_root: Path) -> str:
    dirty = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    if dirty.stdout.strip():
        raise ValueError("retrospective replay requires a clean committed pipeline worktree")
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    commit = completed.stdout.strip()
    if not _git_sha(commit):
        raise ValueError("pipeline git commit is unavailable")
    return commit


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a fail-closed historical point-in-time valuation replay."
    )
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--date", required=True, dest="as_of_date")
    parser.add_argument("--raw-companyfacts", required=True)
    parser.add_argument("--raw-prices", required=True)
    parser.add_argument("--cik-records", required=True)
    parser.add_argument("--replay-root", required=True)
    args = parser.parse_args()
    try:
        result = build_retrospective_replay(
            ticker=args.ticker,
            as_of_date=args.as_of_date,
            raw_companyfacts_path=args.raw_companyfacts,
            raw_prices_path=args.raw_prices,
            cik_records_path=args.cik_records,
            replay_root=args.replay_root,
        )
    except (OSError, RuntimeError, ValueError) as error:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "ticker": args.ticker.strip().upper(),
                    "as_of_date": args.as_of_date,
                    "error": str(error),
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["eligible"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
