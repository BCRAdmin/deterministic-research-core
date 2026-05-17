from __future__ import annotations


def infer_action_class(actions: list[str]):
    text = " ".join(actions).lower()

    if "close position" in text or "sell entire" in text or "exit fully" in text:
        return "sell"

    if "trim" in text or "reduce" in text or "teilweise reduzieren" in text:
        return "tactical_trim"

    if "hold" in text and "add" not in text:
        return "hold"

    if "staged entry" in text or "accumulate" in text or "gestaffelt" in text:
        return "accumulate"

    if "buy" in text:
        return "buy"

    return "unknown"


def validate_rating_vs_actions(rating: str, actions: list[str]):
    inferred = infer_action_class(actions)

    if rating.lower() == "sell" and inferred == "tactical_trim":
        return {
            "severity": "warning",
            "code": "RATING_TOO_HARSH_FOR_ACTION",
            "message": "Actions imply tactical trim, not full sell.",
        }

    if rating.lower() == "buy" and inferred == "accumulate":
        return {
            "severity": "info",
            "code": "BUY_IS_STAGED_ENTRY",
            "message": "Actions imply staged accumulation, not immediate full buy.",
        }

    incompatible = {
        "sell": ["hold", "accumulate", "buy"],
        "buy": ["sell", "tactical_trim"],
        "underweight": ["buy"],
    }
    if inferred in incompatible.get(rating.lower(), []):
        return {
            "severity": "warning",
            "code": "RATING_ACTION_CLASS_MISMATCH",
            "message": f"Rating {rating} is inconsistent with inferred action class {inferred}.",
        }

    return None

