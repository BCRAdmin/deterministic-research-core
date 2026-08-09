from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
import sys
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict

from research_agent.calibration.valuation_calibration import (
    ValuationCalibrationPricePoint,
    ValuationCalibrationSnapshot,
    ValuationCalibrationSourceBundle,
    build_valuation_calibration_outcome,
    calculate_source_bundle_sha256,
    file_sha256,
    source_bundle_invalid_reasons,
)


OUTCOME_WORKBENCH_SCHEMA = "room16.valuation_outcome_workbench@1"
AUTOMATION_REVIEWER_PATTERN = re.compile(
    r"^(?:ai|agent|automation|bot|chatgpt|claude|codex|deepseek|gemini|llm|"
    r"model|openai|room\s*16|system|vega|vivi)(?:\b|[-_])",
    re.IGNORECASE,
)


class ValuationOutcomeWorkbenchStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_id: str = OUTCOME_WORKBENCH_SCHEMA
    mode: Literal["draft", "verified"]
    snapshot_id: str
    ticker: str
    benchmark: str
    source_bundle_path: str
    source_bundle_contract_sha256: str
    source_bundle_file_sha256: str
    outcome_preview_path: str
    review_packet_path: str
    source_contract_valid: bool
    source_contract_reasons: list[str]
    outcome_status: str
    outcome_notes: list[str]
    live_activation_allowed: Literal[False] = False


def load_normalized_price_csv(
    path: Union[str, Path],
) -> list[ValuationCalibrationPricePoint]:
    source = Path(path)
    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not {"date", "close"}.issubset(reader.fieldnames):
            raise ValueError(f"price CSV requires date and close columns: {source}")
        by_date: dict[str, float] = {}
        for row in reader:
            day = str(row.get("date") or "").strip()
            try:
                parsed_day = datetime.strptime(day, "%Y-%m-%d").date()
                if parsed_day.isoformat() != day:
                    raise ValueError
                close = float(str(row.get("close") or "").replace("$", "").replace(",", ""))
            except ValueError as error:
                raise ValueError(f"price CSV contains invalid date or close: {source}") from error
            if not math.isfinite(close) or close <= 0:
                raise ValueError(f"price CSV contains nonpositive or nonfinite close: {source}")
            if day in by_date:
                raise ValueError(f"price CSV contains duplicate date {day}: {source}")
            by_date[day] = close
    if not by_date:
        raise ValueError(f"price CSV contains no observations: {source}")
    return [ValuationCalibrationPricePoint(date=day, close=by_date[day]) for day in sorted(by_date)]


