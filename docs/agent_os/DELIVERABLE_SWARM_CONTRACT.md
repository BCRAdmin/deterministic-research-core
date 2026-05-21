# Deliverable-Swarm-Vertrag

Status: aktive lokale v1
Runtime-Aenderungen: keine
Quellmuster: VRSEN/OpenSwarm, nur als Muster uebernommen

## Zweck

Dieser Vertrag uebersetzt das nuetzliche OpenSwarm-Produktmuster in eine
sichere lokale Oberflaeche fuer Vega-, Vivi-, LIONCOM- und OpenClaw-Arbeit.

Das uebernommene Muster ist einfach:

- ein Orchestrator routet Arbeit
- Spezialisten besitzen konkrete Lieferobjekte
- jedes Lieferobjekt hat einen Output-Pfad
- jedes finale Artefakt hat einen Verifier
- Provider-, Konto-, Scheduled-Runner- oder Publishing-Verhalten laeuft nie ohne Gate

## Pflicht-Lanes

- `orchestrator`: Routenplan und Handoff-Paket
- `assistant`: Operator-Notizen, Nachrichtenentwuerfe, Task-Zusammenfassungen
- `research`: Research-Briefs, Quellenmatrizen, Entscheidungsoptionen
- `data`: Analyseberichte, Chart-Artefakte, Datenqualitaetsnotizen
- `docs`: Markdown, DOCX, PDF, Aenderungszusammenfassungen
- `slides`: Slide-Quellen, PPTX-Deck, visuelle QA
- `images`: Bildartefakte und Bild-QC, provider-gated
- `video`: Videoartefakte und Video-QC, provider-gated

## Output-Metadaten

Jedes finale Artefakt braucht:

- `artifact_id`
- `lane_id`
- `artifact_type`
- `output_path`
- `status`
- `verifier`
- `blocked_gates`
- `next_action`

## Handoff-Regel

Der Orchestrator darf an jede Spezialisten-Lane routen. Spezialisten-Lanes
geben an den Orchestrator oder an eine eng definierte nachgelagerte
Artefakt-Lane zurueck. Ein verstecktes all-to-all-Runtime-Mesh ist nicht
erlaubt.

## Harte Grenzen

- keine Auto-Installation externer Runtimes
- keine Systempaket-Installation
- keine automatische Verbindung externer Konten
- kein Secret-Import
- keine oeffentliche Veroeffentlichung
- kein kanonischer Obsidian-Write durch generierte Runtime
- keine Hintergrundautomation-Erstellung
- keine unbegrenzte all-to-all-Handoff-Runtime

## Befehl

```bash
python3 scripts/ops/agent_os_readiness.py
```

Generierte Outputs:

- `outputs/agent_os_readiness/DELIVERABLE_SWARM_CONTRACT.md`
- `outputs/agent_os_readiness/DELIVERABLE_SWARM_CONTRACT.json`

Nutzungsuebersicht:

- `docs/agent_os/DELIVERABLE_SWARM_OPERATING_OVERVIEW.md`
- `docs/agent_os/DELIVERABLE_SWARM_OPERATING_MAP.canvas`
