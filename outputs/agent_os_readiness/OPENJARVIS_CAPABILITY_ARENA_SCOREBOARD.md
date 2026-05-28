# OpenJarvis Capability Arena

- Status: `PASS`
- Modus: `shadow_read_only`
- Source of Truth: `False`
- Aufgaben: `30/30`
- Sichere Quellen: `87`
- Baseline-Dokumente: `6`
- Shadow-Dokumente: `87`
- Runtime-Aktion: `False`
- Empfehlung: `promote_shadow_retrieval_benchmark_to_next_read_only_trial`

## Scoreboard

- `pig_obsidian_baseline`: Ø `82.81`, PASS `19`, WARN `10`, FAIL `1`, Wins `0`
- `openjarvis_shadow`: Ø `96.5`, PASS `30`, WARN `0`, FAIL `0`, Wins `12`

## Kategorien

- `autonomy`: Shadow Ø `100.0`, Baseline Ø `98.15`, Shadow Wins `0`, Baseline Wins `0`, Ties `4`
- `code_qa_shadow`: Shadow Ø `82.5`, Baseline Ø `56.15`, Shadow Wins `1`, Baseline Wins `0`, Ties `0`
- `future_github`: Shadow Ø `82.5`, Baseline Ø `63.0`, Shadow Wins `1`, Baseline Wins `0`, Ties `0`
- `kanzlei`: Shadow Ø `100.0`, Baseline Ø `98.3`, Shadow Wins `0`, Baseline Wins `0`, Ties `2`
- `lioncom`: Shadow Ø `91.25`, Baseline Ø `50.5`, Shadow Wins `2`, Baseline Wins `0`, Ties `0`
- `memory`: Shadow Ø `100.0`, Baseline Ø `98.0`, Shadow Wins `0`, Baseline Wins `0`, Ties `2`
- `openjarvis_policy`: Shadow Ø `100.0`, Baseline Ø `61.76`, Shadow Wins `6`, Baseline Wins `0`, Ties `0`
- `openjarvis_surface`: Shadow Ø `91.25`, Baseline Ø `80.5`, Shadow Wins `1`, Baseline Wins `0`, Ties `1`
- `pig_truth`: Shadow Ø `88.33`, Baseline Ø `86.33`, Shadow Wins `1`, Baseline Wins `0`, Ties `2`
- `quality`: Shadow Ø `100.0`, Baseline Ø `98.6`, Shadow Wins `0`, Baseline Wins `0`, Ties `1`
- `room16`: Shadow Ø `100.0`, Baseline Ø `98.15`, Shadow Wins `0`, Baseline Wins `0`, Ties `4`
- `vivi_worker`: Shadow Ø `100.0`, Baseline Ø `98.6`, Shadow Wins `0`, Baseline Wins `0`, Ties `2`

## Schwächste Shadow-Aufgaben

- `oj_capability_lab_evidence` `PASS` score `82.5`: missing sources `quality_os_operator_surface`, missing terms `none`
- `oj_code_qa_shadow_projects` `PASS` score `82.5`: missing sources `package.json`, missing terms `none`
- `pig_operator_surface_truth` `PASS` score `82.5`: missing sources `pig.py`, missing terms `none`
- `pig_rule_propagation` `PASS` score `82.5`: missing sources `pig.py`, missing terms `none`
- `lioncom_planning_quality_surface` `PASS` score `82.5`: missing sources `lib/types`, missing terms `none`
- `github_digest_gate` `PASS` score `82.5`: missing sources `OPENJARVIS_THREAT_MODEL`, missing terms `none`
- `oj_policy_shadow_mode` `PASS` score `100.0`: missing sources `none`, missing terms `none`
- `oj_policy_no_runtime` `PASS` score `100.0`: missing sources `none`, missing terms `none`

## Nicht-Aktionen

- `no_openjarvis_runtime_execution`
- `no_shell_exec`
- `no_file_write_by_openjarvis`
- `no_network`
- `no_github_api`
- `no_commit_push_release`