def build_valuation_outcome_workbench(
    *,
    mode: Literal["draft", "verified"],
    snapshot_path: Union[str, Path],
    instrument_series_path: Union[str, Path],
    benchmark_series_path: Union[str, Path],
    provider_id: str,
    provider_dataset_id: str,
    benchmark: str,
    retrieved_at: str,
    instrument_price_series_basis: str,
    benchmark_price_series_basis: str,
    instrument_cash_distributions_included: bool,
    benchmark_cash_distributions_included: bool,
    instrument_corporate_actions_included: bool,
    benchmark_corporate_actions_included: bool,
    provider_methodology_path: Optional[Union[str, Path]],
    usage_rights_evidence_path: Optional[Union[str, Path]],
    verification_evidence_path: Optional[Union[str, Path]],
    prepared_by: Optional[str],
    rights_approved_by: Optional[str],
    rights_approved_at: Optional[str],
    verified_by: Optional[str],
    verified_at: Optional[str],
    approve_internal_calibration_rights: bool,
    confirm_independent_review: bool,
    output_dir: Union[str, Path],
) -> ValuationOutcomeWorkbenchStatus:
    snapshot_file = Path(snapshot_path).resolve()
    instrument_file = Path(instrument_series_path).resolve()
    benchmark_file = Path(benchmark_series_path).resolve()
    _require_nonempty(
        provider_id=provider_id,
        provider_dataset_id=provider_dataset_id,
        benchmark=benchmark,
        instrument_price_series_basis=instrument_price_series_basis,
        benchmark_price_series_basis=benchmark_price_series_basis,
    )
    snapshot = ValuationCalibrationSnapshot(**json.loads(snapshot_file.read_text(encoding="utf-8")))
    instrument_prices = load_normalized_price_csv(instrument_file)
    benchmark_prices = load_normalized_price_csv(benchmark_file)
    if mode == "verified":
        _validate_verified_gate(
            snapshot=snapshot,
            retrieved_at=retrieved_at,
            instrument_price_series_basis=instrument_price_series_basis,
            benchmark_price_series_basis=benchmark_price_series_basis,
            instrument_cash_distributions_included=instrument_cash_distributions_included,
            benchmark_cash_distributions_included=benchmark_cash_distributions_included,
            instrument_corporate_actions_included=instrument_corporate_actions_included,
            benchmark_corporate_actions_included=benchmark_corporate_actions_included,
            provider_methodology_path=provider_methodology_path,
            usage_rights_evidence_path=usage_rights_evidence_path,
            verification_evidence_path=verification_evidence_path,
            prepared_by=prepared_by,
            rights_approved_by=rights_approved_by,
            rights_approved_at=rights_approved_at,
            verified_by=verified_by,
            verified_at=verified_at,
            approve_internal_calibration_rights=approve_internal_calibration_rights,
            confirm_independent_review=confirm_independent_review,
        )
    bundle_created_at = datetime.now(timezone.utc).isoformat()

    target = Path(output_dir).resolve()
    _require_clean_output_target(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{target.name}-building-", dir=target.parent
    ) as temporary:
        staging = Path(temporary)
        evidence_dir = staging / "evidence"
        evidence_dir.mkdir()
        instrument_artifact = _copy_artifact(
            instrument_file, evidence_dir / "instrument_series.csv"
        )
        benchmark_artifact = _copy_artifact(benchmark_file, evidence_dir / "benchmark_series.csv")
        methodology_artifact = _copy_optional_artifact(
            provider_methodology_path,
            evidence_dir / _artifact_name("provider_methodology", provider_methodology_path),
        )
        rights_artifact = _copy_optional_artifact(
            usage_rights_evidence_path,
            evidence_dir / _artifact_name("usage_rights", usage_rights_evidence_path),
        )
        verification_artifact = _copy_optional_artifact(
            verification_evidence_path,
            evidence_dir / _artifact_name("human_verification", verification_evidence_path),
        )

        bundle = ValuationCalibrationSourceBundle(
            snapshot_id=snapshot.snapshot_id,
            provider_id=provider_id.strip(),
            provider_dataset_id=provider_dataset_id.strip(),
            instrument=snapshot.ticker,
            benchmark=benchmark.strip(),
            basis_date=snapshot.price_basis_date,
            retrieved_at=retrieved_at,
            bundle_created_at=bundle_created_at,
            instrument_price_series_basis=instrument_price_series_basis.strip(),
            benchmark_price_series_basis=benchmark_price_series_basis.strip(),
            instrument_cash_distributions_included=instrument_cash_distributions_included,
            benchmark_cash_distributions_included=benchmark_cash_distributions_included,
            instrument_corporate_actions_included=instrument_corporate_actions_included,
            benchmark_corporate_actions_included=benchmark_corporate_actions_included,
            provider_methodology_sha256=_optional_file_sha256(methodology_artifact),
            provider_methodology_path=_relative_artifact_path(methodology_artifact, staging),
            usage_rights_status=(
                "internal_calibration_allowed"
                if mode == "verified" and approve_internal_calibration_rights
                else "unverified"
            ),
            usage_rights_evidence_sha256=_optional_file_sha256(rights_artifact),
            usage_rights_evidence_path=_relative_artifact_path(rights_artifact, staging),
            usage_rights_approved_by=(
                str(rights_approved_by).strip()
                if mode == "verified" and rights_approved_by
                else None
            ),
            usage_rights_approved_at=(rights_approved_at if mode == "verified" else None),
            instrument_source_sha256=file_sha256(instrument_artifact),
            instrument_source_path=_relative_artifact_path(instrument_artifact, staging),
            benchmark_source_sha256=file_sha256(benchmark_artifact),
            benchmark_source_path=_relative_artifact_path(benchmark_artifact, staging),
            prepared_by=str(prepared_by).strip() if prepared_by else None,
            verification_status="human_verified" if mode == "verified" else "unverified",
            verified_by=(str(verified_by).strip() if mode == "verified" and verified_by else None),
            verified_at=verified_at if mode == "verified" else None,
            verification_independent_from_preparation=(
                mode == "verified" and confirm_independent_review
            ),
            verification_evidence_sha256=_optional_file_sha256(verification_artifact),
            verification_evidence_path=_relative_artifact_path(verification_artifact, staging),
            instrument_prices=instrument_prices,
            benchmark_prices=benchmark_prices,
        )
        bundle.source_bundle_sha256 = calculate_source_bundle_sha256(bundle)
        bundle_path = staging / "valuation_calibration_source_bundle.json"
        outcome_path = staging / "valuation_calibration_outcome_preview.json"
        packet_path = staging / "valuation_calibration_review_packet.md"
        status_path = staging / "valuation_calibration_workbench_status.json"
        _write_json(bundle_path, bundle.model_dump(mode="json"))
        reasons = source_bundle_invalid_reasons(snapshot, bundle, bundle_path)
        if mode == "verified" and reasons:
            raise ValueError("verified source contract is invalid: " + ", ".join(reasons))
        outcome = build_valuation_calibration_outcome(snapshot, bundle)
        if not reasons and outcome.status == "invalidated":
            raise RuntimeError("valid source contract produced an invalidated outcome")
        _write_json(outcome_path, outcome.model_dump(mode="json"))
        packet_path.write_text(
            render_outcome_review_packet(
                mode=mode,
                snapshot=snapshot,
                bundle=bundle,
                source_contract_reasons=reasons,
                outcome_status=outcome.status,
                outcome_notes=outcome.notes,
            ),
            encoding="utf-8",
        )
        final_bundle_path = target / bundle_path.name
        final_outcome_path = target / outcome_path.name
        final_packet_path = target / packet_path.name
        status = ValuationOutcomeWorkbenchStatus(
            mode=mode,
            snapshot_id=snapshot.snapshot_id,
            ticker=snapshot.ticker,
            benchmark=bundle.benchmark,
            source_bundle_path=str(final_bundle_path),
            source_bundle_contract_sha256=str(bundle.source_bundle_sha256),
            source_bundle_file_sha256=file_sha256(bundle_path),
            outcome_preview_path=str(final_outcome_path),
            review_packet_path=str(final_packet_path),
            source_contract_valid=not reasons,
            source_contract_reasons=reasons,
            outcome_status=outcome.status,
            outcome_notes=outcome.notes,
        )
        _write_json(status_path, status.model_dump(mode="json"))
        if target.exists():
            target.rmdir()
        staging.rename(target)
    return status


