# PDF Render Playbook

Status: active draft
Scope: Room16 / Quellwert / Utility operator artifacts
Risk class: R2 local write within project
Runtime changes: none

## Purpose

PDF is a final or internal render artifact, not proof that content is approved. Markdown and JSON remain the primary review surfaces until promotion.

## PDF Lanes

| Lane | Meaning | Public use |
| --- | --- | --- |
| `markdown_first_qa` | Work remains in Markdown/JSON for review. | No |
| `internal_best_pdf` | Optional internal render for operator reading. | No |
| `public_final_pdf` | Final promoted render after gates. | Yes, only after promotion |

## Rules

- A PDF is not evidence of content approval.
- UTF-8 and German umlauts must render correctly.
- Table of contents must be checked when present.
- Page breaks must be reviewed.
- Tables must not be cut off.
- No unexpected empty pages.
- Headers and footers must match the lane.
- Do not render blocked or `manual_review` artifacts unless clearly marked `internal_best_pdf`.

## Required QA

- `source_markdown_path`
- `render_mode`
- `pdf_path`
- `page_count`
- `text_extract_sanity`
- `unicode_test`
- `status_lane_consistency`

## Use Cases

- RGTI internal PDF.
- Public final report PDF after Promotion Gate.
- Utility operator package PDF if later needed.

## Forbidden

- Treating PDF generation as promotion.
- Creating public-final PDFs from manual-review artifacts.
- Hiding source Markdown/JSON defects behind a polished PDF.
- Exporting without lane and status.
