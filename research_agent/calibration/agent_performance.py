from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from pydantic import BaseModel

from research_agent.outcomes.calibration_dataset import CalibrationRow


class AgentPerformance(BaseModel):
    agent: str
    sample_size: int
    audit_issue_count: int
    avg_quality_score: float


def aggregate_agent_performance(rows: Iterable[CalibrationRow]) -> list[AgentPerformance]:
    grouped: dict[str, list[CalibrationRow]] = defaultdict(list)
    for row in rows:
        for agent in row.agent_issue_counts:
            grouped[agent].append(row)

    results: list[AgentPerformance] = []
    for agent, agent_rows in sorted(grouped.items()):
        audit_issue_count = sum(row.agent_issue_counts.get(agent, 0) for row in agent_rows)
        avg_quality_score = sum(row.quality_score for row in agent_rows) / len(agent_rows)
        results.append(
            AgentPerformance(
                agent=agent,
                sample_size=len(agent_rows),
                audit_issue_count=audit_issue_count,
                avg_quality_score=avg_quality_score,
            )
        )
    return results
