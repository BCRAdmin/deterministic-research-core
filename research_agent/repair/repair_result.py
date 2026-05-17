from typing import List, Optional

from pydantic import BaseModel, Field


class RepairChange(BaseModel):
    issue_code: str
    original_text: Optional[str] = None
    repaired_text: Optional[str] = None
    explanation: str


class RepairResult(BaseModel):
    ticker: str
    attempt: int
    success: bool
    repaired_markdown: str
    changes: List[RepairChange] = Field(default_factory=list)
    remaining_blocking_errors: List[str] = Field(default_factory=list)