def render_outcome_review_packet(
    *,
    mode: str,
    snapshot: ValuationCalibrationSnapshot,
    bundle: ValuationCalibrationSourceBundle,
    source_contract_reasons: list[str],
    outcome_status: str,
    outcome_notes: list[str],
) -> str:
    blockers = source_contract_reasons or ["keine"]
    blocker_summary = _summarize_blockers(source_contract_reasons)
    notes = (
        ["Ergebnis nicht berechnet, solange der Quellenvertrag blockiert ist."]
        if source_contract_reasons
        and sorted(set(source_contract_reasons)) == sorted(set(outcome_notes))
        else outcome_notes or ["keine"]
    )
    return "\n".join(
        [
            "# Room16-Prüfpaket für Bewertungsergebnisse",
            "",
            f"- Modus: `{mode}`",
            f"- Ticker: `{snapshot.ticker}`",
            f"- Snapshot: `{snapshot.snapshot_id}`",
            f"- Bewertungsstichtag: `{snapshot.price_basis_date}`",
            f"- Benchmark: `{bundle.benchmark}`",
            f"- Anbieter: `{bundle.provider_id}` / `{bundle.provider_dataset_id}`",
            f"- Aufbereitet durch: `{bundle.prepared_by or 'nicht angegeben'}`",
            f"- Rechte freigegeben durch: `{bundle.usage_rights_approved_by or 'nicht freigegeben'}`",
            f"- Geprüft durch: `{bundle.verified_by or 'nicht geprüft'}`",
            f"- Unabhängige Prüfung: `{str(bundle.verification_independent_from_preparation).lower()}`",
            f"- Quellenpaket: `{bundle.source_bundle_sha256}`",
            f"- Ergebnisstatus: `{outcome_status}`",
            "- Live-Aktivierung erlaubt: `false`",
            "",
            "## Blocker des Quellenvertrags",
            "",
            *[f"- {summary}" for summary in blocker_summary],
            "",
            "## Maschinenlesbare Gründe",
            "",
            *[f"- `{reason}`" for reason in blockers],
            "",
            "## Hinweise zum Ergebnis",
            "",
            *[f"- `{note}`" for note in notes],
            "",
            "## Grenze der menschlichen Prüfung",
            "",
            "Die Workbench bindet die vom Operator bereitgestellten Nachweise. Sie entscheidet "
            "nicht selbst, ob Nutzungsrechte, Dividendenbehandlung, Kapitalmaßnahmen oder "
            "menschliche Prüfung inhaltlich zutreffen. Der verifizierte Modus verlangt dafür "
            "separate Nachweisdateien, eine ausdrückliche Rechtefreigabe und eine identifizierte "
            "menschliche Prüfung, die nicht von derselben Identität wie die Aufbereitung stammt.",
            "",
        ]
    )


