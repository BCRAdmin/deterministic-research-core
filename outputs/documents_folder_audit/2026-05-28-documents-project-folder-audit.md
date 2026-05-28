# Documents Project Folder Audit 2026-05-28

## Kurzurteil

Die Ablage ist funktionsfähig, aber nicht sauber benannt. `DreamFactory`, `Obsidian`, `Codex`, `BCR Ventures` und `Room 16 Reports` sind plausible bzw. dokumentierte Anker. Die größten Struktur-Schulden sind die aktiven Legacy-Namen `New project` und `New project 2`, ein klar falscher Restordner `New%20project`, sowie lose Root-Leaks `docs`, `dashboard` und `prompts`.

Wichtig: `New project` und `New project 2` sind trotz schlechtem Namen aktuell echte Arbeitswahrheit. Sie dürfen nicht spontan verschoben oder umbenannt werden, weil Vault, Scripts, Handoffs und Verifier sie referenzieren.

## P0/P1 Befunde

- **P0 cleanup candidate** `/Users/BjornRosinger/Documents/New%20project`: Falscher URL-encoded Pfad aus dokumentiertem `New%20project`-Bug; heute nur .DS_Store/leere Runtime-Struktur. Empfehlung: Nach kurzem Operator-Go löschen oder in Cleanup-Quarantine verschieben.
- **P0 naming truth mismatch** `/Users/BjornRosinger/Documents/Obsidian/Test Vaul Privat/Human Overview/Vault Visibility and Location.md`: Vault-Notiz behauptet noch, `/Users/BjornRosinger/Documents/New project` existiere nicht mehr sichtbar; aktueller Backbone nutzt ihn wieder aktiv. Empfehlung: Memory/Location-Note aktualisieren.
- **P1 structure debt** `/Users/BjornRosinger/Documents/New project`: Aktiver Legacy-Umbrella mit generischem Namen, vielen Produktachsen und Runtime-Dirt; Name ist falsch, Pfad ist aktuell trotzdem kanonisch referenziert. Empfehlung: Formale Migration planen, nicht spontan umbenennen.
- **P1 structure debt** `/Users/BjornRosinger/Documents/New project 2`: Aktives Repo mit generischem Namen; für Agent-OS/Research-Agent/Quellwert-Operating semantisch zu unklar. Empfehlung: Bei nächstem ruhigen Fenster Zielnamen festlegen und Verweis-Migration bauen.
- **P1 root leak** `/Users/BjornRosinger/Documents/{docs,dashboard,prompts}`: Lose Root-Ordner mit Autonomy-/Dashboard-/Prompt-Dateien; teils identisch zu `/Users/BjornRosinger/Documents/New project`, teils stale gegenüber LIONCOM. Empfehlung: Nach Sicherungscheck in Projekt-Quarantine oder New-project-Archive verschieben/löschen.
- **P1 name cleanup** `/Users/BjornRosinger/Documents/Midjurney`: Dokumentiertes Starter-Kit, aber Name ist Tippfehler. Vault verweist mehrfach darauf, daher nicht blind umbenennen. Empfehlung: Rename-Migration `Midjurney` -> `Midjourney` mit Vault-Link-Update.
- **P2 project hygiene** `/Users/BjornRosinger/Documents/New project/Library`: Mac-ähnlicher `Library/Application Support/LIONCOM/...`-Pfad innerhalb des Legacy-Umbrellas; wirkt wie falsch kopierter Runtime-Pfad. Empfehlung: In einem Cleanup-Lauf gegen echten Runtime-Workspace abgleichen und dann quarantänisieren.
- **P2 worktree/archive review** `/Users/BjornRosinger/Documents/New project/company-dossier-lab-*`: Mehrere Room16/Company-Dossier-Snapshot-/Worktree-Ordner sind im Vault erklärbar, aber langfristig eher Archive als aktive Projektordner. Empfehlung: Erst nach Git-/PR-/Evidence-Abgleich archivieren.
- **P2 loose prototype** `/Users/BjornRosinger/Documents/wp-stb-roesinger-redesign`: Dokumentierter UI-Prototyp, aber lose im Documents-Root. Empfehlung: Bei Reaktivierung unter BCR Ventures oder DreamFactory/Client-Prototypes einsortieren.

