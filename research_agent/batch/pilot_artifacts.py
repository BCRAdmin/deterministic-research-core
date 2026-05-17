from __future__ import annotations

import argparse
import json
import shutil
import statistics
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


GOLD_TEMPLATES = ["GOOGL", "SNOW"]
NEAR_GOLD_TEMPLATES = ["MSFT"]
USABLE_INTERNAL_DRAFTS = ["AAPL", "META", "NFLX", "DDOG", "CRM", "AVGO"]


def generate_manual_review_triage(batch_dir: str | Path) -> tuple[Path, Path]:
    base = Path(batch_dir)
    dashboard = _load_json(base / "dashboard_status.json")
    items = [item for item in dashboard.get("items", []) if item.get("status") == "manual_review"]

    triage_items = []
    group_counts: Counter[str] = Counter()
    for item in items:
        reason_groups = _reason_groups(item)
        for group in reason_groups:
            group_counts[group] += 1
        primary = _primary_root_cause(reason_groups)
        fixability = _fixability_for_item(primary, item)
        triage_items.append(
            {
                "ticker": item.get("ticker"),
                "status": item.get("status"),
                "quality_score": item.get("quality_score"),
                "external_display_rating": item.get("external_display_rating") or item.get("display_rating"),
                "reason_codes": item.get("manual_review_reasons", []),
                "reason_groups": reason_groups,
                "primary_root_cause": primary,
                "fixability": fixability,
                "recommended_next_action": _recommended_next_action(primary, fixability, item),
            }
        )

    payload = {
        "batch_id": dashboard.get("batch_id"),
        "generated_at": _utc_now(),
        "total_manual_review": len(triage_items),
        "count_by_reason_group": dict(group_counts),
        "items": triage_items,
    }

    json_path = base / "manual_review_triage.json"
    md_path = base / "manual_review_triage.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_render_manual_review_triage_markdown(payload), encoding="utf-8")
    return md_path, json_path


def generate_operating_pilot_review(batch_dir: str | Path) -> Path:
    base = Path(batch_dir)
    dashboard = _load_json(base / "dashboard_status.json")
    triage_path = base / "manual_review_triage.json"
    triage = _load_json(triage_path) if triage_path.exists() else {"items": [], "count_by_reason_group": {}}

    items = dashboard.get("items", [])
    passed_items = [item for item in items if item.get("status") == "passed"]
    manual_items = [item for item in items if item.get("status") == "manual_review"]
    failed_items = [item for item in items if item.get("status") == "failed"]
    qualities = [float(item["quality_score"]) for item in items if item.get("quality_score") is not None]
    avg_quality = round(sum(qualities) / len(qualities), 2) if qualities else None
    median_quality = round(statistics.median(qualities), 2) if qualities else None
    lowest_quality = min(qualities) if qualities else None

    top_data_gaps = Counter()
    for entry in triage.get("items", []):
        for group in entry.get("reason_groups", []):
            if group in {
                "data_gap",
                "claim_substance_gap",
                "missing_current_period_context",
                "missing_fcf_support",
            }:
                top_data_gaps[group] += 1

    issue_counts = Counter()
    for item in items:
        for code in item.get("evidence_warning_codes", []):
            issue_counts[code] += 1
        for code in item.get("reconciliation_warning_codes", []):
            issue_counts[code] += 1
        for code in item.get("manual_review_reasons", []):
            if code in {
                "CURRENT_PERIOD_IR_RECONCILIATION_REQUIRED",
                "COMPANY_DEFINED_FCF_MISMATCH",
                "COMPANY_DEFINED_FCF_OCF_INCONSISTENCY",
                "TRUE_SOURCE_VALUE_DISAGREEMENT",
            }:
                issue_counts[code] += 1

    false_pass_candidates = [
        item.get("ticker")
        for item in passed_items
        if _is_false_pass_candidate(item)
    ]

    best_items = sorted(
        [item for item in items if item.get("quality_score") is not None],
        key=lambda item: float(item["quality_score"]),
        reverse=True,
    )[:5]
    worst_items = sorted(
        [item for item in items if item.get("quality_score") is not None],
        key=lambda item: float(item["quality_score"]),
    )[:5]

    review = {
        "batch_id": dashboard.get("batch_id"),
        "generated_at": _utc_now(),
        "passed_count": len(passed_items),
        "manual_review_count": len(manual_items),
        "failed_count": len(failed_items),
        "avg_quality": avg_quality,
        "median_quality": median_quality,
        "lowest_quality": lowest_quality,
        "passed_tickers": [item.get("ticker") for item in passed_items],
        "manual_review_tickers": [item.get("ticker") for item in manual_items],
        "failed_tickers": [item.get("ticker") for item in failed_items],
        "top_manual_review_reasons": dict(Counter(triage.get("count_by_reason_group", {})).most_common(8)),
        "top_data_coverage_gaps": dict(top_data_gaps.most_common(8)),
        "top_evidence_reconciliation_issues": dict(issue_counts.most_common(8)),
        "false_pass_candidates": false_pass_candidates,
        "best_5_reports": [_ticker_quality(item) for item in best_items],
        "worst_5_reports": [_ticker_quality(item) for item in worst_items],
        "recommendation": _operating_pilot_recommendation(
            failed=len(failed_items),
            avg_quality=avg_quality,
            false_pass_candidates=false_pass_candidates,
        ),
    }

    output_path = base / "operating_pilot_review.md"
    output_path.write_text(_render_operating_review_markdown(review), encoding="utf-8")
    return output_path


