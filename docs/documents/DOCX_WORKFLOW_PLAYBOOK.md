# DOCX Workflow Playbook

Status: active draft
Scope: LIONCOM / Vega / Vivi document workflows
Risk class: R2 local write within project
Runtime changes: none

## Purpose

Use DOCX as a controlled document artifact format, not as an invisible editing surface. Every DOCX task must preserve the source, produce reviewable intermediate artifacts, and validate that content and layout did not silently break.

## Use Cases

- Read a Word document and extract reviewable text.
- Create a Word document from approved Markdown.
- Prepare a review or redline summary.
- Prepare a PDF-ready DOCX for an operator package.
- Confirm that no hidden or untracked changes were introduced.

## Rules

- Never overwrite the original file.
- Always create a working copy or new output file.
- Document every material change in `change_summary.md`.
- Check tables, images, footnotes, headers, footers, lists and page breaks.
- Do not embed fonts or export fonts unless the operator explicitly asks.
- Check metadata risk before sharing outside the local workspace.
- Document output paths in the handoff.
- Do not claim a DOCX is final unless validation passed.

## Required Artifacts

- `source_file`
- `working_copy.docx`
- `extracted_text.md`
- `change_summary.md`
- `output.docx`
- `validation_report.md`

## Validation

- File opens without repair prompts.
- Page structure is plausible.
- Tables are preserved.
- Images remain present and correctly placed.
- Footnotes, headers and footers are not lost.
- No unexpected empty pages.
- German umlauts and other Unicode characters render correctly.
- Metadata risk is checked and recorded.

## Vivi Review

Vivi checks:

- layout risk
- content drift risk
- missing validation evidence
- metadata/export risk
- whether "final" language is justified

Vivi must not report a DOCX as final without a validation report.

## Forbidden

- Directly editing the only source copy.
- Hiding tracked changes or comments without operator instruction.
- Treating text extraction as layout validation.
- Sending or publishing any generated document.
- Converting files without explicit operator input.