def _summarize_blockers(reasons: list[str]) -> list[str]:
    if not reasons:
        return ["Keine Blocker; der Quellenvertrag ist vollständig."]
    reason_set = set(reasons)
    summaries: list[str] = []
    if reason_set.intersection(
        {
            "instrument_total_return_adjustment_not_verified",
            "benchmark_total_return_adjustment_not_verified",
            "instrument_cash_distributions_not_verified",
            "benchmark_cash_distributions_not_verified",
            "instrument_corporate_actions_not_verified",
            "benchmark_corporate_actions_not_verified",
        }
    ):
        summaries.append(
            "Die Kursreihen sind nicht als vollständige Total-Return-Reihen einschließlich "
            "Dividenden und Kapitalmaßnahmen nachgewiesen."
        )
    if reason_set.intersection(
        {"provider_methodology_artifact_path_invalid", "provider_methodology_hash_invalid"}
    ):
        summaries.append("Die Methodik des Datenanbieters ist nicht belegt.")
    if any("usage_rights" in reason for reason in reason_set):
        summaries.append(
            "Nutzungsrecht, Nachweis, menschliche Freigabe oder Freigabezeitpunkt fehlen."
        )
    if reason_set.intersection(
        {
            "source_bundle_human_verification_missing",
            "source_bundle_independent_verification_missing",
            "source_bundle_verified_at_invalid",
            "source_bundle_verified_by_missing",
            "verification_evidence_artifact_path_invalid",
            "verification_evidence_hash_invalid",
        }
    ):
        summaries.append("Eine unabhängige menschliche Datenprüfung ist nicht belegt.")
    covered_tokens = (
        "total_return",
        "cash_distributions",
        "corporate_actions",
        "provider_methodology",
        "usage_rights",
        "human_verification",
        "independent_verification",
        "verified_at",
        "verified_by",
        "verification_evidence",
    )
    if any(not any(token in reason for token in covered_tokens) for reason in reason_set):
        summaries.append("Weitere technische Quellenvertragsfehler stehen in der Codeliste.")
    return summaries


