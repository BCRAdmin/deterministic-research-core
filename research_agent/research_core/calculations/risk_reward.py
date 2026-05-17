from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class RiskRewardLevels(BaseModel):
    position_type: str
    entry: float
    stop_loss: float
    take_profit: Optional[float] = None
    risk_per_share: Optional[float] = None
    reward_per_share: Optional[float] = None
    reward_to_risk: Optional[float] = None


def calculate_risk_reward(
    position_type: str,
    entry: float,
    stop_loss: float,
    take_profit: Optional[float] = None,
) -> RiskRewardLevels:
    if position_type not in {"long", "short"}:
        raise ValueError("position_type must be 'long' or 'short'.")
    if position_type == "long":
        risk = entry - stop_loss
        reward = take_profit - entry if take_profit is not None else None
    else:
        risk = stop_loss - entry
        reward = entry - take_profit if take_profit is not None else None

    return RiskRewardLevels(
        position_type=position_type,
        entry=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_per_share=risk,
        reward_per_share=reward,
        reward_to_risk=(reward / risk) if reward is not None and risk > 0 else None,
    )

