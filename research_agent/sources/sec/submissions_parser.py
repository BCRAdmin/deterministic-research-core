from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class FilingRecord(BaseModel):
    accession_number: str
    filing_date: str
    report_date: Optional[str] = None
    form: str
    primary_document: Optional[str] = None


class SubmissionsParser:
    def __init__(self, submissions_json: Dict[str, Any]):
        self.data = submissions_json

    def recent_filings(self, forms: Optional[set[str]] = None) -> List[FilingRecord]:
        recent = self.data.get("filings", {}).get("recent", {})
        accession_numbers = recent.get("accessionNumber", [])
        forms_list = recent.get("form", [])
        filing_dates = recent.get("filingDate", [])
        report_dates = recent.get("reportDate", [])
        primary_documents = recent.get("primaryDocument", [])
        filings = []
        for index, accession in enumerate(accession_numbers):
            form = _at(forms_list, index)
            if forms and form not in forms:
                continue
            filings.append(
                FilingRecord(
                    accession_number=accession,
                    filing_date=_at(filing_dates, index) or "",
                    report_date=_at(report_dates, index),
                    form=form or "",
                    primary_document=_at(primary_documents, index),
                )
            )
        return filings

    def latest_filing(self, form: str) -> Optional[FilingRecord]:
        filings = self.recent_filings({form})
        if not filings:
            return None
        return sorted(filings, key=lambda filing: filing.filing_date)[-1]


def _at(values: list, index: int):
    return values[index] if index < len(values) else None
