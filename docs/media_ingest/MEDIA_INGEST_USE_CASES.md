# Media Ingest Use Cases

Status: internal playbook only  
Scope: Whisper / YouTube Watcher patterns, no external skill installation, no runtime activation

## Purpose

This playbook defines safe media-ingest use cases for Quellwert, Room16, Vivi and Obsidian. Media may help create transcript drafts, source notes and evidence candidates, but it must not directly change reports, ratings, guards, calibration, `MetricsPacket`, `DecisionPacket` or public output.

## Global Rules

- No new API keys.
- No downloads without explicit Operator-Go.
- No paywall, login or DRM circumvention.
- No mass downloads.
- No long copyrighted excerpts or full transcript reproduction from third-party sources.
- No automatic public output.
- No direct report use without Evidence Gate.
- Transcript output is an Evidence Candidate, not Evidence.

## Use Cases

| Use case | Allowed | Required operator input | Copyright risk | Source reliability | Evidence use allowed | Report use allowed | Required review gate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Earnings Call Audio/Video transcribe | yes | source URL or local file, company, date, rights status, download approval if needed | medium | high if official IR source, medium otherwise | candidate only | only after source authenticity and hard-claim verification | Vivi Media Review plus Room16 Evidence Gate |
| Investor Day / Company Presentation transcribe | yes | source URL or local file, company, event date, rights status | medium | high if official IR source | candidate only | only after source authenticity and hard-claim verification | Vivi Media Review plus Room16 Evidence Gate |
| YouTube interview pre-triage as research source | yes | URL, channel identity, intended use, quote limits | medium to high | low to medium unless official company/IR channel | candidate only | only for paraphrase or timestamped context after review | Vivi Media Review plus source rank check |
| Podcast / audio source pre-triage | yes | source, owner, episode date, rights status, intended use | medium to high | low to medium unless official source | candidate only | only after verification against primary/official evidence | Vivi Media Review plus primary-source check |
| Utility-site content ideas from owned or permitted videos | yes | owned/permitted source, use scope, target project | low if owned/permitted | medium | no Room16 evidence use by default | draft only, no auto-publish | Operator content review |
| Room16 Evidence Candidate from transcript | yes | source metadata, timestamp, speaker, claim type | medium | depends on source rank | candidate only | no direct report use | Room16 Evidence Candidate Gate |
| Obsidian note from owned material | yes | owner approval, sensitivity status, target note type | low if owned | internal memory only | not evidence by default | no public/report use | Obsidian Memory Promotion Map |

## Acceptance

Media ingest is considered safe only when it stays in draft/candidate lanes, preserves source metadata, and keeps all promotion steps gated by Vivi, Room16 Evidence Review or explicit Operator-Go.
