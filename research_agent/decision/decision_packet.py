from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

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
    permission_type: Literal["analytical", "provisional", "safety_fallback"] = (
        "analytical"
    )
    display_rating: str = ""
    publication_allowed: bool = True
    fallback_only: bool = False


class DecisionInput(BaseModel):
    input_id: str
    input_type: Literal["financial_metric", "operating_kpi", "current_risk"]
    direction: Literal["positive", "negative", "mixed", "neutral", "unknown"]
    materiality: Literal["material", "immaterial", "unknown"]
    confidence: Literal["high", "medium", "low"]
    included_in_score: bool
    exclusion_reason: Optional[str] = None
    label: Optional[str] = None
    summary: Optional[str] = None
    transmission: Optional[str] = None
    management_counterposition: Optional[str] = None
    review_trigger: Optional[str] = None


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
    evidence_maturity: Literal["complete", "partial", "incomplete", "blocked"] = (
        "complete"
    )
    publication_permission: Literal["eligible", "manual_review", "blocked"] = (
        "eligible"
    )
    rating_permission: RatingPermission
    action_policy: Dict[str, object] = Field(default_factory=dict)
    key_reasons: List[str] = Field(default_factory=list)
    key_risks: List[str] = Field(default_factory=list)
    triggered_rules: List[str] = Field(default_factory=list)
    score_version: str = "v1"
    calibration_mode: Literal[
        "standardized_uncalibrated",
        "company_calibrated",
        "backtested",
        "shadow",
    ] = "standardized_uncalibrated"
    decision_inputs: List[DecisionInput] = Field(default_factory=list)

    @field_validator("calibration_mode", mode="before")
    @classmethod
    def migrate_legacy_live_calibration(cls, value):
        # Historical packets used ``live`` to mean that the deterministic
        # standardized rules were active.  They were never company-calibrated
        # or backtested, so the honest migration is explicitly uncalibrated.
        if value == "live":
            return "standardized_uncalibrated"
        return value
