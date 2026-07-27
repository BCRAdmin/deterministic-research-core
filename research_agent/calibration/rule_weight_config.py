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
        "REVENUE_GROWTH_GT_30": RuleWeight(rule_id="REVENUE_GROWTH_GT_30", base_weight=2.0),
        "REVENUE_GROWTH_GT_15": RuleWeight(rule_id="REVENUE_GROWTH_GT_15", base_weight=1.0),
        "REVENUE_GROWTH_LT_5": RuleWeight(rule_id="REVENUE_GROWTH_LT_5", base_weight=-1.0),
        "FCF_TTM_POSITIVE": RuleWeight(rule_id="FCF_TTM_POSITIVE", base_weight=1.0),
        "FCF_MARGIN_GT_25": RuleWeight(rule_id="FCF_MARGIN_GT_25", base_weight=1.0),
        "FCF_MARGIN_NEGATIVE": RuleWeight(rule_id="FCF_MARGIN_NEGATIVE", base_weight=-1.0),
        "OPERATING_MARGIN_GT_10": RuleWeight(rule_id="OPERATING_MARGIN_GT_10", base_weight=1.0),
        "OPERATING_MARGIN_NEGATIVE": RuleWeight(rule_id="OPERATING_MARGIN_NEGATIVE", base_weight=-1.0),
        "SBC_TO_REVENUE_GT_20": RuleWeight(rule_id="SBC_TO_REVENUE_GT_20", base_weight=-1.0),
        "SBC_TO_FCF_GT_100": RuleWeight(rule_id="SBC_TO_FCF_GT_100", base_weight=-1.0),
        "NET_CASH_POSITIVE": RuleWeight(rule_id="NET_CASH_POSITIVE", base_weight=1.0),
        "PRICE_ABOVE_200SMA": RuleWeight(rule_id="PRICE_ABOVE_200SMA", base_weight=1.0),
        "PRICE_BELOW_200SMA": RuleWeight(rule_id="PRICE_BELOW_200SMA", base_weight=-1.0),
        "GOLDEN_CROSS": RuleWeight(rule_id="GOLDEN_CROSS", base_weight=1.0),
        "DEATH_CROSS": RuleWeight(rule_id="DEATH_CROSS", base_weight=-1.0),
        "BULLISH_MA_ALIGNMENT": RuleWeight(rule_id="BULLISH_MA_ALIGNMENT", base_weight=0.5),
        "BEARISH_MA_ALIGNMENT": RuleWeight(rule_id="BEARISH_MA_ALIGNMENT", base_weight=-0.5),
        "PRICE_ABOVE_EMA10": RuleWeight(rule_id="PRICE_ABOVE_EMA10", base_weight=1.0),
        "PRICE_BELOW_EMA10": RuleWeight(rule_id="PRICE_BELOW_EMA10", base_weight=-1.0),
        "RSI_GT_75": RuleWeight(rule_id="RSI_GT_75", base_weight=-1.0),
        "RSI_LT_30": RuleWeight(rule_id="RSI_LT_30", base_weight=1.0),
        "MACD_HISTOGRAM_POSITIVE": RuleWeight(rule_id="MACD_HISTOGRAM_POSITIVE", base_weight=1.0),
        "MACD_HISTOGRAM_NEGATIVE": RuleWeight(rule_id="MACD_HISTOGRAM_NEGATIVE", base_weight=-1.0),
        "FORWARD_PE_LT_25": RuleWeight(rule_id="FORWARD_PE_LT_25", base_weight=1.0),
        "FORWARD_PE_GT_60": RuleWeight(rule_id="FORWARD_PE_GT_60", base_weight=-1.0),
        "PRICE_TO_FCF_LT_30": RuleWeight(rule_id="PRICE_TO_FCF_LT_30", base_weight=1.0),
        "PRICE_TO_FCF_GT_60": RuleWeight(rule_id="PRICE_TO_FCF_GT_60", base_weight=-1.0),
        "PEG_LT_1": RuleWeight(rule_id="PEG_LT_1", base_weight=1.0),
        "PEG_GT_2": RuleWeight(rule_id="PEG_GT_2", base_weight=-1.0),
        "ATR_PCT_GT_5": RuleWeight(rule_id="ATR_PCT_GT_5", base_weight=-1.0),
        "ATR_PCT_GT_8": RuleWeight(rule_id="ATR_PCT_GT_8", base_weight=-2.0),
        "VALIDATION_ERROR": RuleWeight(rule_id="VALIDATION_ERROR", base_weight=-3.0),
        "VALIDATION_WARNINGS_GE_3": RuleWeight(rule_id="VALIDATION_WARNINGS_GE_3", base_weight=-1.0),
        "AUDIT_ERROR": RuleWeight(rule_id="AUDIT_ERROR", base_weight=-3.0),
        "AUDIT_WARNINGS_GE_2": RuleWeight(rule_id="AUDIT_WARNINGS_GE_2", base_weight=-1.0),
        "FORWARD_EPS_GUIDANCE_MISMATCH": RuleWeight(rule_id="FORWARD_EPS_GUIDANCE_MISMATCH", base_weight=-1.0),
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
