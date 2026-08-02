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
from pypdf import PdfReader

from research_agent.sources.prices.price_provider_base import PriceProviderBase


_MONTH_ENDS = {"MAR": 3, "JUN": 6, "SEP": 9, "DEC": 12}
_ANNUAL_METRICS = {
    "Total revenues": ("revenue", "income_statement"),
    "Operating Profit (EBIT)": ("operating_income", "income_statement"),
    "Profit after tax": ("net_income", "income_statement"),
    "Total assets": ("total_assets", "balance_sheet"),
    "Shareholders equity": ("equity", "balance_sheet"),
    "Earnings per Share (EPS)": ("eps_diluted", "income_statement"),
}
_INTERIM_METRICS = {
    "Net sales": "revenue",
    "Operating profit (EBIT)": "operating_income",
    "Profit after tax": "net_income",
}
_BSE_FINANCIAL_RISK_HEADINGS = (
    "Foreign currency risk",
    "Interest rate risk",
    "Liquidity risk",
    "Credit risk",
)


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


def _html_text(fragment: str) -> str:
    parser = _TextExtractor()
    parser.feed(fragment)
    return parser.text()


def _profile_business_activity(html: str) -> Optional[str]:
    match = re.search(
        r"<td[^>]*>\s*Business activity\s*</td>\s*<td[^>]*>(.*?)</td>",
        html,
        re.IGNORECASE | re.DOTALL,
    )
    return _html_text(match.group(1)).strip() if match else None


def _qualitative_business_summary(activity: Optional[str]) -> Optional[str]:
    if not activity:
        return None
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", activity)
        if len(sentence.strip()) >= 40
        and not any(character.isdigit() for character in sentence)
    ]
    if not sentences:
        return None
    return (
        "The BSE issuer profile describes the business as follows: "
        f"{sentences[0]}"
    )[:800].strip()


def _bse_publications(html: str, *, as_of_date: str) -> list[dict[str, str]]:
    tab_start = html.find('id="cp_tab_content_5"')
    tab_end = html.find('id="cp_tab_content_6"', tab_start + 1)
    if tab_start < 0 or tab_end < 0:
        return []
    as_of = date.fromisoformat(as_of_date)
    publications: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for row in re.findall(
        r"<tr[^>]*>(.*?)</tr>",
        html[tab_start:tab_end],
        re.IGNORECASE | re.DOTALL,
    ):
        date_match = re.search(
            r"<span[^>]*>\s*(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})",
            row,
            re.IGNORECASE,
        )
        link_match = re.search(
            r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
            row,
            re.IGNORECASE | re.DOTALL,
        )
        if not date_match or not link_match:
            continue
        month = {
            "jan": 1,
            "feb": 2,
            "mar": 3,
            "apr": 4,
            "may": 5,
            "jun": 6,
            "jul": 7,
            "aug": 8,
            "sep": 9,
            "oct": 10,
            "nov": 11,
            "dec": 12,
        }.get(date_match.group(2).lower())
        if month is None:
            continue
        published = date(
            int(date_match.group(3)),
            month,
            int(date_match.group(1)),
        )
        if published > as_of:
            continue
        url = urllib.parse.urljoin("https://www.bse.hu", link_match.group(1))
        if url in seen_urls:
            continue
        headline = _html_text(link_match.group(2)).strip()
        if not headline:
            continue
        seen_urls.add(url)
        publications.append(
            {
                "date": published.isoformat(),
                "headline": headline,
                "url": url,
            }
        )
    return sorted(publications, key=lambda item: item["date"], reverse=True)


def _bse_publication_type(headline: str) -> str:
    text = headline.lower()
    if "dividend" in text:
        return "dividend"
    if "voting rights" in text or "share capital" in text:
        return "capital_structure"
    if "quarter" in text or "half-year" in text:
        return "earnings_results"
    if "annual report" in text:
        return "filing"
    if "governance" in text or "general meeting" in text:
        return "governance"
    if "corporate action timetable" in text:
        return "calendar"
    return "issuer_publication"


