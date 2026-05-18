from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Union

from research_agent.outcomes.outcome_packet import (
    OUTCOME_PACKET_HORIZONS,
    calculate_outcome_packets,
    load_outcome_fixtures,
    packet_by_horizon,
)

DEFAULT_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "outcomes"


def verify_outcome_schema_fixture_dir(fixture_dir: Union[str, Path] = DEFAULT_FIXTURE_DIR) -> list[str]:
    errors: list[str] = []
    fixtures = load_outcome_fixtures(fixture_dir)
    if not fixtures:
        return [f"No outcome fixtures found in {fixture_dir}"]

    scenario_ids = {fixture.scenario_id for fixture in fixtures}
    for required in [
        "pending_5d",
        "matured_5d",
        "missing_benchmark",
        "data_unavailable",
        "invalidated_source",
        "manual_review_no_auto_publish",
    ]:
        if required not in scenario_ids:
            errors.append(f"Missing required outcome scenario: {required}")

    for fixture in fixtures:
        try:
            packets = calculate_outcome_packets(fixture)
        except Exception as exc:  # pragma: no cover - surfaced as verifier error
            errors.append(f"{fixture.scenario_id}: calculation failed: {exc}")
            continue

        by_horizon = packet_by_horizon(packets)
        if set(by_horizon) != set(OUTCOME_PACKET_HORIZONS):
            errors.append(f"{fixture.scenario_id}: horizon set mismatch: {sorted(by_horizon)}")

        for horizon, expected_status in fixture.expected_status_by_horizon.items():
            packet = by_horizon.get(horizon)
            if packet is None:
                errors.append(f"{fixture.scenario_id}: missing horizon {horizon}")
            elif packet.status != expected_status:
                errors.append(
                    f"{fixture.scenario_id}: {horizon} expected {expected_status}, got {packet.status}"
                )

        if fixture.decision_type == "manual_review":
            if any(packet.public_ready for packet in packets):
                errors.append(f"{fixture.scenario_id}: manual_review packet became public_ready")
            if not all(packet.manual_review_reason for packet in packets):
                errors.append(f"{fixture.scenario_id}: manual_review reason missing on packets")

        if any(packet.calc_version != "outcome-tracking-v1" for packet in packets):
            errors.append(f"{fixture.scenario_id}: unexpected calc_version")

    try:
        calculate_outcome_packets(fixtures[0], no_live_fetch=False)
        errors.append("no_live_fetch=False did not fail")
    except RuntimeError:
        pass

    return errors


def main(argv: Optional[list[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    fixture_dir = Path(argv[0]) if argv else DEFAULT_FIXTURE_DIR
    errors = verify_outcome_schema_fixture_dir(fixture_dir)
    if errors:
        print("Outcome schema verification failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Outcome schema verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
