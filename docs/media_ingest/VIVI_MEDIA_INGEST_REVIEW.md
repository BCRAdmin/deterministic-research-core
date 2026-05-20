# Vivi Media Ingest Review

Status: review contract  
Reviewer role: Vivi  
Scope: media-ingest packets, evidence candidates and Obsidian draft notes

## Vivi Checks

Vivi must check:

- source allowed
- rights and use policy clear
- no paywall, login or DRM circumvention
- download approval present if a download happened
- transcript complete enough for intended use
- language, timestamps, speaker attribution and known gaps documented
- hard claims marked `requires_verification=true`
- no long quotes or full third-party transcript reproduction
- no direct report promotion
- no `MetricsPacket` or `DecisionPacket` mutation
- no guard, rating or calibration change
- Obsidian promotion gate followed
- Room16 Evidence Candidate lane preserved

## Review Status

- `pass`: packet is internally usable as draft/candidate material.
- `needs_fix`: packet is close, but metadata, claim flags, source rank or quote handling must be fixed.
- `manual_human_review`: rights, source authenticity, sensitive content, poor transcript quality or intended public/report use needs human decision.

## Output Fields

- `review_status`
- `blocking_issues`
- `non_blocking_issues`
- `source_allowed`
- `rights_policy_clear`
- `download_gate_ok`
- `transcript_quality`
- `hard_claims_require_verification`
- `long_quotes_present`
- `direct_report_promotion_present`
- `obsidian_gate_ok`
- `room16_candidate_lane_ok`
- `recommended_action`

## Hard Stops

Vivi must not pass the packet if:

- source access required bypassing paywall/login/DRM
- rights/use status is unknown for intended use
- full third-party transcript reproduction is present
- media claims directly changed packets, reports, ratings, guards or public status
- hard financial claims are report-ready without primary/official verification

## Acceptance

The review contract is satisfied when Vivi can classify the packet without extra source guessing and every recommendation remains monitoring, fixing, candidate review or human gate.
