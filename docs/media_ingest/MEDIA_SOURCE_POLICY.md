# Media Source Policy

Status: internal policy  
Applies to: Whisper / YouTube Watcher derived workflows, Room16, Quellwert, Vivi and Obsidian

## Allowed Sources

- Owned audio or video files.
- Public company webcasts where terms permit the intended internal use.
- IR or earnings-call sources from legitimate company, exchange, filing or event-host channels.
- YouTube videos when the workflow uses short summary, analysis or timestamped paraphrase, not mass quoting.
- Manually provided transcripts when rights and source identity are documented.

## Forbidden Sources

- Paywall, login or DRM circumvention.
- Mass scraping or bulk downloads.
- Long quotations from copyrighted third-party material.
- Full transcript reproduction of third-party sources.
- Music or song lyrics except minimal legally permitted short excerpts.
- Automatic public publication from transcript material.
- Use as primary evidence without source review.

## Download Rule

Downloads require explicit Operator-Go and must record:

- source URL or local source path
- source owner
- intended use
- rights status
- whether a download happened
- who approved the download
- when it happened

No helper in this package may fetch YouTube, call external APIs or download media.

## Evidence Rule

Transcript is not automatically truth. Transcript is an Evidence Candidate. A claim extracted from media becomes an EvidenceItem only after source authenticity, timestamp, speaker attribution, rights/use check and hard-claim verification where required.

## Source Rank

- Official IR/company channel: high candidate rank, still requires review.
- SEC/filing or official release cited inside media: verify against the primary source before use.
- Vendor, third-party YouTube, podcast or interview: low to medium rank; use for context and questions, not unverified hard financial claims.
- Owned material: safe for internal notes, but report/public use still needs the relevant project gate.

## Quote Rule

Reports and Obsidian notes should paraphrase. If a quote is needed, use the shortest necessary excerpt, retain timestamp/source, and keep copyright limits in force.

## Acceptance

Media source use is acceptable only when rights are clear enough for the intended use, no forbidden access path is used, and the output remains gated as draft, note or evidence candidate.
