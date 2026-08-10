"""Fail-closed scale and change-review controls for deterministic Room16 research."""

from research_agent.scale.change_detector import detect_authority_changes
from research_agent.scale.scale_contract import (
    ScaleContractError,
    ScalePlanRequest,
    build_scale_plan,
    execute_scale_plan,
    load_scale_plan,
    save_scale_plan,
)

__all__ = [
    "ScaleContractError",
    "ScalePlanRequest",
    "build_scale_plan",
    "detect_authority_changes",
    "execute_scale_plan",
    "load_scale_plan",
    "save_scale_plan",
]
