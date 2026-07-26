from __future__ import annotations

import io
import json
import re
import urllib.parse
import urllib.request
import warnings
from dataclasses import dataclass
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from typing import Any, Optional
from zoneinfo import ZoneInfo

import pandas as pd

from research_agent.sources.prices.price_provider_base import PriceProviderBase


_MONTH_ENDS = {"MAR": 3, "JUN": 6, "SEP": 9, "DEC": 12}
_ANNUAL_METRICS = {
    "Total revenues": ("revenue", "income_statement"),
    "Operating Profit (EBIT)": ("operating_income", "income_statement"),
    "Profit after tax": ("net_income", "income_statement"),
    "Total assets": ("total_assets", "balance_sheet"),
    "Shareholders equity": ("equity", "balance_sheet"),
}
_INTERIM_METRICS = {
    "Net sales": "revenue",
    "Operating profit (EBIT)": "operating_income",
    "Profit after tax": "net_income",
}


@dataclass(frozen=True)
class BseIssuer:
    ticker: str
    company_name: str
    isin: str
    currency: str
    issuer_id: str
    security_id: str
    profile_url: str


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text:
            self.parts.append(text)

    def text(self) -> str:
        return " ".join(self.parts)


class BseIssuerProvider(PriceProviderBase):
    """Official issuer, financial and OHLCV data from Budapest Stock Exchange."""

    source_type = "exchange_ohlcv"
    source_url = "https://www.bse.hu/pages/company_profile/"

    def __init__(self, *, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds
        self._html_by_ticker: dict[str, str] = {}
        self._issuer_by_ticker: dict[str, Optional[BseIssuer]] = {}

    def resolve(self, ticker: str) -> Optional[BseIssuer]:
        symbol = ticker.strip().upper()
        if symbol in self._issuer_by_ticker:
            return self._issuer_by_ticker[symbol]
        profile_url = (
            "https://www.bse.hu/pages/company_profile/%24security/"
            + urllib.parse.quote(symbol)
        )
        try:
            html = self._fetch(profile_url).decode("utf-8", "replace")
        except Exception:
            self._issuer_by_ticker[symbol] = None
            return None
        text_parser = _TextExtractor()
        text_parser.feed(html)
        page_text = text_parser.text()
        issuer_id = _first_group(r"[?&]issuer=(\d+)", html)
        security_id = _first_group(r"securityId=(\d+)", html)
        official_ticker = _first_group(
            r"Basic Information\s+Ticker\s+([A-Z0-9._-]{1,24})\b",
            page_text,
        )
        isin = _first_group(
            r"(?:Code of security \(ISIN\)|\bISIN)\s*([A-Z]{2}[A-Z0-9]{10})",
            page_text,
        )
        company_name = _first_group(r"Full Name\s+(.+?)\s+Short name", page_text)
        currency = _first_group(r"Currency of trading\s+([A-Z]{3})", page_text)
        if (
            official_ticker != symbol
            or not issuer_id
            or not security_id
            or not isin
            or not company_name
        ):
            self._issuer_by_ticker[symbol] = None
            return None
        issuer = BseIssuer(
            ticker=symbol,
            company_name=company_name,
            isin=isin,
            currency=currency or "HUF",
            issuer_id=issuer_id,
            security_id=security_id,
            profile_url=profile_url,
        )
        self._html_by_ticker[symbol] = html
        self._issuer_by_ticker[symbol] = issuer
        return issuer

    def get_history(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        issuer = self.resolve(ticker)
        if issuer is None:
            raise RuntimeError(f"BSE has no unambiguous listed equity for {ticker}.")
        html = self._html_by_ticker[issuer.ticker]
        marker = f'"SecurityHistoricDataSource;securityId={issuer.security_id}":'
        start_at = html.find(marker)
        if start_at < 0:
            raise RuntimeError(f"BSE historical price payload missing for {issuer.ticker}.")
        payload, _ = json.JSONDecoder().raw_decode(html[start_at + len(marker) :])
        requested_start = date.fromisoformat(start)
        requested_end = date.fromisoformat(end)
        budapest = ZoneInfo("Europe/Budapest")
        rows: list[dict[str, Any]] = []
        for item in payload.get("values") or []:
            if not isinstance(item, list) or len(item) < 7:
                continue
            trading_date = datetime.fromtimestamp(
                float(item[0]) / 1000,
                tz=timezone.utc,
            ).astimezone(budapest).date()
            if not requested_start <= trading_date <= requested_end:
                continue
            if any(value is None for value in item[1:5]):
                continue
            rows.append(
                {
                    "date": trading_date.isoformat(),
                    "open": float(item[1]),
                    "high": float(item[2]),
                    "low": float(item[3]),
                    "close": float(item[4]),
                    "volume": int(round(float(item[6] or 0))),
                    "adjusted_close": float(item[4]),
                }
            )
        if not rows:
            raise RuntimeError(f"BSE returned no usable OHLCV rows for {issuer.ticker}.")
        return pd.DataFrame(rows).drop_duplicates("date").sort_values("date")

    def build_financial_payload(
        self,
        issuer: BseIssuer,
        *,
        as_of_date: str,
        retrieved_at: str,
    ) -> dict[str, Any]:
        as_of = date.fromisoformat(as_of_date)
        annual = self._read_excel(self._annual_url(issuer))
        interim = self._read_excel(self._interim_url(issuer))
        metrics = self._annual_metrics(annual, issuer, as_of)
        metrics.extend(self._quarterly_metrics(interim, issuer, as_of))
        if not any(item["metric_name"] == "revenue" for item in metrics):
            raise RuntimeError(
                f"BSE financial tables contain no usable revenue history for {issuer.ticker}."
            )
        return {
            "company_name": issuer.company_name,
            "text": "",
            "period": "current",
            "source_id": f"BSE_{issuer.ticker}_OFFICIAL_FINANCIALS",
            "source_type": "company_ir",
            "url": issuer.profile_url,
            "retrieved_at": retrieved_at,
            "jurisdiction": "HU",
            "exchange": "Budapest Stock Exchange",
            "isin": issuer.isin,
            "currency": issuer.currency,
            "metrics": metrics,
        }

    def _annual_metrics(
        self,
        frame: pd.DataFrame,
        issuer: BseIssuer,
        as_of: date,
    ) -> list[dict[str, Any]]:
        header_row = _find_row(frame, lambda value: bool(re.search(r"\b20\d{2}\b", value)))
        if header_row is None:
            return []
        year_columns: list[tuple[int, int]] = []
        for column in range(1, frame.shape[1]):
            match = re.search(r"\b(20\d{2})\b", str(frame.iat[header_row, column]))
            if match and int(match.group(1)) <= as_of.year:
                year_columns.append((int(match.group(1)), column))
        if not year_columns:
            return []
        fiscal_year, column = max(year_columns)
        rows_by_label = _rows_by_label(frame)
        metrics: list[dict[str, Any]] = []
        for label, (metric_name, statement_type) in _ANNUAL_METRICS.items():
            row = rows_by_label.get(label)
            if row is None or pd.isna(frame.iat[row, column]):
                continue
            value = float(frame.iat[row, column]) * 1000.0
            metrics.append(
                _metric_row(
                    metric_name=metric_name,
                    value=value,
                    unit=issuer.currency,
                    period=f"FY{fiscal_year}",
                    fiscal_year=fiscal_year,
                    fiscal_period="FY",
                    period_bucket="instant" if statement_type == "balance_sheet" else "annual",
                    start_date=None if statement_type == "balance_sheet" else f"{fiscal_year}-01-01",
                    end_date=f"{fiscal_year}-12-31",
                    statement_type=statement_type,
                    statement=(
                        f"{issuer.ticker} reported {label} of {value:.0f} "
                        f"{issuer.currency} for FY{fiscal_year}."
                    ),
                )
            )
        return metrics

    def _quarterly_metrics(
        self,
        frame: pd.DataFrame,
        issuer: BseIssuer,
        as_of: date,
    ) -> list[dict[str, Any]]:
        header_row = _find_row(frame, lambda value: value.strip() == "Key P&L Figures")
        if header_row is None:
            return []
        cumulative: dict[int, dict[int, int]] = {}
        for column in range(1, frame.shape[1]):
            label = str(frame.iat[header_row, column])
            match = re.search(
                r"Jan\s+(20\d{2})\s*-\s*(Mar|Jun|Sep|Dec)\s+(20\d{2})",
                label,
                re.IGNORECASE,
            )
            if not match or match.group(1) != match.group(3):
                continue
            year = int(match.group(1))
            month = _MONTH_ENDS[match.group(2).upper()]
            cumulative.setdefault(year, {})[month] = column
        rows_by_label = _rows_by_label(frame)
        result: list[dict[str, Any]] = []
        for label, metric_name in _INTERIM_METRICS.items():
            row = rows_by_label.get(label)
            if row is None:
                continue
            quarter_values: list[tuple[date, int, int, float]] = []
            for year, month_columns in cumulative.items():
                previous = 0.0
                for month in (3, 6, 9, 12):
                    column = month_columns.get(month)
                    if column is None or pd.isna(frame.iat[row, column]):
                        continue
                    current = float(frame.iat[row, column]) * 1000.0
                    quarter_value = current if month == 3 else current - previous
                    previous = current
                    end = date(year, month, 31 if month in {3, 12} else 30)
                    if end <= as_of:
                        quarter_values.append((end, year, month, quarter_value))
            for end, year, month, value in sorted(quarter_values)[-4:]:
                start_month = month - 2
                start = date(year, start_month, 1)
                quarter = month // 3
                result.append(
                    _metric_row(
                        metric_name=metric_name,
                        value=value,
                        unit=issuer.currency,
                        period=f"FY{year}_Q{quarter}",
                        fiscal_year=year,
                        fiscal_period=f"Q{quarter}",
                        period_bucket="quarterly",
                        start_date=start.isoformat(),
                        end_date=end.isoformat(),
                        statement_type="income_statement",
                        statement=(
                            f"{issuer.ticker} reported {label} of {value:.0f} "
                            f"{issuer.currency} for FY{year} Q{quarter}."
                        ),
                    )
                )
        return result

    def _read_excel(self, url: str) -> pd.DataFrame:
        content = self._fetch(url)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=UserWarning)
            return pd.read_excel(io.BytesIO(content), header=None)

    def _fetch(self, url: str) -> bytes:
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "User-Agent": "Room16Research/1.0",
            },
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            return response.read()

    @staticmethod
    def _annual_url(issuer: BseIssuer) -> str:
        return (
            f"https://www.bse.hu/pages/company_profile/$security/{issuer.ticker}/"
            f"$rspid0x117770x12/$riOSSZEFOGLALO0x1EVES0x1ADATOK?issuer={issuer.issuer_id}"
        )

    @staticmethod
    def _interim_url(issuer: BseIssuer) -> str:
        return (
            f"https://www.bse.hu/pages/company_profile/$security/{issuer.ticker}/"
            f"$rspid0x117770x12/$riEVKOZI0x1JELENTESEK?issuer={issuer.issuer_id}"
        )


