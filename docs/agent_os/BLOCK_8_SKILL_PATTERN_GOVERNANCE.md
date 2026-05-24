# Block 8 Skill Pattern Governance

Status: `implemented_local_guard`

Block 8 fuehrt externe Skill-Repos und Skill-Patterns nicht als Runtime-Wahrheit ein. Gute Muster werden in lokale Playbooks, Hold-Register und Review-Gates übersetzt. Riskante Runtime-Ideen bleiben blockiert, bis Source, Risiko, Operator-Gate und Obsidian-Kompatibilität geprüft sind.

## Lokaler Guard

Command:

```bash
python3 scripts/ops/skill_pattern_governance_check.py
```

JSON:

```bash
python3 scripts/ops/skill_pattern_governance_check.py --json
```

Der Guard prüft:

- die erwarteten DOCX/XLSX/PDF/Humanizer/Automation/Skill-Inventory/Media-Backlog/Hold-Register-Playbooks
- `outputs/skill_playbooks/REMAINING_SKILL_PATTERN_IMPLEMENTATION_SUMMARY.json`
- `docs/skills/HIGH_RISK_SKILLS_HOLD_REGISTER.json`
- den lokalen Helper `scripts/skills/local_skill_inventory_scan.py`

## Blockierende Abweichungen

Der Guard blockt, wenn:

- ein Pflicht-Playbook fehlt
- `runtime_changes` nicht `none` ist
- `not_implemented` nicht mehr alle geblockten Runtime-Ausweitungen enthaelt
- High-Risk-Hold-Items fehlen oder kein Operator-Gate erzwingen
- der lokale Skill-Inventory-Helper nicht mehr als local-only/read-only dokumentiert ist
- der Helper einfache verbotene Source-Marker für Netzwerk, Subprocess oder Writes enthaelt

## Grenze

Dieser Guard ist nur ein lokaler Vertragscheck. Er installiert keine Skills, fuehrt keine externen Tools aus, schreibt nicht in Obsidian und ersetzt kein Operator-Go für echte Runtime-, Public-, Publishing-, API-, Desktop-Control- oder Autonomy-Änderungen.
