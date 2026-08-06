from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from research_agent.decision.rating_taxonomy import Rating


class SignalScores(BaseModel):
    fundamental_score: float
    technical_score: float
    valuation_score: float
    risk_score: float
    composite_score: float
    fundamental_status: str = "measured"
    technical_status: str = "measured"
    valuation_status: str = "measured"
    risk_status: str = "measured"


class RatingPermission(BaseModel):
    allowed_ratings: List[Rating]
    blocked_ratings: List[Rating]
    preferred_rating: Rating
    reason: str
    evidence_status: str = "complete"


class DecisionPacket(BaseModel):
    ticker: str
    as_of_date: str
    signal_scores: SignalScores
    analytical_rating_unconstrained: Optional[Rating] = None
    analytical_rating_reason: Optional[str] = None
    conclusion_status: Literal["rated", "provisional", "not_rated", "blocked"] = (
        "rated"
    )
    conclusion_status_reason: Optional[str] = None
    rating_permission: RatingPermission
    action_policy: Dict[str, object] = Field(default_factory=dict)
    key_reasons: List[str] = Field(default_factory=list)
    key_risks: List[str] = Field(default_factory=list)
    triggered_rules: List[str] = Field(default_factory=list)
    score_version: str = "v1"
    calibration_mode: str = "live"