## Top-Level Ordner Ampel

- `/Users/BjornRosinger/Documents/Arbeitsstunden und Finanzen ` - `personal_or_business_archive_not_evaluated` (37.6 MiB, 43 Dateien, Marker: -)
  - Befund: Kein aktiver Vega-Projektpfad erkannt; vermutlich persönlicher, geschäftlicher oder App-/Medien-Archivordner.
  - Empfehlung: Nicht automatisch verschieben.
- `/Users/BjornRosinger/Documents/BCR Group` - `personal_or_business_archive_not_evaluated` (89.2 MiB, 280 Dateien, Marker: -)
  - Befund: Kein aktiver Vega-Projektpfad erkannt; vermutlich persönlicher, geschäftlicher oder App-/Medien-Archivordner.
  - Empfehlung: Nicht automatisch verschieben.
- `/Users/BjornRosinger/Documents/BCR Ventures` - `ok_business_project_namespace` (6.2 MiB, 61 Dateien, Marker: -)
  - Befund: BCR Ventures enthält Brand, Membership-Finanzplattform und Toolsuite; als Business-/Produktablage plausibel.
  - Empfehlung: Beibehalten; spätere Struktur optional unter Produktachsen schärfen.
- `/Users/BjornRosinger/Documents/Blog` - `personal_or_business_archive_not_evaluated` (85.2 MiB, 239 Dateien, Marker: -)
  - Befund: Kein aktiver Vega-Projektpfad erkannt; vermutlich persönlicher, geschäftlicher oder App-/Medien-Archivordner.
  - Empfehlung: Nicht automatisch verschieben.
- `/Users/BjornRosinger/Documents/Brother Scans` - `personal_or_business_archive_not_evaluated` (131.4 MiB, 33 Dateien, Marker: -)
  - Befund: Kein aktiver Vega-Projektpfad erkannt; vermutlich persönlicher, geschäftlicher oder App-/Medien-Archivordner.
  - Empfehlung: Nicht automatisch verschieben.
- `/Users/BjornRosinger/Documents/Call Recorder Aufzeichnungen` - `personal_or_business_archive_not_evaluated` (186.0 MiB, 8 Dateien, Marker: -)
  - Befund: Kein aktiver Vega-Projektpfad erkannt; vermutlich persönlicher, geschäftlicher oder App-/Medien-Archivordner.
  - Empfehlung: Nicht automatisch verschieben.
- `/Users/BjornRosinger/Documents/Codex` - `ok_agent_archive_namespace` (40.9 MiB, 96 Dateien, Marker: AGENTS.md)
  - Befund: Codex-Session-/Backup-/Pending-Sync-Archiv; als technischer Archivcontainer plausibel.
  - Empfehlung: Beibehalten, später separat nach alten Backups prüfen.
- `/Users/BjornRosinger/Documents/dashboard` - `misplaced_root_runtime_or_template_leak` (0.1 MiB, 7 Dateien, Marker: -)
  - Befund: Top-Level-Leak aus Autonomy/LIONCOM/New-project-Struktur; nicht als eigenständiger Projektordner sinnvoll.
  - Empfehlung: Nach Sicherungscheck in passenden Workspace archivieren oder löschen; root frei halten.
- `/Users/BjornRosinger/Documents/docs` - `misplaced_root_runtime_or_template_leak` (0.0 MiB, 2 Dateien, Marker: -)
  - Befund: Top-Level-Leak aus Autonomy/LIONCOM/New-project-Struktur; nicht als eigenständiger Projektordner sinnvoll.
  - Empfehlung: Nach Sicherungscheck in passenden Workspace archivieren oder löschen; root frei halten.
