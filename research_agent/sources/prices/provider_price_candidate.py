from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import date, datetime
from pathlib import Path
from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict


PROVIDER_PRICE_CANDIDATE_SCHEMA = "room16.provider_price_candidate@1"


class ProviderPriceCandidateReceipt(BaseModel):
    """Provider-neutral, non-live provenance for one normalized price series."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[PROVIDER_PRICE_CANDIDATE_SCHEMA] = PROVIDER_PRICE_CANDIDATE_SCHEMA
    created_at: str
    status: Literal["candidate_downloaded"] = "candidate_downloaded"
    provider_id: str
    provider_dataset_id: str
    ticker: str
    requested_start: str
    requested_end: str
    rows: int
    first_date: str
    last_date: str
    series_basis: str
    cash_distributions_included: bool
    corporate_actions_included: bool
    data_file: str
    data_sha256: str
    source_url: str
    methodology_url: str
    license_url: str
    pricing_url: str
    rights_verification_status: Literal["operator_evidence_still_required"] = (
        "operator_evidence_still_required"
    )
    live_activation_allowed: Literal[False] = False


def load_provider_price_candidate(
    receipt_path: Union[str, Path],
    *,
    expected_series_path: Optional[Union[str, Path]] = None,
) -> ProviderPriceCandidateReceipt:
    """Load and fail closed on any receipt-to-series provenance mismatch."""

    source = Path(receipt_path).resolve()
    if not source.is_file():
        raise ValueError(f"provider receipt is not a file: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"provider receipt is not valid JSON: {source}") from error
    receipt = ProviderPriceCandidateReceipt(**payload)
    _require_nonempty_receipt_fields(receipt)

    created_at = _aware_datetime(receipt.created_at, "created_at")
    requested_start = _iso_date(receipt.requested_start, "requested_start")
    requested_end = _iso_date(receipt.requested_end, "requested_end")
    first_date = _iso_date(receipt.first_date, "first_date")
    last_date = _iso_date(receipt.last_date, "last_date")
    if requested_start > requested_end:
        raise ValueError("provider receipt requested_start is after requested_end")
    if first_date > last_date:
        raise ValueError("provider receipt first_date is after last_date")
    if first_date < requested_start or last_date > requested_end:
        raise ValueError("provider receipt observations exceed the requested range")
    if created_at.date() < last_date:
        raise ValueError("provider receipt predates its last observation")
    if receipt.rows <= 0:
        raise ValueError("provider receipt rows must be positive")

    relative_data_path = Path(receipt.data_file)
    if (
        relative_data_path.is_absolute()
        or len(relative_data_path.parts) != 1
        or relative_data_path.name in {"", ".", ".."}
    ):
        raise ValueError("provider receipt data_file must be one safe relative filename")
    data_path = (source.parent / relative_data_path).resolve()
    if data_path.parent != source.parent or not data_path.is_file():
        raise ValueError("provider receipt data_file is missing or escapes its candidate directory")
    if expected_series_path is not None and data_path != Path(expected_series_path).resolve():
        raise ValueError("provider receipt does not bind the supplied price series")
    if not _is_sha256(receipt.data_sha256) or _file_sha256(data_path) != receipt.data_sha256:
        raise ValueError("provider receipt data hash does not match the supplied price series")

    observation_dates = _validated_normalized_price_dates(data_path)
    if receipt.rows != len(observation_dates):
        raise ValueError("provider receipt row count does not match the supplied price series")
    if receipt.first_date != observation_dates[0].isoformat():
        raise ValueError("provider receipt first_date does not match the supplied price series")
    if receipt.last_date != observation_dates[-1].isoformat():
        raise ValueError("provider receipt last_date does not match the supplied price series")
    for field in ("source_url", "methodology_url", "license_url", "pricing_url"):
        if not str(getattr(receipt, field)).startswith("https://"):
            raise ValueError(f"provider receipt {field} must use HTTPS")
    return receipt


def _validated_normalized_price_dates(path: Path) -> list[date]:
    dates: list[date] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["date", "close"]:
            raise ValueError("provider candidate price CSV must contain exactly date and close")
        for row in reader:
            raw_date = str(row.get("date") or "")
            parsed_date = _iso_date(raw_date, "price date")
            if raw_date in seen:
                raise ValueError("provider candidate price CSV contains a duplicate date")
            seen.add(raw_date)
            try:
                close = float(str(row.get("close") or ""))
            except ValueError as error:
                raise ValueError(
                    "provider candidate price CSV contains an invalid close"
                ) from error
            if not math.isfinite(close) or close <= 0:
                raise ValueError("provider candidate price CSV contains an invalid close")
            dates.append(parsed_date)
    if not dates:
        raise ValueError("provider candidate price CSV contains no observations")
    if dates != sorted(dates):
        raise ValueError("provider candidate price CSV is not ordered by date")
    return dates


def _require_nonempty_receipt_fields(receipt: ProviderPriceCandidateReceipt) -> None:
    fields = (
        "provider_id",
        "provider_dataset_id",
        "ticker",
        "series_basis",
        "data_file",
        "data_sha256",
        "source_url",
        "methodology_url",
        "license_url",
        "pricing_url",
    )
    empty = [field for field in fields if not str(getattr(receipt, field)).strip()]
    if empty:
        raise ValueError("provider receipt contains empty fields: " + ", ".join(empty))


def _aware_datetime(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"provider receipt {field} is not a valid timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"provider receipt {field} must include a timezone")
    return parsed


def _iso_date(value: str, field: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"provider receipt {field} is not a valid ISO date") from error
    if parsed.isoformat() != value:
        raise ValueError(f"provider receipt {field} is not a canonical ISO date")
    return parsed


def _file_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _is_sha256(value: str) -> bool:
    normalized = value.removeprefix("sha256:")
    return len(normalized) == 64 and all(
        character in "0123456789abcdef" for character in normalized.lower()
    )