def generate_release_package(
    fresh_batch_dir: str | Path,
    operating_batch_dir: str | Path,
    output_dir: str | Path,
) -> Path:
    fresh_dir = Path(fresh_batch_dir)
    operating_dir = Path(operating_batch_dir)
    target = Path(output_dir)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)

    example_dir = target / "EXAMPLE_REPORTS"
    dashboard_dir = target / "DASHBOARD_EXAMPLE"
    example_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)

    fresh_dashboard = _load_json(fresh_dir / "dashboard_status.json")
    operating_dashboard = _load_json(operating_dir / "dashboard_status.json")
    outcome_review = _load_json(Path("outputs/backtests/pilot_outcome_review.json"))

    selected_reports = _select_example_reports(fresh_dashboard, operating_dashboard)
    for ticker, source in selected_reports:
        shutil.copy2(source, example_dir / f"{ticker}_publish_report.md")

    for name, source in [
        ("dashboard_status.json", fresh_dir / "dashboard_status.json"),
        ("batch_manifest.json", fresh_dir / "batch_manifest.json"),
        ("pilot_review.md", fresh_dir / "pilot_review.md"),
        ("operating_pilot_review.md", operating_dir / "operating_pilot_review.md"),
    ]:
        shutil.copy2(source, dashboard_dir / name)

    release_status = _release_status_payload(fresh_dashboard, operating_dashboard)
    (target / "PILOT_V1_OVERVIEW.md").write_text(_pilot_overview_markdown(), encoding="utf-8")
    (target / "TECHNICAL_ARCHITECTURE.md").write_text(_technical_architecture_markdown(), encoding="utf-8")
    (target / "OPERATING_RUNBOOK.md").write_text(
        _operating_runbook_markdown(fresh_dir, operating_dir),
        encoding="utf-8",
    )
    (target / "KNOWN_LIMITATIONS.md").write_text(_known_limitations_markdown(), encoding="utf-8")
    (target / "OUTCOME_STATUS.md").write_text(_outcome_status_markdown(outcome_review), encoding="utf-8")
    (target / "COST_AND_RUNTIME_ESTIMATE.md").write_text(
        _cost_runtime_markdown(fresh_dir, operating_dir),
        encoding="utf-8",
    )
    (target / "NEXT_30_DAYS.md").write_text(_next_30_days_markdown(), encoding="utf-8")
    (target / "RELEASE_STATUS.json").write_text(
        json.dumps(release_status, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    zip_path = target.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(target.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(target.parent))
    return zip_path


def _select_example_reports(fresh_dashboard: dict, operating_dashboard: dict) -> list[tuple[str, Path]]:
    selected: list[tuple[str, Path]] = []
    selected.extend(_report_paths_for_tickers(fresh_dashboard, ["GOOGL", "SNOW"]))
    selected.extend(_report_paths_for_tickers(fresh_dashboard, ["MSFT"]))

    already = {ticker for ticker, _ in selected}
    remaining = [
        item
        for item in operating_dashboard.get("items", [])
        if item.get("status") == "passed"
        and item.get("ticker") not in already
        and item.get("artifacts", {}).get("publish_report.md")
    ]
    remaining.sort(key=lambda item: float(item.get("quality_score") or 0), reverse=True)
    for item in remaining[:2]:
        selected.append((item["ticker"], Path(item["artifacts"]["publish_report.md"])))
    return selected


def _report_paths_for_tickers(dashboard: dict, tickers: list[str]) -> list[tuple[str, Path]]:
    items = {item.get("ticker"): item for item in dashboard.get("items", [])}
    selected = []
    for ticker in tickers:
        item = items.get(ticker)
        if not item or item.get("status") != "passed":
            continue
        path = Path(item.get("artifacts", {}).get("publish_report.md", ""))
        if path.exists():
            selected.append((ticker, path))
    return selected


def _release_status_payload(fresh_dashboard: dict, operating_dashboard: dict) -> dict:
    summary = operating_dashboard.get("summary", {})
    return {
        "release_name": "Pilot-v1 Operating Baseline",
        "date": datetime.now(timezone.utc).date().isoformat(),
        "latest_batch_id": operating_dashboard.get("batch_id"),
        "passed_count": summary.get("passed", 0),
        "manual_review_count": summary.get("manual_review", 0),
        "failed_count": summary.get("failed", 0),
        "gold_templates": GOLD_TEMPLATES,
        "near_gold_templates": NEAR_GOLD_TEMPLATES,
        "usable_internal_drafts": USABLE_INTERNAL_DRAFTS,
        "known_manual_review_groups": sorted(
            {
                group
                for item in [*fresh_dashboard.get("manual_review_queue", []), *operating_dashboard.get("manual_review_queue", [])]
                for group in item.get("manual_review_reasons", [])
            }
        ),
        "publish_ready": False,
        "pilot_ready": True,
    }


def _pilot_overview_markdown() -> str:
    return "\n".join(
        [
            "# PILOT_V1_OVERVIEW",
            "",
            "## Was ist Quellwert Research Agent?",
            "",
            "Quellwert Research Agent ist ein deterministischer Research- und Review-Stack fuer interne Aktienanalysen. Python berechnet Kennzahlen, reconciliert Quellen, validiert Claims und erzwingt Review-Gates; der Publish-Layer formuliert nur auf Basis dieser validierten Pakete.",
            "",
            "## Was kann das System?",
            "",
            "- SEC-, IR- und Preisquellen in Data-/Metrics-/Evidence-Pakete ueberfuehren.",
            "- Ratings ueber DecisionPacket und Quality Gates begrenzen.",
            "- `final_report.md` und `publish_report.md` mit Evidence Appendix erzeugen.",
            "- Batch-Runs, Dashboard, Manual-Review-Queue und Review-Bundles erzeugen.",
            "",
            "## Was kann es nicht?",
            "",
            "- Keine unbeaufsichtigte externe Publikation.",
            "- Keine Guard-Bypasses fuer fehlende FCF-, KPI- oder Reconciliation-Supports.",
            "- Keine finale Wahrheit bei True-Anomalien ohne menschliche Pruefung.",
            "",
            "## Pipeline-Uebersicht",
            "",
            "1. Source ingestion / packet build",
            "2. Canonical reconciliation",
            "3. Validation + audit",
            "4. Decision layer + quality score",
            "5. Publish/final report generation",
            "6. Batch dashboard + manual-review triage",
            "",
            "## Kontrollschichten",
            "",
            "- ValidationReport",
            "- Markdown Auditor",
            "- Evidence Ledger",
            "- Reconciliation warnings",
            "- DecisionPacket / rating permission",
            "- Quality score / publishability gate",
            "",
            "## Beispiel-Output",
            "",
            "Siehe `EXAMPLE_REPORTS/` und `DASHBOARD_EXAMPLE/` im Release-Paket.",
            "",
            "## Empfohlener Betriebsmodus",
            "",
            "Interner Pilotbetrieb mit menschlicher Review-Schicht. Passed Reports sind review-faehige interne Drafts; Manual Review ist ein echter Stop, kein Soft Warning.",
            "",
            "## Grenzen",
            "",
            "Pilot-v1 ist absichtlich streng. Die Staerke liegt in der Gate-Disziplin und Erklaerbarkeit, nicht in maximaler Pass-Rate.",
            "",
        ]
    )


def _technical_architecture_markdown() -> str:
    return "\n".join(
        [
            "# TECHNICAL_ARCHITECTURE",
            "",
            "## DataPacket",
            "",
            "Preis-, Event- und Grundkontext fuer den Reportlauf.",
            "",
            "## MetricsPacket",
            "",
            "Technicals, Fundamentals und Valuation aus deterministischen Berechnungen.",
            "",
            "## ValidationReport",
            "",
            "Fruehe Daten- und Logikpruefung vor dem Report-Audit.",
            "",
            "## EvidenceLedger",
            "",
            "Claim- und Metric-Evidence mit Source-Typ, Confidence und IDs.",
            "",
            "## CanonicalFinancials",
            "",
            "Reconciliertes Zielmodell ueber SEC-, IR- und Derived-Facts.",
            "",
            "## Reconciliation",
            "",
            "Source-Konflikte, Frame-Varianten und Current-Period-Facts werden vor der Publikation sichtbar gemacht.",
            "",
            "## Markdown Auditor",
            "",
            "Lintet Finaltext gegen MetricsPacket, Evidence und Decision-Grenzen.",
            "",
            "## Decision Layer",
            "",
            "Erzeugt RatingPermission, Allowed/Blocked Ratings und operativen Rating-Korridor.",
            "",
            "## Quality Score",
            "",
            "Verdichtet Content-, Evidence-, Logic- und Writing-Qualitaet zu einem Publish-Gate.",
            "",
            "## Auto-Repair",
            "",
            "Kontrollierte Reparaturschleife fuer fehlerhafte Drafts, ohne Guard-Lockerung.",
            "",
            "## Batch/Dashboard",
            "",
            "Mehrere Ticker laufen isoliert; Dashboard, Manifest, Manual-Review-Triage und Review-Bundles werden batchweise erzeugt.",
            "",
            "## Outcome Backtesting",
            "",
            "ReportManifests werden spaeter gegen Forward-Return-Fenster bewertet.",
            "",
            "## Calibration Shadow Mode",
            "",
            "Kalibrierung bleibt von Live-Ratings getrennt, bis genug Outcome-Zeitfenster reif sind.",
            "",
            "## publish_report.md vs final_report.md",
            "",
            "`final_report.md` bleibt die interne, claim-nahe Vollspur. `publish_report.md` ist die externere, lesbarere Surface mit Appendix statt Claim-IDs im Haupttext.",
            "",
        ]
    )


def _operating_runbook_markdown(fresh_dir: Path, operating_dir: Path) -> str:
    return "\n".join(
        [
            "# OPERATING_RUNBOOK",
            "",
            "## Wie Fresh Batch gestartet wird",
            "",
            f"`python -m research_agent.batch.batch_runner --config {fresh_dir.parent / (fresh_dir.name + '_config.json')}`",
            "",
            "## Wie Dashboard gelesen wird",
            "",
            "Auf `status`, `quality_score`, `external_display_rating`, `manual_review_reasons`, `true_source_disagreements`, `evidence_warnings` und `reconciliation_warnings` pro Ticker schauen.",
            "",
            "## Was passed bedeutet",
            "",
            "Passed bedeutet: kein Blocking-Audit, publishable Quality Gate, harte Claims voll evidence-gemappt und keine manuelle Stop-Regel aktiv.",
            "",
            "## Was manual_review bedeutet",
            "",
            "Manual Review ist ein echter Review-Stop. Der Report darf nicht als quasi-passed behandelt oder still extern weitergereicht werden.",
            "",
            "## Wann man Reports extern reviewen lassen muss",
            "",
            "- Immer vor externer Publikation.",
            "- Immer bei True-Anomaly, Reconciliation-Noise oder FCF-/Current-Period-Sonderfaellen.",
            "",
            "## Wie Outcome Backtesting spaeter laeuft",
            "",
            "1D kann frueh geprueft werden. 5D/10D/20D/60D erst werten, wenn die Preisfenster vollstaendig sind.",
            "",
            "## Welche Fehler nicht automatisch gefixt werden sollen",
            "",
            "- True-Anomalien",
            "- period_bug / Reconciliation-Brueche",
            "- fehlender FCF-Support fuer offensivere Ratings",
            "- fehlende Current-Period-Kontexte, die neue echte Daten verlangen",
            "",
            f"Operating Pilot baseline: `{operating_dir}`",
            "",
        ]
    )


def _known_limitations_markdown() -> str:
    return "\n".join(
        [
            "# KNOWN_LIMITATIONS",
            "",
            "- Nicht unbeaufsichtigt publish-ready.",
            "- IR-/Guidance-Abdeckung ist noch nicht fuer das ganze Universum vollstaendig.",
            "- Valuation/Sensitivity und Action-Trigger sind besser, aber noch nicht durchgehend Near-Gold.",
            "- Outcome-Kalibrierung braucht mehr Zeitfenster als nur 1D.",
            "- True-Anomalien brauchen menschliche Pruefung und duerfen nicht wegerklaert werden.",
            "- `manual_review` darf nicht ignoriert oder in stilles Passed uebersetzt werden.",
            "",
        ]
    )


def _outcome_status_markdown(outcome_review: dict) -> str:
    counts = outcome_review.get("complete_window_counts", {})
    latest_date = outcome_review.get("latest_available_outcome_date")
    return "\n".join(
        [
            "# OUTCOME_STATUS",
            "",
            f"- Latest available outcome date: `{latest_date}`",
            "- 1D ist aktuell die einzige vollstaendig reife Auswertungsschicht.",
            "- 5D/10D/20D/60D erst bewerten, wenn das Preisfenster vollstaendig ist.",
            "",
            "## Window Status",
            "",
            f"- 1D: `{counts.get('1d', 0)}` complete reports",
            f"- 5D: `{counts.get('5d', 0)}` complete reports",
            f"- 10D: `{counts.get('10d', 0)}` complete reports",
            f"- 20D: `{counts.get('20d', 0)}` complete reports",
            f"- 60D: `{counts.get('60d', 0)}` complete reports",
            "",
            "## Hinweis",
            "",
            "5D/10D/20D/60D duerfen nicht als Bewertung genutzt werden, solange sie im Outcome-Review als unvollstaendig markiert sind.",
            "",
            "## Micron / MU",
            "",
            "Der bestehende Outcome-Review fuehrt MU als Manual-Review-Fall mit spaeter positiver Kursentwicklung. Das ist ein wichtiges Kalibrierungsbeispiel, aber kein Argument fuer Guard-Lockerung.",
            "",
        ]
    )


def _cost_runtime_markdown(fresh_dir: Path, operating_dir: Path) -> str:
    fresh_manifest = _load_json(fresh_dir / "batch_manifest.json")
    operating_manifest = _load_json(operating_dir / "batch_manifest.json")
    fresh_runtime = _runtime_minutes(fresh_manifest)
    operating_runtime = _runtime_minutes(operating_manifest)
    return "\n".join(
        [
            "# COST_AND_RUNTIME_ESTIMATE",
            "",
            f"- Typical fresh batch runtime from the latest run: `{fresh_runtime}` minutes.",
            f"- Operating pilot runtime from the latest run: `{operating_runtime}` minutes.",
            "- Model usage / token / cost logging is not consistently populated in the checked-in batch artifacts; current estimates should be treated as partial.",
            "- Logged generation baseline uses `ollama / deepseek-v4-pro` for the deterministic pilot runs.",
            "",
            "## DeepSeek vs GPT-Review",
            "",
            "- DeepSeek: primary batch generation / deterministic pilot throughput.",
            "- GPT-Review: selective human-supervised publish review, release-note polish and edge-case challenge runs.",
            "",
            "## Empfohlener Betriebsmodus zur Kostensenkung",
            "",
            "- Grosser Batch in `source_ingestion_mode` laufen lassen.",
            "- Nur passed Reports in den Publish-Review-Bundle nehmen.",
            "- GPT nur fuer Passed-Stichprobe und Manual-Review-Sonderfaelle zuschalten.",
            "",
        ]
    )


def _next_30_days_markdown() -> str:
    return "\n".join(
        [
            "# NEXT_30_DAYS",
            "",
            "- Woche 1: Pilotbetrieb, manuelle Review, Outcome 5D vorbereiten.",
            "- Woche 2: IR/Guidance Coverage priorisieren.",
            "- Woche 3: 20D Outcome auswerten.",
            "- Woche 4: Calibration Shadow Report.",
            "- Keine neuen Backbone-Phasen ohne echten neuen Fehler aus Betrieb, Review oder Outcome.",
            "",
        ]
    )


def _render_manual_review_triage_markdown(payload: dict) -> str:
    lines = [
        f"# Manual Review Triage - {payload.get('batch_id')}",
        "",
        f"- Generated at: `{payload.get('generated_at')}`",
        f"- Total manual review: `{payload.get('total_manual_review')}`",
        "",
        "## Group Summary",
        "",
    ]
    if payload.get("count_by_reason_group"):
        for reason, count in sorted(payload["count_by_reason_group"].items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- `{reason}`: `{count}`")
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Manual Review Items",
            "",
            "| Ticker | Reasons | Primary Root Cause | Fixability | Recommended Next Action |",
            "|---|---|---|---|---|",
        ]
    )
    for item in payload.get("items", []):
        lines.append(
            f"| {item['ticker']} | {', '.join(item.get('reason_groups', [])) or 'none'} | "
            f"{item.get('primary_root_cause')} | {item.get('fixability')} | "
            f"{item.get('recommended_next_action')} |"
        )
    return "\n".join(lines) + "\n"


def _render_operating_review_markdown(review: dict) -> str:
    lines = [
        f"# Operating Pilot Review - {review.get('batch_id')}",
        "",
        f"- Passed: `{review.get('passed_count')}`",
        f"- Manual review: `{review.get('manual_review_count')}`",
        f"- Failed: `{review.get('failed_count')}`",
        f"- Avg quality: `{review.get('avg_quality')}`",
        f"- Median quality: `{review.get('median_quality')}`",
        f"- Lowest quality: `{review.get('lowest_quality')}`",
        "",
        "## Passed Tickers",
        "",
        f"- {', '.join(review.get('passed_tickers', [])) or 'None'}",
        "",
        "## Manual Review Tickers",
        "",
        f"- {', '.join(review.get('manual_review_tickers', [])) or 'None'}",
        "",
        "## Top Manual Review Reasons",
        "",
    ]
    lines.extend(_render_counter_lines(review.get("top_manual_review_reasons", {})))
    lines.extend(
        [
            "",
            "## Top Data Coverage Gaps",
            "",
        ]
    )
    lines.extend(_render_counter_lines(review.get("top_data_coverage_gaps", {})))
    lines.extend(
        [
            "",
            "## Top Evidence / Reconciliation Issues",
            "",
        ]
    )
    lines.extend(_render_counter_lines(review.get("top_evidence_reconciliation_issues", {})))
    lines.extend(
        [
            "",
            "## False Pass Candidates",
            "",
            f"- {', '.join(review.get('false_pass_candidates', [])) or 'None'}",
            "",
            "## Best 5 Reports",
            "",
        ]
    )
    lines.extend(_render_rank_lines(review.get("best_5_reports", [])))
    lines.extend(
        [
            "",
            "## Worst 5 Reports",
            "",
        ]
    )
    lines.extend(_render_rank_lines(review.get("worst_5_reports", [])))
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            f"- `{review.get('recommendation')}`",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_counter_lines(counter_payload: dict) -> list[str]:
    if not counter_payload:
        return ["- None"]
    return [f"- `{key}`: `{value}`" for key, value in counter_payload.items()]


def _render_rank_lines(items: list[dict]) -> list[str]:
    if not items:
        return ["- None"]
    return [f"- `{item['ticker']}`: quality `{item['quality_score']}` status `{item['status']}`" for item in items]


def _reason_groups(item: dict) -> list[str]:
    counts = item.get("counts", {})
    codes = set(item.get("manual_review_reasons", []))
    groups = []
    if counts.get("true_anomaly", 0) or codes.intersection({"TRUE_FINANCIAL_ANOMALY", "TRUE_VALUATION_ANOMALY", "EXTREME_VALUATION_REQUIRES_REVIEW"}):
        groups.append("true_anomaly")
    if counts.get("period_bug", 0) or codes.intersection({"PERIOD_DENOMINATOR_BUG", "PERIOD_MISMATCH"}):
        groups.append("period_bug")
    if counts.get("guard_threshold_review", 0) or "GUARD_THRESHOLD_REVIEW" in codes:
        groups.append("guard_too_strict")
    if counts.get("early_commercial_capital_intensive_tech_count", 0) or "EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH_MANUAL_REVIEW_PROFILE" in codes:
        groups.append("early_commercial_capital_intensive_tech")
    if counts.get("missing_current_period_context_count", 0) or codes.intersection(
        {"MISSING_CURRENT_PERIOD_CONTEXT", "MISSING_CURRENT_PERIOD_KPI_CONTEXT", "AVGO_CURRENT_KPI_CONTEXT_REQUIRED"}
    ):
        groups.append("missing_current_period_context")
    if counts.get("fcf_unavailable_block_count", 0) or "MISSING_FCF_SUPPORT_FOR_ACCUMULATE" in codes:
        groups.append("missing_fcf_support")
    if counts.get("company_defined_fcf_mismatch_count", 0) or counts.get("fcf_ocf_inconsistency_count", 0) or codes.intersection(
        {"CURRENT_PERIOD_IR_RECONCILIATION_REQUIRED", "COMPANY_DEFINED_FCF_MISMATCH", "COMPANY_DEFINED_FCF_OCF_INCONSISTENCY"}
    ):
        groups.append("current_period_ir_reconciliation_required")
    if counts.get("evidence_warnings", 0) or counts.get("validation_errors", 0) or codes.intersection(
        {
            "MISSING_EVIDENCE_FOR_HARD_CLAIM",
            "LOW_AUTHORITY_EVIDENCE_FOR_HARD_CLAIM",
            "NO_PRIMARY_EVIDENCE_FOR_HARD_METRIC",
            "MISSING_EVIDENCE_FOR_METRIC",
            "UNSUPPORTED_GUIDANCE_CLAIM",
            "UNSUPPORTED_EARNINGS_EVENT_CLAIM",
        }
    ):
        groups.append("data_gap")
    if counts.get("substantive_claim_count", 0) < 12 or counts.get("current_period_kpi_claim_count", 0) < 3:
        groups.append("claim_substance_gap")
    return list(dict.fromkeys(groups or ["data_gap"]))


def _primary_root_cause(reason_groups: list[str]) -> str:
    priority = [
        "true_anomaly",
        "current_period_ir_reconciliation_required",
        "early_commercial_capital_intensive_tech",
        "missing_fcf_support",
        "missing_current_period_context",
        "period_bug",
        "data_gap",
        "claim_substance_gap",
        "guard_too_strict",
    ]
    for candidate in priority:
        if candidate in reason_groups:
            return candidate
    return reason_groups[0] if reason_groups else "data_gap"


def _fixability_for_item(primary_root_cause: str, item: dict) -> str:
    if primary_root_cause == "true_anomaly":
        return "2. keep manual_review"
    if primary_root_cause == "early_commercial_capital_intensive_tech":
        return "2. keep manual_review"
    if primary_root_cause in {"period_bug", "current_period_ir_reconciliation_required"}:
        return "5. reconciliation fix"
    if primary_root_cause == "guard_too_strict":
        return "3. guard tuning"
    if primary_root_cause == "claim_substance_gap":
        return "4. template improvement"
    if primary_root_cause == "missing_current_period_context":
        if item.get("current_period_kpi_claim_count", 0) > 0:
            return "4. template improvement"
        return "1. add IR data"
    return "1. add IR data"


def _recommended_next_action(primary_root_cause: str, fixability: str, item: dict) -> str:
    ticker = item.get("ticker")
    if primary_root_cause == "true_anomaly":
        return f"Keep `{ticker}` in manual_review until the anomaly is explained or disproved."
    if fixability.startswith("5."):
        return f"Reconcile company-period metrics for `{ticker}` before any publish promotion."
    if fixability.startswith("4."):
        return f"Improve the report template/prose for `{ticker}` and rerun without changing guards."
    if fixability.startswith("3."):
        return f"Review whether `{ticker}` is a guard-threshold edge case; do not loosen guards blindly."
    return f"Add or confirm stronger IR/current-period support for `{ticker}` before rerun."


def _is_false_pass_candidate(item: dict) -> bool:
    counts = item.get("counts", {})
    return any(
        [
            counts.get("hard_claim_evidence_ratio", 100) < 100,
            counts.get("validation_errors", 0) > 0,
            counts.get("audit_errors", 0) > 0,
            counts.get("evidence_warnings", 0) > 0,
            counts.get("missing_current_period_context_count", 0) > 0,
            counts.get("company_defined_fcf_mismatch_count", 0) > 0,
            counts.get("fcf_unavailable_block_count", 0) > 0,
        ]
    )


def _operating_pilot_recommendation(
    failed: int,
    avg_quality: Optional[float],
    false_pass_candidates: list[str],
) -> str:
    if failed <= 3 and (avg_quality or 0) >= 75 and not false_pass_candidates:
        return "pilotfaehig"
    return "nicht pilotfaehig"


def _ticker_quality(item: dict) -> dict:
    return {
        "ticker": item.get("ticker"),
        "quality_score": item.get("quality_score"),
        "status": item.get("status"),
    }


def _runtime_minutes(manifest: dict) -> str:
    started_at = manifest.get("started_at")
    finished_at = manifest.get("finished_at")
    if not started_at or not finished_at:
        return "not logged"
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        finish = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
    except ValueError:
        return "not logged"
    minutes = (finish - start).total_seconds() / 60
    return f"{minutes:.1f}"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate pilot batch support artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    triage_parser = subparsers.add_parser("manual-review-triage")
    triage_parser.add_argument("--batch-dir", required=True)

    review_parser = subparsers.add_parser("operating-review")
    review_parser.add_argument("--batch-dir", required=True)

    release_parser = subparsers.add_parser("release-package")
    release_parser.add_argument("--fresh-batch-dir", required=True)
    release_parser.add_argument("--operating-batch-dir", required=True)
    release_parser.add_argument("--output-dir", required=True)

    args = parser.parse_args(argv)
    if args.command == "manual-review-triage":
        md_path, json_path = generate_manual_review_triage(args.batch_dir)
        print(md_path)
        print(json_path)
        return 0
    if args.command == "operating-review":
        path = generate_operating_pilot_review(args.batch_dir)
        print(path)
        return 0
    if args.command == "release-package":
        path = generate_release_package(
            fresh_batch_dir=args.fresh_batch_dir,
            operating_batch_dir=args.operating_batch_dir,
            output_dir=args.output_dir,
        )
        print(path)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