def _bse_financial_risk_disclosures(text: str) -> list[dict[str, str]]:
    normalized = " ".join(text.split())
    section = None
    for match in re.finditer(r"(?:\d+\s+)?Risk management", normalized, re.IGNORECASE):
        candidate = normalized[match.end() : match.end() + 20_000]
        if re.search(
            re.escape(_BSE_FINANCIAL_RISK_HEADINGS[0]),
            candidate[:700],
            re.IGNORECASE,
        ):
            section = candidate
            break
    if section is None:
        return []

    headings: list[tuple[int, int, str]] = []
    for heading in _BSE_FINANCIAL_RISK_HEADINGS:
        match = re.search(re.escape(heading), section, re.IGNORECASE)
        if match:
            headings.append((match.start(), match.end(), heading))
    headings.sort()

    disclosures: list[dict[str, str]] = []
    for index, (_start, body_start, heading) in enumerate(headings):
        body_end = headings[index + 1][0] if index + 1 < len(headings) else len(section)
        body = section[body_start:body_end]
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", body)
            if 50 <= len(sentence.strip()) <= 600
            and not any(character.isdigit() for character in sentence)
            and sum(character.isalpha() for character in sentence) >= 30
        ]
        if not sentences:
            continue
        disclosures.append(
            {
                "risk_type": heading,
                "statement": f"{heading}: {' '.join(sentences[:2])}"[:1_200],
            }
        )
    return disclosures


