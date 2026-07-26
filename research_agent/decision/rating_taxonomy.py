from enum import Enum


class Rating(str, Enum):
    STRONG_BUY = "Strong Buy"
    BUY = "Buy"
    ACCUMULATE = "Accumulate"
    HOLD = "Hold"
    TACTICAL_TRIM = "Tactical Trim"
    TACTICAL_UNDERWEIGHT = "Tactical Underweight"
    UNDERWEIGHT = "Underweight"
    SELL = "Sell"
    AVOID = "Avoid"


RATING_DEFINITIONS = {
    Rating.STRONG_BUY: "Highest-conviction positive research view.",
    Rating.BUY: "Positive research view; valuation and setup are attractive.",
    Rating.ACCUMULATE: "Constructive research view, conditional on pullbacks or confirmation.",
    Rating.HOLD: "Neutral research view; no strong positive or negative signal.",
    Rating.TACTICAL_TRIM: "Cautious research view due to timing or event risk.",
    Rating.TACTICAL_UNDERWEIGHT: "Defensive research view due to risk/reward or event risk.",
    Rating.UNDERWEIGHT: "Structurally cautious research view relative to the benchmark.",
    Rating.SELL: "Strong negative research view.",
    Rating.AVOID: "Unsuitable current research setup.",
}
