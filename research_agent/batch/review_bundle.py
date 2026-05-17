from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path
from typing import Optional

from research_agent.batch.artifact_consistency_validator import (
    update_bundle_manifest,
    validate_bundle_artifacts,
    write_consistency_artifacts,
)

REVIEW_BUNDLE_REQUIRED_FILES = [
    "final_report.md",
    "internal_best_report.md",
    "publish_report.md",
    "quality_score.json",
    "publish_report_quality_score.json",
    "decision_packet.json",
    "audit_report.json",
    "evidence_report.md",
    "reconciliation_report.md",
    "report_manifest.json",
    "metrics_packet.json",
    "canonical_financials.json",
    "reconciliation_warnings.json",
    "source_registry.json",
    "data_packet.json",
    "current_period_reconciliation_summary.md",
]


def create_chatgpt_review_bundle(
    batch_dir: str | Path,
    tickers: list[str],
    output_zip: Optional[str | Path] = None,
) -> Path:
    base = Path(batch_dir)
    dashboard = json.loads((base / "dashboard_status.json").read_text(encoding="utf-8"))
    items = {item["ticker"].upper(): item for item in dashboard.get("items", [])}
    bundle_dir = base / "chatgpt_review_bundle"
    zip_path = Path(output_zip) if output_zip else base / "chatgpt_review_bundle.zip"

    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()

    missing: list[str] = []
    selected = [ticker.upper() for ticker in tickers]
    for ticker in selected:
        item = items.get(ticker)
        if item is None:
            missing.append(f"{ticker}: dashboard item")
            continue
        target_dir = bundle_dir / ticker
        target_dir.mkdir(parents=True, exist_ok=True)
        artifacts = item.get("artifacts") or {}
        for name in REVIEW_BUNDLE_REQUIRED_FILES:
            source = artifacts.get(name)
            if not source or not Path(source).exists():
                missing.append(f"{ticker}: {name}")
                continue
            shutil.copy2(source, target_dir / name)

    for name in ["dashboard_status.json", "pilot_review.md"]:
        source = base / name
        if not source.exists():
            missing.append(name)
        else:
            shutil.copy2(source, bundle_dir / name)

    manifest = {
        "source_batch_id": dashboard.get("batch_id"),
        "selected_tickers": selected,
        "tickers": selected,
        "required_files": REVIEW_BUNDLE_REQUIRED_FILES,
        "missing": missing,
        "all_required_files_present": not missing,
    }
    (bundle_dir / "bundle_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    if missing:
        raise FileNotFoundError("Missing required bundle files: " + "; ".join(missing))

    consistency = validate_bundle_artifacts(bundle_dir)
    write_consistency_artifacts(bundle_dir, consistency)
    update_bundle_manifest(bundle_dir, consistency)
    if consistency.error_count:
        failed_zip_path = zip_path.with_name(f"{zip_path.stem}_FAILED_ARTIFACT_CONSISTENCY{zip_path.suffix}")
        if failed_zip_path.exists():
            failed_zip_path.unlink()
        with zipfile.ZipFile(failed_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(bundle_dir.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(bundle_dir.parent))
        return failed_zip_path

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(bundle_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(bundle_dir.parent))
    return zip_path


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Create a ChatGPT review bundle from a batch output directory.")
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--tickers", required=True, help="Comma-separated ticker list.")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    tickers = [item.strip().upper() for item in args.tickers.split(",") if item.strip()]
    path = create_chatgpt_review_bundle(args.batch_dir, tickers, args.output)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
