# Automation Workflows Playbook

Status: active draft
Scope: Codex app automations / Utility / Outcome / Data Ops reviews
Risk class: R6 pattern constrained to scheduled review only
Runtime changes: none

## Purpose

Automations may remind, inspect data maturity and produce review artifacts. They must not become autonomous feature work or bypass Operator Gates.

## Allowed Automations

- Outcome Window Check.
- Utility 7/14 Day Review.
- Data Freshness Check.
- AdSense/CMP status check.
- GSC/Event data maturity check.
- No-action reminder.

## Forbidden

- Automatically change code.
- Automatically release reports.
- Automatically enable Ads or Affiliate.
- Automatically loosen guards.
- Automatically update Obsidian Backbone.
- Automatically publish.
- Automatically create runtime rights, API keys or background agents.

## Timing Rules

- Use exact schedules only for real calendar deadlines.
- Use flexible schedules for review tasks.
- Use condition-watch prompts for data maturity.
- If data is not mature, output `no_action`.

## Output Contract

Every automation review should report:

- `status`
- `missing_data`
- `allowed_next_action`
- `blocked_gates`
- `no_action_if_not_mature`

## Existing Automations

- Utility Websites Mature 14-Day GSC/Event Review.
- Re-run 5D Outcome.
- Outcome 10D/20D/60D checks may be created only when a real outcome window exists.

## Guardrails

- No runtime mutation from automation alone.
- No Public/Promotion Gate bypass.
- No Obsidian autowrites.
- No hidden scope shift.
