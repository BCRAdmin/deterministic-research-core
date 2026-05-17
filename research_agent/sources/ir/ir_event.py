from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class IrEvent(BaseModel):
    ticker: str
    event_type: str
    title: str
    date: Optional[str] = None
    url: Optional[str] = None
    source_id: str