def _validate_verified_gate(
    *,
    snapshot: ValuationCalibrationSnapshot,
    retrieved_at: str,
    instrument_price_series_basis: str,
    benchmark_price_series_basis: str,
    instrument_cash_distributions_included: bool,
    benchmark_cash_distributions_included: bool,
    instrument_corporate_actions_included: bool,
    benchmark_corporate_actions_included: bool,
    provider_methodology_path: Optional[Union[str, Path]],
    usage_rights_evidence_path: Optional[Union[str, Path]],
    verification_evidence_path: Optional[Union[str, Path]],
    prepared_by: Optional[str],
    rights_approved_by: Optional[str],
    rights_approved_at: Optional[str],
    verified_by: Optional[str],
    verified_at: Optional[str],
    approve_internal_calibration_rights: bool,
    confirm_independent_review: bool,
) -> None:
    if not snapshot.eligible:
        raise ValueError("verified mode requires an eligible valuation snapshot")
    if not approve_internal_calibration_rights:
        raise ValueError("verified mode requires explicit internal-calibration rights approval")
    if instrument_price_series_basis != "total_return_adjusted":
        raise ValueError("verified instrument series must be total_return_adjusted")
    if benchmark_price_series_basis != "total_return_adjusted":
        raise ValueError("verified benchmark series must be total_return_adjusted")
    if not all(
        [
            instrument_cash_distributions_included,
            benchmark_cash_distributions_included,
            instrument_corporate_actions_included,
            benchmark_corporate_actions_included,
        ]
    ):
        raise ValueError("verified mode requires all distribution and corporate-action assurances")
    evidence_paths = {
        "provider methodology": provider_methodology_path,
        "usage rights": usage_rights_evidence_path,
        "human verification": verification_evidence_path,
    }
    for label, evidence_path in evidence_paths.items():
        if evidence_path is None or not Path(evidence_path).is_file():
            raise ValueError(f"verified mode requires {label} evidence")
    verification_path = Path(str(verification_evidence_path)).resolve()
    if verification_path in {
        Path(str(provider_methodology_path)).resolve(),
        Path(str(usage_rights_evidence_path)).resolve(),
    }:
        raise ValueError("human verification evidence must be a separate artifact")
    preparer = str(prepared_by or "").strip()
    reviewer = str(verified_by or "").strip()
    rights_approver = str(rights_approved_by or "").strip()
    if not preparer:
        raise ValueError("verified mode requires an identified preparer")
    if not reviewer:
        raise ValueError("verified mode requires an identified human reviewer")
    if AUTOMATION_REVIEWER_PATTERN.search(reviewer):
        raise ValueError("automation or model identities cannot satisfy human verification")
    if not rights_approver:
        raise ValueError("verified mode requires an identified human rights approver")
    if AUTOMATION_REVIEWER_PATTERN.search(rights_approver):
        raise ValueError("automation or model identities cannot approve usage rights")
    if not confirm_independent_review:
        raise ValueError("verified mode requires explicit independent-review confirmation")
    if _normalized_identity(preparer) == _normalized_identity(reviewer):
        raise ValueError("human reviewer must be independent from the preparer")
    retrieved = _aware_datetime(retrieved_at, "retrieved_at")
    rights_approved = _aware_datetime(str(rights_approved_at or ""), "rights_approved_at")
    verified = _aware_datetime(str(verified_at or ""), "verified_at")
    if verified < retrieved:
        raise ValueError("verified_at must not be before retrieved_at")
    if verified < rights_approved:
        raise ValueError("verified_at must not be before rights_approved_at")


def _require_nonempty(**values: str) -> None:
    missing = sorted(name for name, value in values.items() if not str(value).strip())
    if missing:
        raise ValueError("required values are empty: " + ", ".join(missing))


def _require_clean_output_target(target: Path) -> None:
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise FileExistsError(f"output directory already exists and is not empty: {target}")


def _artifact_name(label: str, path: Optional[Union[str, Path]]) -> str:
    suffix = Path(str(path)).suffix.lower() if path is not None else ""
    return label + (suffix if suffix else ".bin")


def _copy_artifact(source: Union[str, Path], target: Path) -> Path:
    source_path = Path(source)
    if not source_path.is_file():
        raise FileNotFoundError(f"source artifact does not exist: {source_path}")
    shutil.copy2(source_path, target)
    return target


def _copy_optional_artifact(source: Optional[Union[str, Path]], target: Path) -> Optional[Path]:
    return _copy_artifact(source, target) if source is not None else None


