from __future__ import annotations


def validate_trade_levels(
    position_type: str,
    entry: float,
    stop_loss: float,
    take_profit: float = None,
):
    issues = []

    if position_type == "long":
        if stop_loss >= entry:
            issues.append(
                {
                    "severity": "error",
                    "code": "LONG_STOP_ABOVE_ENTRY",
                    "message": "For a long position, stop-loss must be below entry.",
                }
            )
        if take_profit is not None and take_profit <= entry:
            issues.append(
                {
                    "severity": "error",
                    "code": "LONG_TAKE_PROFIT_BELOW_ENTRY",
                    "message": "For a long position, take-profit must be above entry.",
                }
            )

    if position_type == "short":
        if stop_loss <= entry:
            issues.append(
                {
                    "severity": "error",
                    "code": "SHORT_STOP_BELOW_ENTRY",
                    "message": "For a short position, stop-loss must be above entry.",
                }
            )
        if take_profit is not None and take_profit >= entry:
            issues.append(
                {
                    "severity": "error",
                    "code": "SHORT_TAKE_PROFIT_ABOVE_ENTRY",
                    "message": "For a short position, take-profit must be below entry.",
                }
            )

    if position_type not in {"long", "short"}:
        issues.append(
            {
                "severity": "error",
                "code": "UNKNOWN_POSITION_TYPE",
                "message": "position_type must be either long or short.",
            }
        )

    return issues

