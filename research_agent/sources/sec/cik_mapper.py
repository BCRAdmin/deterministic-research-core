from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional, Union

from pydantic import BaseModel


class CikRecord(BaseModel):
    ticker: str
    cik: str
    company_name: str


class CikMapper:
    def __init__(self, records: list[CikRecord]):
        self.by_ticker: Dict[str, CikRecord] = {
            record.ticker.upper(): record for record in records
        }

    def get_cik(self, ticker: str) -> str:
        record = self.by_ticker.get(ticker.upper())
        if not record:
            raise KeyError(f"No CIK found for ticker {ticker}")
        return record.cik

    def get_company_name(self, ticker: str) -> Optional[str]:
        record = self.by_ticker.get(ticker.upper())
        return record.company_name if record else None


def load_cik_mapper(path: Union[str, Path]) -> CikMapper:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    records = payload.get("records", payload) if isinstance(payload, dict) else payload
    return CikMapper([CikRecord(**record) for record in records])