- `/Users/BjornRosinger/Documents/DreamFactory` - `ok_primary_project_namespace` (4047.8 MiB, 67124 Dateien, Marker: -)
  - Befund: Richtiger Sammelpfad für LIONCOM/Vivi/DreamFactory laut Backbone und aktueller Nutzung.
  - Empfehlung: Beibehalten; Unterordner separat über Projektstatus prüfen.
- `/Users/BjornRosinger/Documents/Exported Calls` - `personal_or_business_archive_not_evaluated` (49.0 MiB, 2 Dateien, Marker: -)
  - Befund: Kein aktiver Vega-Projektpfad erkannt; vermutlich persönlicher, geschäftlicher oder App-/Medien-Archivordner.
  - Empfehlung: Nicht automatisch verschieben.
- `/Users/BjornRosinger/Documents/Frank Beteiligung- und Verwaltungs GmbH` - `personal_or_business_archive_not_evaluated` (13.2 MiB, 78 Dateien, Marker: -)
  - Befund: Kein aktiver Vega-Projektpfad erkannt; vermutlich persönlicher, geschäftlicher oder App-/Medien-Archivordner.
  - Empfehlung: Nicht automatisch verschieben.
- `/Users/BjornRosinger/Documents/Hintergrund:Bildschirmschoner Bilder` - `personal_or_business_archive_not_evaluated` (219.9 MiB, 103 Dateien, Marker: -)
  - Befund: Kein aktiver Vega-Projektpfad erkannt; vermutlich persönlicher, geschäftlicher oder App-/Medien-Archivordner.
  - Empfehlung: Nicht automatisch verschieben.
- `/Users/BjornRosinger/Documents/Midjurney` - `documented_project_but_misspelled_name` (0.1 MiB, 28 Dateien, Marker: .git, README.md, docs)
  - Befund: Vault-dokumentiertes Starter-Kit, aber Ordnername ist offensichtlich falsch geschrieben; Git-Repo ohne Commit.
  - Empfehlung: Empfohlen: nach `Midjourney` umbenennen und Vault-Referenzen aktualisieren.
  - Git: ## No commits yet on main; sichtbare Dirt-Zeilen: 4
- `/Users/BjornRosinger/Documents/New project` - `active_legacy_workspace_bad_name` (6978.0 MiB, 120898 Dateien, Marker: README.md, AGENTS.md, pyproject.toml, docs, outputs)
  - Befund: Aktiv und stark im Vault referenziert, aber semantisch falsch/generisch benannt; enthält PIG, Mission-Control-Mirror, Room16, Kanzlei und Runtime-/Quarantine-Anteile.
  - Empfehlung: Nicht ad hoc umbenennen. Nur per formaler Migration mit Link-/Vault-/Script-Update.
- `/Users/BjornRosinger/Documents/New project 2` - `active_legacy_workspace_bad_name` (1211.8 MiB, 13148 Dateien, Marker: .git, README.md, pyproject.toml, docs, outputs, research_agent)
  - Befund: Aktives Git-Repo für Research-Agent/Agent-OS/Quellwert-Operating; Name ist generisch, aber aktuell Arbeitsrealität.
  - Empfehlung: Nicht ad hoc umbenennen. Später als `room16-quellwert-research-core` oder ähnlich migrieren.
  - Git: ## main...origin/main [ahead 5]; sichtbare Dirt-Zeilen: 0
- `/Users/BjornRosinger/Documents/New%20project` - `wrong_url_encoded_leftover` (0.0 MiB, 7 Dateien, Marker: -)
  - Befund: URL-encoded Restpfad aus altem Leerzeichen-Bug; enthält nur .DS_Store und leere Runtime-Unterordner.
  - Empfehlung: Sicherer Lösch-/Quarantäne-Kandidat nach Operator-Go.
- `/Users/BjornRosinger/Documents/Obsidian` - `ok_knowledge_namespace` (4.0 MiB, 371 Dateien, Marker: -)
  - Befund: Aktiver Vault liegt korrekt unter Obsidian/Test Vaul Privat.
  - Empfehlung: Beibehalten.
