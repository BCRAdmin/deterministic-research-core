# XLSX Workflow Playbook

Status: active draft
Scope: Room16 / Quellwert / Utility / Data Ops tables
Risk class: R2 local write within project
Runtime changes: none

## Purpose

Use XLSX files as controlled workbook artifacts. The default is to inspect, profile and validate before editing. Formulas, formats, hidden sheets, pivots and charts are treated as risk surfaces.

## Use Cases

- Read an XLSX workbook.
- Validate data and schema.
- Create a result or audit workbook.
- Export Batch, Outcome or Guardrail matrices.
- Preserve formulas instead of blindly overwriting them.

## Rules

- Never overwrite the original workbook.
- Detect and preserve formula cells.
- Check datatypes before writing.
- Check date, currency and percentage formats.
- Inspect hidden sheets.
- Document pivots and charts; do not blindly mutate them.
- Do not use LibreOffice or PDF paths for spreadsheet tasks unless there is a specific reason.
- Record any type coercion risk.

## Required Artifacts

- `input_summary.md`
- `schema_profile.json`
- `validation_report.md`
- `output.xlsx`
- `changelog.md`

## Validation

- Workbook opens.
- Sheet count matches expectation.
- Row and column counts are plausible.
- Formula cells are preserved or explicitly documented.
- Date and number formats are preserved.
- No silent type coercion.
- Hidden sheets and workbook protection are reported.

## Room16 / Quellwert Use Cases

- Outcome Review XLSX.
- Guardrail Coverage Matrix XLSX.
- Data Ops Backlog XLSX.
- Utility GSC/Event Review XLSX.

## Forbidden

- Blind formula overwrite.
- Treating CSV roundtrip as safe XLSX editing.
- Dropping hidden sheets without review.
- Claiming workbook validation from cell reads alone.
- Publishing or sending workbooks without operator approval.
