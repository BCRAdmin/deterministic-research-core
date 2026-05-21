# Materialbedarf Next-Step Verification - Route Plan

Status: `candidate_only`
Run type: `system_verification`
Date: `2026-05-21`

## Auftrag

Teste, ob das neue Vega/Vivi/Deliverable-Swarm-System bei einem echten kleinen
Projektfall korrekt arbeitet:

- richtige Projektkarte waehlen
- richtige Deliverable-Lanes binden
- Output-Pfade erzeugen
- Gates sichtbar halten
- kein blockiertes Monetarisierungs-, Provider-, Deploy- oder Public-Verhalten oeffnen
- Memory-Capture und Git-Hygiene am Ende pruefen

## Projekt-Routing

- Projekt: `Project - Utility Websites Portfolio`
- Nicht routen zu: `Project - Utility Wortcluster`
- Begruendung: Der Fall betrifft Materialbedarf, Mess-/Trust-/Revenue-Readiness
  und nicht Wortquelle, Regelset oder Solver-MVP.

## Deliverable-Swarm-Lanes

| Lane | Aufgabe | Output |
| --- | --- | --- |
| `orchestrator` | Scope binden, Gates einfrieren, Artefaktpfade festlegen | `ROUTE_PLAN.md` |
| `research` | Projekt-/Roadmap-/Review-Wahrheit auswerten | `DECISION_ARTIFACT.md` |
| `data` | Datenreife und fehlende GSC-/Event-Exporte pruefen | `DECISION_ARTIFACT.md` |
| `docs` | Verification-Readout, Claims-to-check und Abschlussbericht erzeugen | `VERIFICATION_REPORT.md` |

## Output-Vertrag

- `artifact_id`: `materialbedarf_next_step_verification_2026_05_21`
- `lane_id`: `orchestrator,research,data,docs`
- `artifact_type`: `route_plan,decision_options,analysis_report,change_summary`
- `output_path`: `outputs/system_verification/materialbedarf_next_step_2026-05-21/`
- `status`: `candidate_only`
- `verifier`: `local_pytest_ruff_json_canvas_git_diff_check_agent_os_readiness`
- `blocked_gates`: `ads,live_affiliate,production_deploy,external_provider,new_domain_assumption,public_claim`
- `next_action`: `mature_data_review_after_2026_06_01_or_operator_go_for_manual_partner_prep_only`

## Harte Gates

- Keine Ads.
- Keine Live-Affiliate-Links.
- Kein Production-/Deploy-Go.
- Keine externen Provider oder Credentials.
- Keine neuen Domainannahmen.
- Kein Public-/Legal-/Revenue-Claim aus Mock- oder Candidate-Artefakten.
