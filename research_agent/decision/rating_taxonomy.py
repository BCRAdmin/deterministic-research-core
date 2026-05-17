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
    Rating.STRONG_BUY: "Aggressively build position now.",
    Rating.BUY: "Build position, valuation and setup are attractive.",
    Rating.ACCUMULATE: "Build position gradually, usually on pullbacks or confirmation.",
    Rating.HOLD: "Maintain existing position; no strong add or reduce signal.",
    Rating.TACTICAL_TRIM: "Reduce partial exposure due to timing/risk, but keep core.",
    Rating.TACTICAL_UNDERWEIGHT: "Temporarily below target weight due to risk/reward or event risk.",
    Rating.UNDERWEIGHT: "Structurally below benchmark/target weight.",
    Rating.SELL: "Exit most or all of position.",
    Rating.AVOID: "Do not initiate; unsuitable setup.",
}

