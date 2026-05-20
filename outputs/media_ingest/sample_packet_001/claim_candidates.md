# Claim Candidates

Status: evidence candidates only  
Sample type: synthetic_operator_test  
Evidence use: not usable as evidence  
Report use: not usable in reports

| claim_id | timestamp | speaker | claim_text | confidence | requires_verification | usable_in_report | reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sample_claim_001 | 00:00 | Operator Test Speaker | This packet is a synthetic media ingest test and is not a real company source. | high | true | false | Synthetic packet marker; retained only to test candidate extraction. |
| sample_claim_002 | 00:12 | Operator Test Speaker | Media ingest should preserve source metadata and mark extracted claims as candidates. | high | true | false | Workflow claim from synthetic test, not external evidence. |
| sample_claim_003 | 00:25 | Operator Test Speaker | No report, MetricsPacket, DecisionPacket, EvidenceLedger, rating, guard, calibration, Obsidian Backbone, or public output should change during the dry run. | high | true | false | Guardrail assertion for dry-run validation; not evidence. |
| sample_claim_004 | 00:42 | Operator Test Speaker | A real future media packet would need authenticity, rights, speaker, timestamp and primary-source checks before hard-claim use. | high | true | false | Policy rehearsal from synthetic test; requires verification before real use. |

## Boundary

No candidate in this file may be promoted to EvidenceLedger or used in a report.
