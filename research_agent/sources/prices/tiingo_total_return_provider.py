from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import sys
import tempfile
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from research_agent.sources.prices.price_provider_base import PriceProviderBase


class TiingoTotalReturnProvider(PriceProviderBase):
    """Dormant Tiingo EOD candidate for evidence-bound total-return calibration."""

    provider_id = "tiingo"
    provider_dataset_id = "tiingo_eod_adjusted_crsp_methodology"
    source_type = "licensed_total_return_candidate"
    source_url = "https://api.tiingo.com/tiingo/daily"
    methodology_url = "https://www.tiingo.com/documentation/end-of-day"
    license_url = "https://www.tiingo.com/documentation/general"
    pricing_url = "https://www.tiingo.com/about/pricing"
    series_basis = "total_return_adjusted"
    cash_distributions_included = True
    corporate_actions_included = True
    token_environment_variable = "TIINGO_API_TOKEN"

    def __init__(
        self,
        api_token: str,
        *,
        base_url: str = "https://api.tiingo.com",
        timeout_seconds: int = 30,
    ):
        if not api_token.strip():
            raise ValueError("Tiingo API token is required.")
        self._api_token = api_token.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_environment(
        cls,
        *,
        base_url: str = "https://api.tiingo.com",
        timeout_seconds: int = 30,
    ) -> "TiingoTotalReturnProvider":
        token = os.environ.get(cls.token_environment_variable, "")
        if not token.strip():
            raise ValueError(
                f"{cls.token_environment_variable} is not configured; Tiingo remains disabled."
            )
        return cls(
            token,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )

    def get_history(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        symbol = _validated_symbol(ticker)
        start_date = _iso_date(start, "start")
        end_date = _iso_date(end, "end")
        if start_date > end_date:
            raise ValueError("Tiingo price range start must not be after end.")
        query = urllib.parse.urlencode(
            {
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "resampleFreq": "daily",
                "format": "json",
            }
        )
        url = f"{self.base_url}/tiingo/daily/{urllib.parse.quote(symbol)}/prices?{query}"
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Token {self._api_token}",
                "User-Agent": "Room16Research/1.0",
            },
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, list):
            detail = payload.get("detail") if isinstance(payload, dict) else None
            raise RuntimeError(
                f"Tiingo returned no usable EOD rows for {symbol}"
                + (f": {detail}" if detail else ".")
            )

        rows: list[dict[str, object]] = []
        seen_dates: set[str] = set()
        for item in payload:
            if not isinstance(item, dict):
                raise RuntimeError(f"Tiingo returned a non-object EOD row for {symbol}.")
            day = _tiingo_date(item.get("date"))
            if day < start_date or day > end_date:
                raise RuntimeError(f"Tiingo returned an out-of-range EOD row for {symbol}.")
            day_string = day.isoformat()
            if day_string in seen_dates:
                raise RuntimeError(f"Tiingo returned duplicate EOD date {day_string} for {symbol}.")
            seen_dates.add(day_string)
            raw_ohlc = {
                "open": _positive_number(item, "open"),
                "high": _positive_number(item, "high"),
                "low": _positive_number(item, "low"),
                "close": _positive_number(item, "close"),
            }
            adjusted_ohlc = {
                "open": _positive_number(item, "adjOpen"),
                "high": _positive_number(item, "adjHigh"),
                "low": _positive_number(item, "adjLow"),
                "close": _positive_number(item, "adjClose"),
            }
            _validate_ohlc(raw_ohlc, "raw")
            _validate_ohlc(adjusted_ohlc, "adjusted")
            row = {
                "date": day_string,
                **raw_ohlc,
                "volume": _nonnegative_number(item, "volume"),
                "adjusted_open": adjusted_ohlc["open"],
                "adjusted_high": adjusted_ohlc["high"],
                "adjusted_low": adjusted_ohlc["low"],
                "adjusted_close": adjusted_ohlc["close"],
                "adjusted_volume": _nonnegative_number(item, "adjVolume"),
                "cash_distribution": _nonnegative_number(item, "divCash"),
                "split_factor": _positive_number(item, "splitFactor"),
            }
            rows.append(row)
        if not rows:
            raise RuntimeError(f"Tiingo returned no usable EOD rows for {symbol}.")
        return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)

    def get_total_return_series(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        history = self.get_history(ticker, start, end)
        return history.loc[:, ["date", "adjusted_close"]].rename(
            columns={"adjusted_close": "close"}
        )

    @classmethod
    def outcome_contract_metadata(cls) -> dict[str, object]:
        return {
            "provider_id": cls.provider_id,
            "provider_dataset_id": cls.provider_dataset_id,
            "series_basis": cls.series_basis,
            "cash_distributions_included": cls.cash_distributions_included,
            "corporate_actions_included": cls.corporate_actions_included,
            "methodology_url": cls.methodology_url,
            "license_url": cls.license_url,
            "pricing_url": cls.pricing_url,
            "activation_status": "operator_purchase_and_rights_evidence_required",
        }


def _validated_symbol(value: str) -> str:
    symbol = value.strip().upper()
    if not re.fullmatch(r"[A-Z0-9-]{1,24}", symbol):
        raise ValueError("Tiingo ticker is missing or invalid.")
    return symbol


def _iso_date(value: str, field: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"Tiingo {field} date must use YYYY-MM-DD.") from error
    if parsed.isoformat() != value:
        raise ValueError(f"Tiingo {field} date must use YYYY-MM-DD.")
    return parsed


def _tiingo_date(value: object) -> date:
    raw = str(value or "")
    if len(raw) < 10:
        raise RuntimeError("Tiingo EOD row has no valid date.")
    try:
        parsed = date.fromisoformat(raw[:10])
    except ValueError as error:
        raise RuntimeError("Tiingo EOD row has no valid date.") from error
    return parsed


def _positive_number(item: dict[str, object], field: str) -> float:
    value = _number(item, field)
    if value <= 0:
        raise RuntimeError(f"Tiingo EOD row has nonpositive {field}.")
    return value


def _nonnegative_number(item: dict[str, object], field: str) -> float:
    value = _number(item, field)
    if value < 0:
        raise RuntimeError(f"Tiingo EOD row has negative {field}.")
    return value


def _number(item: dict[str, object], field: str) -> float:
    try:
        value = float(item[field])
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError(f"Tiingo EOD row has no numeric {field}.") from error
    if not math.isfinite(value):
        raise RuntimeError(f"Tiingo EOD row has nonfinite {field}.")
    return value


def _validate_ohlc(values: dict[str, float], label: str) -> None:
    if values["high"] < max(values["open"], values["low"], values["close"]):
        raise RuntimeError(f"Tiingo EOD row has inconsistent {label} high.")
    if values["low"] > min(values["open"], values["high"], values["close"]):
        raise RuntimeError(f"Tiingo EOD row has inconsistent {label} low.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run an explicitly gated Tiingo total-return candidate probe."
    )
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Create one new atomic candidate directory containing prices and provenance.",
    )
    parser.add_argument(
        "--confirm-paid-provider",
        action="store_true",
        help="Confirm that this command may consume a paid commercial provider request.",
    )
    args = parser.parse_args()
    if not args.confirm_paid_provider:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "reason": "explicit_paid_provider_confirmation_required",
                }
            ),
            file=sys.stderr,
        )
        return 2
    target = Path(args.output_dir).expanduser().resolve()
    if target.exists():
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "reason": "output_target_already_exists",
                    "output_dir": str(target),
                }
            ),
            file=sys.stderr,
        )
        return 2
    if not target.parent.is_dir():
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "reason": "output_parent_must_already_exist",
                    "output_parent": str(target.parent),
                }
            ),
            file=sys.stderr,
        )
        return 2
    temporary_dir = None
    try:
        provider = TiingoTotalReturnProvider.from_environment()
        frame = provider.get_total_return_series(args.ticker, args.start, args.end)
        if frame.empty or list(frame.columns) != ["date", "close"]:
            raise RuntimeError("Tiingo candidate series has an invalid normalized shape.")
        temporary_dir = Path(
            tempfile.mkdtemp(prefix=".tiingo-candidate-building-", dir=target.parent)
        )
        prices_path = temporary_dir / "prices.csv"
        with prices_path.open("w", encoding="utf-8", newline="") as handle:
            frame.to_csv(handle, index=False)
        with prices_path.open("rb") as handle:
            digest = "sha256:" + hashlib.sha256(handle.read()).hexdigest()
        receipt = {
            "schema_version": "room16.provider_price_candidate@1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "candidate_downloaded",
            "provider_id": TiingoTotalReturnProvider.provider_id,
            "provider_dataset_id": TiingoTotalReturnProvider.provider_dataset_id,
            "ticker": args.ticker.strip().upper(),
            "requested_start": args.start,
            "requested_end": args.end,
            "rows": len(frame),
            "first_date": str(frame.iloc[0]["date"]),
            "last_date": str(frame.iloc[-1]["date"]),
            "series_basis": TiingoTotalReturnProvider.series_basis,
            "cash_distributions_included": (TiingoTotalReturnProvider.cash_distributions_included),
            "corporate_actions_included": (TiingoTotalReturnProvider.corporate_actions_included),
            "data_file": "prices.csv",
            "data_sha256": digest,
            "source_url": TiingoTotalReturnProvider.source_url,
            "methodology_url": TiingoTotalReturnProvider.methodology_url,
            "license_url": TiingoTotalReturnProvider.license_url,
            "pricing_url": TiingoTotalReturnProvider.pricing_url,
            "rights_verification_status": "operator_evidence_still_required",
            "live_activation_allowed": False,
        }
        receipt_path = temporary_dir / "provider_receipt.json"
        receipt_path.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_dir, target)
        temporary_dir = None
    except (OSError, RuntimeError, ValueError) as error:
        if temporary_dir and temporary_dir.exists():
            shutil.rmtree(temporary_dir)
        print(json.dumps({"status": "blocked", "error": str(error)}), file=sys.stderr)
        return 2
    receipt["output_dir"] = str(target)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