class BseIssuerProvider(PriceProviderBase):
    """Official issuer, financial and OHLCV data from Budapest Stock Exchange."""

    source_type = "exchange_ohlcv"
    source_url = "https://www.bse.hu/pages/company_profile/"

    def __init__(self, *, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds
        self._html_by_ticker: dict[str, str] = {}
        self._issuer_by_ticker: dict[str, Optional[BseIssuer]] = {}
        self._pdf_text_by_detail_url: dict[str, str] = {}

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
        frame = pd.DataFrame(rows).drop_duplicates("date").sort_values("date")
        actions = self._corporate_actions(issuer)
        frame = _back_adjust_dividends(frame, actions)
        frame["corporate_action_count"] = len(actions)
        frame["series_adjustment_status"] = "corporate_action_adjusted"
        return frame

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
        metrics.extend(self._full_report_metrics(issuer, as_of))
        metrics = _dedupe_metrics(metrics)
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

    def build_news_payload(
        self,
        issuer: BseIssuer,
        *,
        as_of_date: str,
        retrieved_at: str,
    ) -> dict[str, Any]:
        html = self._html_by_ticker.get(issuer.ticker)
        if not html:
            raise RuntimeError(
                f"BSE issuer profile is unavailable for {issuer.ticker}."
            )
        events: list[dict[str, Any]] = []
        business_summary = _qualitative_business_summary(
            _profile_business_activity(html)
        )
        if business_summary:
            events.append(
                {
                    "date": as_of_date,
                    "headline": f"BSE issuer profile describes {issuer.ticker}'s business activity",
                    "event_type": "business_context",
                    "material": True,
                    "source_id": f"BSE_{issuer.ticker}_ISSUER_PROFILE",
                    "source_type": "company_ir",
                    "authority_rank": 1,
                    "url": issuer.profile_url,
                    "retrieved_at": retrieved_at,
                    "summary": business_summary,
                }
            )
        publications = _bse_publications(html, as_of_date=as_of_date)
        annual_publication = next(
            (
                publication
                for publication in publications
                if _bse_publication_type(publication["headline"]) == "filing"
            ),
            None,
        )
        if annual_publication:
            risk_disclosures = _bse_financial_risk_disclosures(
                self._download_best_pdf_text(annual_publication["url"])
            )
            for index, disclosure in enumerate(risk_disclosures, start=1):
                risk_id = re.sub(
                    r"[^A-Z0-9]+",
                    "_",
                    disclosure["risk_type"].upper(),
                ).strip("_")
                events.append(
                    {
                        "date": annual_publication["date"],
                        "headline": (
                            f"{issuer.ticker} annual report discloses "
                            f"{disclosure['risk_type'].lower()}"
                        ),
                        "event_type": "risk",
                        "material": True,
                        "source_id": (
                            f"BSE_{issuer.ticker}_ANNUAL_REPORT_RISK_"
                            f"{risk_id}_{index:02d}"
                        ),
                        "source_type": "company_ir",
                        "authority_rank": 1,
                        "url": annual_publication["url"],
                        "retrieved_at": retrieved_at,
                        "summary": disclosure["statement"],
                    }
                )
        for index, publication in enumerate(publications, start=1):
            event_type = _bse_publication_type(publication["headline"])
            events.append(
                {
                    **publication,
                    "event_type": event_type,
                    "material": False,
                    "source_id": (
                        f"BSE_{issuer.ticker}_PUBLICATION_"
                        f"{publication['date'].replace('-', '')}_{index:02d}"
                    ),
                    "source_type": "company_ir",
                    "authority_rank": 1,
                    "retrieved_at": retrieved_at,
                    "summary": publication["headline"],
                }
            )
        publication_dates = [item["date"] for item in publications]
        return {
            "coverage_status": "partial",
            "checked_at": retrieved_at,
            "window_start": min(publication_dates) if publication_dates else None,
            "window_end": as_of_date,
            "sources_checked": [issuer.profile_url],
            "events": events,
        }

    def _corporate_actions(self, issuer: BseIssuer) -> list[dict[str, Any]]:
        html = self._html_by_ticker[issuer.ticker]
        marker = '"flags":'
        start_at = html.find(marker)
        if start_at < 0:
            return []
        try:
            payload, _ = json.JSONDecoder().raw_decode(html[start_at + len(marker) :])
        except json.JSONDecodeError:
            return []
        budapest = ZoneInfo("Europe/Budapest")
        result: list[dict[str, Any]] = []
        for item in payload if isinstance(payload, list) else []:
            if not isinstance(item, dict) or item.get("date") is None:
                continue
            action_date = datetime.fromtimestamp(
                float(item["date"]) / 1000,
                tz=timezone.utc,
            ).astimezone(budapest).date()
            title = str(item.get("title") or "").upper()
            text = str(item.get("text") or "")
            amount_match = re.search(r"([\d.,]+)\s*[A-Z]{3}", text)
            result.append({
                "date": action_date.isoformat(),
                "type": "dividend" if title == "D" else "split" if title == "S" else "other",
                "amount": _parse_number(amount_match.group(1)) if amount_match else None,
                "description": text,
            })
        return result

    def _full_report_metrics(
        self,
        issuer: BseIssuer,
        as_of: date,
    ) -> list[dict[str, Any]]:
        html = self._html_by_ticker[issuer.ticker]
        annual_url = _link_before_text(html, "Latest Annual Report")
        interim_url = _link_before_text(html, "Latest interim management statement")
        result: list[dict[str, Any]] = []
        if annual_url:
            result.extend(
                _extract_report_metrics(
                    self._download_best_pdf_text(annual_url),
                    issuer,
                    fiscal_year=as_of.year - 1,
                    fiscal_period="FY",
                    period_bucket="annual",
                    end_date=f"{as_of.year - 1}-12-31",
                )
            )
        if interim_url:
            result.extend(
                _extract_report_metrics(
                    self._download_best_pdf_text(interim_url),
                    issuer,
                    fiscal_year=as_of.year,
                    fiscal_period="Q1",
                    period_bucket="quarterly",
                    end_date=f"{as_of.year}-03-31",
                )
            )
        return result

    def build_earnings_calendar(
        self,
        issuer: BseIssuer,
        *,
        as_of_date: str,
        retrieved_at: str,
    ) -> dict[str, Any]:
        html = self._html_by_ticker[issuer.ticker]
        timetable_match = re.search(
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>[^<]*Corporate Action Timetable[^<]*</a>',
            html,
            re.IGNORECASE,
        )
        timetable = timetable_match.group(1) if timetable_match else None
        if not timetable:
            return {"events": []}
        text = self._download_best_pdf_text(timetable)
        events: list[dict[str, Any]] = []
        months = {
            month: index
            for index, month in enumerate(
                (
                    "January", "February", "March", "April", "May", "June",
                    "July", "August", "September", "October", "November", "December",
                ),
                start=1,
            )
        }
        pattern = re.compile(
            r"Publication of\s+(.+?results(?:,\s*interim report)?)\s+"
            r"(\d{1,2})(?:st|nd|rd|th)?\s+"
            r"(" + "|".join(months) + r"),?\s+(20\d{2})",
            re.IGNORECASE,
        )
        basis = date.fromisoformat(as_of_date)
        for match in pattern.finditer(text):
            event_date = date(
                int(match.group(4)),
                months[match.group(3).title()],
                int(match.group(2)),
            )
            if event_date < basis:
                continue
            events.append({
                "ticker": issuer.ticker,
                "fiscal_period": match.group(1).strip(),
                "report_date": event_date.isoformat(),
                "timing": None,
                "confirmed": False,
                "source_id": f"BSE_{issuer.ticker}_CORPORATE_ACTION_TIMETABLE",
                "source_type": "company_ir",
                "url": urllib.parse.urljoin("https://www.bse.hu", timetable),
                "retrieved_at": retrieved_at,
            })
        return {"events": events}

    def _download_best_pdf_text(self, detail_path: str) -> str:
        detail_url = urllib.parse.urljoin("https://www.bse.hu", detail_path)
        if detail_url in self._pdf_text_by_detail_url:
            return self._pdf_text_by_detail_url[detail_url]
        html = self._fetch(detail_url).decode("utf-8", "replace")
        pdf_links = list(dict.fromkeys(re.findall(
            r'href=["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\']',
            html,
            re.IGNORECASE,
        )))
        best_text = ""
        best_score = -1
        for href in pdf_links:
            try:
                content = self._fetch(urllib.parse.urljoin(detail_url, href))
                reader = PdfReader(io.BytesIO(content))
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
            except Exception:
                continue
            lower = text.lower()
            score = len(text) + 50_000 * sum(
                phrase in lower
                for phrase in (
                    "consolidated statement of financial position",
                    "net cash provided by operating activities",
                    "earnings before interest, tax, depreciation",
                )
            )
            if score > best_score:
                best_score = score
                best_text = text
        self._pdf_text_by_detail_url[detail_url] = best_text
        return best_text

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


def _link_before_text(html: str, label: str) -> Optional[str]:
    match = re.search(
        rf'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*{re.escape(label)}\s*</a>',
        html,
        re.IGNORECASE,
    )
    return match.group(1) if match else None


def _parse_number(value: str) -> float:
    text = value.strip().replace("\xa0", "").replace(" ", "")
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    if "," in text and "." not in text:
        parts = text.split(",")
        text = "".join(parts) if all(len(part) == 3 for part in parts[1:]) else text.replace(",", ".")
    else:
        text = text.replace(",", "")
    number = float(text)
    return -number if negative else number


def _line_numbers(text: str, label: str) -> list[float]:
    match = re.search(rf"{re.escape(label)}[^\n]*", text, re.IGNORECASE)
    if not match:
        return []
    tokens = re.findall(r"\(?-?\d[\d,]*(?:\.\d+)?\)?", match.group(0)[len(label):])
    return [_parse_number(token) for token in tokens]


def _material_values(values: list[float]) -> list[float]:
    return [value for value in values if abs(value) >= 100]


def _extract_report_metrics(
    text: str,
    issuer: BseIssuer,
    *,
    fiscal_year: int,
    fiscal_period: str,
    period_bucket: str,
    end_date: str,
) -> list[dict[str, Any]]:
    if not text:
        return []
    is_quarter = period_bucket == "quarterly"
    start_date = f"{fiscal_year}-01-01" if is_quarter else f"{fiscal_year}-01-01"
    period = f"FY{fiscal_year}_{fiscal_period}" if is_quarter else f"FY{fiscal_year}"
    rows: list[dict[str, Any]] = []

    def add(metric_name: str, value: Optional[float], statement_type: str) -> None:
        if value is None:
            return
        rows.append(_metric_row(
            metric_name=metric_name,
            value=float(value) * 1000.0,
            unit=issuer.currency,
            period=period,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
            period_bucket=period_bucket,
            start_date=start_date if statement_type != "balance_sheet" else None,
            end_date=end_date,
            statement_type=statement_type,
            statement=f"{issuer.ticker} reported {metric_name} of {float(value) * 1000.0:.0f} {issuer.currency} for {period}.",
        ))

    def row_value(label: str) -> Optional[float]:
        values = _material_values(_line_numbers(text, label))
        if not values:
            return None
        return values[1] if is_quarter and len(values) >= 2 else values[0]

    add("operating_cash_flow", row_value("Net cash provided by operating activities"), "cash_flow")
    add("capex", row_value("Purchase of property, plant and equipment"), "cash_flow")

    ebitda = re.search(
        r"EBITDA(?:\s+is|\s+amounted\s+to)?\s+HUF\s+([\d,]+)\s+million",
        text,
        re.IGNORECASE,
    )
    if ebitda:
        add("ebitda", _parse_number(ebitda.group(1)) * 1000.0, "income_statement")

    if is_quarter:
        cash = re.search(
            r"cash and cash equivalents.*?totalled HUF\s+([\d,]+)\s+million",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if cash:
            add("cash_and_equivalents", _parse_number(cash.group(1)) * 1000.0, "balance_sheet")
        for metric_name, label in {
            "current_assets": "Total current assets",
            "current_liabilities": "Total current liabilities",
            "total_assets": "Total assets",
            "equity": "Total shareholders' equity",
            "short_term_debt": "Short term debt",
            "long_term_debt": "Long term debt",
            "lease_liabilities_current": "Short term part of lease liabilities",
            "lease_liabilities_long_term": "Long term part of lease liabilities",
        }.items():
            add(metric_name, row_value(label), "balance_sheet")
        values = {row["metric_name"]: row["value"] for row in rows}
        debt_components = [
            values.get("short_term_debt"),
            values.get("long_term_debt"),
            values.get("lease_liabilities_current"),
            values.get("lease_liabilities_long_term"),
        ]
        if all(value is not None for value in debt_components):
            rows.append(_metric_row(
                metric_name="total_debt",
                value=sum(float(value) for value in debt_components),
                unit=issuer.currency,
                period=period,
                fiscal_year=fiscal_year,
                fiscal_period=fiscal_period,
                period_bucket="instant",
                start_date=None,
                end_date=end_date,
                statement_type="balance_sheet",
                statement=f"{issuer.ticker} total debt including lease liabilities at {end_date}.",
            ))
        listed = re.search(r"TOTAL:.*?([\d,]{7,})\s+100\.00%", text, re.IGNORECASE | re.DOTALL)
        treasury = re.search(r"Treasury stock[^\n]*?([\d,]{5,})", text, re.IGNORECASE)
        listed_value = _parse_number(listed.group(1)) if listed else None
        treasury_value = _parse_number(treasury.group(1)) if treasury else None
        for metric_name, value in (
            ("listed_share_count", listed_value),
            ("treasury_share_count", treasury_value),
            (
                "economic_share_count",
                listed_value - treasury_value
                if listed_value is not None and treasury_value is not None
                else None,
            ),
        ):
            if value is not None:
                rows.append(_metric_row(
                    metric_name=metric_name,
                    value=value,
                    unit="shares",
                    period=period,
                    fiscal_year=fiscal_year,
                    fiscal_period=fiscal_period,
                    period_bucket="instant",
                    start_date=None,
                    end_date=end_date,
                    statement_type="balance_sheet",
                    statement=f"{issuer.ticker} reported {metric_name} of {value:.0f} at {end_date}.",
                ))
    return rows


def _dedupe_metrics(metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in metrics:
        key = (str(row.get("metric_name")), str(row.get("period")))
        by_key[key] = row
    return list(by_key.values())


def _back_adjust_dividends(
    frame: pd.DataFrame,
    actions: list[dict[str, Any]],
) -> pd.DataFrame:
    adjusted = frame.copy().sort_values("date").reset_index(drop=True)
    for column in ("open", "high", "low", "close"):
        adjusted[f"adjusted_{column}"] = adjusted[column].astype(float)
    for action in sorted(actions, key=lambda item: item["date"]):
        if action.get("type") != "dividend" or not action.get("amount"):
            continue
        earlier = adjusted.index[adjusted["date"] < action["date"]]
        if len(earlier) == 0:
            continue
        previous_index = int(earlier[-1])
        previous_close = float(adjusted.at[previous_index, "close"])
        factor = (previous_close - float(action["amount"])) / previous_close
        if not 0 < factor <= 1:
            continue
        for column in ("open", "high", "low", "close"):
            target = f"adjusted_{column}"
            adjusted.loc[earlier, target] = adjusted.loc[earlier, target] * factor
    return adjusted