def _first_group(pattern: str, text: str) -> Optional[str]:
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _find_row(frame: pd.DataFrame, predicate) -> Optional[int]:
    for row in range(frame.shape[0]):
        for value in frame.iloc[row].tolist():
            if isinstance(value, str) and predicate(value):
                return row
    return None


def _rows_by_label(frame: pd.DataFrame) -> dict[str, int]:
    result: dict[str, int] = {}
    for row, value in enumerate(frame.iloc[:, 0].tolist()):
        if isinstance(value, str) and value.strip():
            result[value.strip()] = row
    return result


def _metric_row(
    *,
    metric_name: str,
    value: float,
    unit: str,
    period: str,
    fiscal_year: int,
    fiscal_period: str,
    period_bucket: str,
    start_date: Optional[str],
    end_date: str,
    statement_type: str,
    statement: str,
) -> dict[str, Any]:
    return {
        "metric_name": metric_name,
        "value": value,
        "unit": unit,
        "period": period,
        "fiscal_year": fiscal_year,
        "fiscal_period": fiscal_period,
        "period_bucket": period_bucket,
        "start_date": start_date,
        "end_date": end_date,
        "date": end_date,
        "duration_days": (
            (date.fromisoformat(end_date) - date.fromisoformat(start_date)).days + 1
            if start_date
            else None
        ),
        "basis": "gaap",
        "statement_type": statement_type,
        "statement": statement,
        "reconciliation_note": "Official BSE table submitted by the issuer under IFRS.",
    }
