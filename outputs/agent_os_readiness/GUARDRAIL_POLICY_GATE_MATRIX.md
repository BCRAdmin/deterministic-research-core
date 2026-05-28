# Guardrail Policy Gate Matrix

Grouped policy surface for Agent-OS guardrail findings. This does not grant runtime rights.

Gates: 4
Highest severity: `high`

| Gate | Check | Category | Severity | Findings | Operator gate | Status | Next action |
| --- | --- | --- | --- | ---: | ---: | --- | --- |
| `guardrail-gate-e6fff2ece826` | `auto_runtime_mutation` | `automation_prompt` | `high` | 15 | true | `report_level_gate_active` | `convert_to_policy_engine_rule_before_runtime_expansion` |
| `guardrail-gate-53982611432d` | `skill_background_or_self_modify` | `skill_package` | `high` | 19 | true | `report_level_gate_active` | `convert_to_policy_engine_rule_before_runtime_expansion` |
| `guardrail-gate-a535cf2e024d` | `skill_memory_write` | `skill_package` | `high` | 4 | true | `report_level_gate_active` | `convert_to_policy_engine_rule_before_runtime_expansion` |
| `guardrail-gate-4c06c50461da` | `skill_network_or_install` | `skill_package` | `high` | 2 | true | `report_level_gate_active` | `convert_to_policy_engine_rule_before_runtime_expansion` |
