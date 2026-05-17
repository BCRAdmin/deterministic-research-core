from datetime import date
from typing import Optional


def days_between(first_date: str, second_date: str) -> int:
    first = date.fromisoformat(first_date)
    second = date.fromisoformat(second_date)
    return abs((second - first).days)


def is_event_confirmed(event_date: Optional[str], confirmed: bool, source: Optional[str]) -> bool:
    return bool(event_date and confirmed and source)