- `/Users/BjornRosinger/Documents/prompts` - `misplaced_root_runtime_or_template_leak` (0.0 MiB, 1 Dateien, Marker: -)
  - Befund: Top-Level-Leak aus Autonomy/LIONCOM/New-project-Struktur; nicht als eigenständiger Projektordner sinnvoll.
  - Empfehlung: Nach Sicherungscheck in passenden Workspace archivieren oder löschen; root frei halten.
- `/Users/BjornRosinger/Documents/Room 16 Reports` - `ok_documented_operator_shelf` (1.0 MiB, 38 Dateien, Marker: -)
  - Befund: Im Vault als fester Room16-Leseordner dokumentiert.
  - Empfehlung: Beibehalten; nicht in Code-Workspace verschieben.
- `/Users/BjornRosinger/Documents/Vorlagemasken Stuerbüro` - `likely_domain_asset_review_name` (1.7 MiB, 6 Dateien, Marker: -)
  - Befund: Steuerbüro-Template-/Vorlagenordner; Name nutzt Mischform `Stuerbüro` und könnte fachlich zur Kanzlei-/Steuer-Rail gehören.
  - Empfehlung: Nicht automatisch verschieben; erst Inhalt/Datenschutz prüfen.
- `/Users/BjornRosinger/Documents/WebEx` - `personal_or_business_archive_not_evaluated` (0.0 MiB, 0 Dateien, Marker: -)
  - Befund: Kein aktiver Vega-Projektpfad erkannt; vermutlich persönlicher, geschäftlicher oder App-/Medien-Archivordner.
  - Empfehlung: Nicht automatisch verschieben.
- `/Users/BjornRosinger/Documents/Wohnungskauf` - `personal_or_business_archive_not_evaluated` (116.8 MiB, 55 Dateien, Marker: -)
  - Befund: Kein aktiver Vega-Projektpfad erkannt; vermutlich persönlicher, geschäftlicher oder App-/Medien-Archivordner.
  - Empfehlung: Nicht automatisch verschieben.
- `/Users/BjornRosinger/Documents/wp-stb-roesinger-redesign` - `documented_project_but_loose_root_location` (5.7 MiB, 18 Dateien, Marker: -)
  - Befund: Im Vault als lokaler UI-Prototyp dokumentiert; Root-Lage ist okay für Prototyp, aber nicht ideal für längerfristige Projektablage.
  - Empfehlung: Bei Fortführung unter BCR Ventures oder DreamFactory/Client-Prototypes migrieren.
- `/Users/BjornRosinger/Documents/Zwift` - `personal_or_business_archive_not_evaluated` (6.5 MiB, 48 Dateien, Marker: -)
  - Befund: Kein aktiver Vega-Projektpfad erkannt; vermutlich persönlicher, geschäftlicher oder App-/Medien-Archivordner.
  - Empfehlung: Nicht automatisch verschieben.

## Migrationsregeln

- Aktive, stark referenzierte Workspaces nicht per Finder/`mv` umbenennen.
- Erst Zielnamen festlegen, dann Vault-Referenzen, Scripts, AGENTS.md, Git remotes/worktrees und Handoffs gemeinsam migrieren.
- Root von `/Users/BjornRosinger/Documents` künftig nur für große Namespaces und persönliche Dokumente nutzen, nicht für Runtime-Ordner wie `docs`, `dashboard`, `prompts`.
- Echte Operator-Shelves wie `Room 16 Reports` getrennt von Code-Workspaces lassen.

## Empfohlene nächste Umsetzung

1. `Vault Visibility and Location.md` korrigieren, damit `New project` nicht mehr als nicht-existent gilt.
2. Clear-Dirt nur nach Mini-Go räumen: `New%20project`, root `docs`, `dashboard`, `prompts`.
3. Separaten Rename-Plan für `Midjurney` -> `Midjourney` bauen und Vault-Referenzen aktualisieren.
4. Für `New project` und `New project 2` eine echte Workspace-Migration planen, nicht sofort verschieben.
