from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional, Union

from pydantic import BaseModel, Field

from research_agent.calibration.rule_weight_config import DEFAULT_RULE_WEIGHTS, RuleWeight, RuleWeightConfig


class CalibrationConfigRecord(BaseModel):
    version: str
    created_at: str
    based_on_reports: int
    min_outcome_window: str
    mode: str
    rules: dict[str, RuleWeight] = Field(default_factory=dict)

    def to_rule_weight_config(self) -> RuleWeightConfig:
        return RuleWeightConfig(version=self.version, rules=self.rules)


def build_calibration_config_record(
    config: RuleWeightConfig = DEFAULT_RULE_WEIGHTS,
    based_on_reports: int = 0,
    min_outcome_window: str = "60d",
    mode: str = "shadow",
    created_at: Optional[str] = None,
) -> CalibrationConfigRecord:
    return CalibrationConfigRecord(
        version=config.version,
        created_at=created_at or date.today().isoformat(),
        based_on_reports=based_on_reports,
        min_outcome_window=min_outcome_window,
        mode=mode,
        rules=config.rules,
    )


def save_calibration_config(
    record: CalibrationConfigRecord,
    base_dir: Union[str, Path] = "research_agent/data/calibration",
) -> Path:
    target_dir = Path(base_dir) / "configs"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"rule_weights_{record.version}.json"
    payload = record.model_dump(mode="json") if hasattr(record, "model_dump") else record.dict()
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return target


def load_calibration_config(path: Union[str, Path]) -> CalibrationConfigRecord:
    return CalibrationConfigRecord(**json.loads(Path(path).read_text(encoding="utf-8")))


def generate_default_rule_weights(
    base_dir: Union[str, Path] = "research_agent/data/calibration",
) -> Path:
    record = build_calibration_config_record(
        config=DEFAULT_RULE_WEIGHTS,
        based_on_reports=0,
        mode="shadow",
        created_at=date.today().isoformat(),
    )
    return save_calibration_config(record, base_dir)
