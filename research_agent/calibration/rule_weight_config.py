from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional, Union

from pydantic import BaseModel, Field


class RuleWeight(BaseModel):
    rule_id: str
    base_weight: float
    calibrated_weight: Optional[float] = None
    min_sample_size: int = 30
    enabled: bool = True
    shadow_only: bool = True


class RuleWeightConfig(BaseModel):
    version: str
    rules: Dict[str, RuleWeight] = Field(default_factory=dict)

    def get_weight(self, rule_id: str, calibration_mode: str = "live") -> float:
        rule = self.rules.get(rule_id)
        if rule is None or not rule.enabled:
            return 0.0
        if rule.calibrated_weight is None:
            return rule.base_weight
        if calibration_mode == "shadow":
            return rule.calibrated_weight
        if calibration_mode == "live" and not rule.shadow_only:
            return rule.calibrated_weight
        return rule.base_weight


DEFAULT_RULE_WEIGHTS = RuleWeightConfig(
    version="v1",
    rules={
        "FCF_TTM_POSITIVE": RuleWeight(rule_id="FCF_TTM_POSITIVE", base_weight=1.0),
        "FCF_MARGIN_NEGATIVE": RuleWeight(rule_id="FCF_MARGIN_NEGATIVE", base_weight=-1.0),
        "OPERATING_MARGIN_NEGATIVE": RuleWeight(rule_id="OPERATING_MARGIN_NEGATIVE", base_weight=-1.0),
        "EQUITY_NON_POSITIVE": RuleWeight(rule_id="EQUITY_NON_POSITIVE", base_weight=-1.0),
        "DEATH_CROSS": RuleWeight(rule_id="DEATH_CROSS", base_weight=-1.0),
        "TREND_STATE_BULLISH": RuleWeight(rule_id="TREND_STATE_BULLISH", base_weight=1.0),
        "TREND_STATE_BEARISH": RuleWeight(rule_id="TREND_STATE_BEARISH", base_weight=-1.0),
    },
)


def save_rule_weight_config(config: RuleWeightConfig, path: Union[str, Path]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = config.model_dump(mode="json") if hasattr(config, "model_dump") else config.dict()
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return target


def load_rule_weight_config(path: Union[str, Path]) -> RuleWeightConfig:
    return RuleWeightConfig(**json.loads(Path(path).read_text(encoding="utf-8")))