def _relative_artifact_path(path: Optional[Path], root: Path) -> Optional[str]:
    return path.relative_to(root).as_posix() if path is not None else None


def _aware_datetime(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} must be a valid ISO timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def _normalized_identity(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return re.sub(r"[^a-z0-9]+", "", decomposed.encode("ascii", "ignore").decode())


def _optional_file_sha256(path: Optional[Path]) -> Optional[str]:
    return file_sha256(path) if path is not None and path.is_file() else None


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _add_boolean_flag(parser: argparse.ArgumentParser, name: str, help_text: str) -> None:
    parser.add_argument(name, action="store_true", help=help_text)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a reviewable Room16 valuation total-return outcome bundle."
    )
    parser.add_argument("--mode", choices=["draft", "verified"], default="draft")
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--instrument-series", required=True)
    parser.add_argument("--benchmark-series", required=True)
    parser.add_argument("--provider-id", required=True)
    parser.add_argument("--provider-dataset-id", required=True)
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--retrieved-at", required=True)
    parser.add_argument("--instrument-series-basis", required=True)
    parser.add_argument("--benchmark-series-basis", required=True)
    _add_boolean_flag(
        parser,
        "--instrument-cash-distributions-included",
        "Confirm that instrument cash distributions are included.",
    )
    _add_boolean_flag(
        parser,
        "--benchmark-cash-distributions-included",
        "Confirm that benchmark cash distributions are included.",
    )
    _add_boolean_flag(
        parser,
        "--instrument-corporate-actions-included",
        "Confirm that instrument corporate actions are included.",
    )
    _add_boolean_flag(
        parser,
        "--benchmark-corporate-actions-included",
        "Confirm that benchmark corporate actions are included.",
    )
    parser.add_argument("--provider-methodology-evidence")
    parser.add_argument("--usage-rights-evidence")
    parser.add_argument("--verification-evidence")
    parser.add_argument("--prepared-by")
    parser.add_argument("--rights-approved-by")
    parser.add_argument("--rights-approved-at")
    parser.add_argument("--verified-by")
    parser.add_argument("--verified-at")
    _add_boolean_flag(
        parser,
        "--approve-internal-calibration-rights",
        "Record an operator-approved internal calibration usage-rights decision.",
    )
    _add_boolean_flag(
        parser,
        "--confirm-independent-review",
        "Confirm that the human reviewer is independent from data preparation.",
    )
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    try:
        status = build_valuation_outcome_workbench(
            mode=args.mode,
            snapshot_path=args.snapshot,
            instrument_series_path=args.instrument_series,
            benchmark_series_path=args.benchmark_series,
            provider_id=args.provider_id,
            provider_dataset_id=args.provider_dataset_id,
            benchmark=args.benchmark,
            retrieved_at=args.retrieved_at,
            instrument_price_series_basis=args.instrument_series_basis,
            benchmark_price_series_basis=args.benchmark_series_basis,
            instrument_cash_distributions_included=(args.instrument_cash_distributions_included),
            benchmark_cash_distributions_included=(args.benchmark_cash_distributions_included),
            instrument_corporate_actions_included=(args.instrument_corporate_actions_included),
            benchmark_corporate_actions_included=(args.benchmark_corporate_actions_included),
            provider_methodology_path=args.provider_methodology_evidence,
            usage_rights_evidence_path=args.usage_rights_evidence,
            verification_evidence_path=args.verification_evidence,
            prepared_by=args.prepared_by,
            rights_approved_by=args.rights_approved_by,
            rights_approved_at=args.rights_approved_at,
            verified_by=args.verified_by,
            verified_at=args.verified_at,
            approve_internal_calibration_rights=(args.approve_internal_calibration_rights),
            confirm_independent_review=args.confirm_independent_review,
            output_dir=args.output_dir,
        )
    except (OSError, RuntimeError, ValueError) as error:
        print(json.dumps({"status": "blocked", "error": str(error)}), file=sys.stderr)
        return 2
    print(status.model_dump_json(indent=2))
    return 0 if args.mode == "draft" or status.source_contract_valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
