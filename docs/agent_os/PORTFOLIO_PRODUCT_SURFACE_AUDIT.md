# Portfolio-Produktoberflaechen-Audit

Status: aktive lokale v1
Scope: LIONCOM / Membership / Utility / Quellwert / Vega-Vivi-Lieferoberflaechen
Runtime-Aenderungen: keine

## Zweck

Dieser Audit ist der wiederholbare Test, ob unsere Projektarbeit wie ein
sichtbares Produktsystem funktioniert und nicht nur als interne Agentenleistung.

Jede kanonische Projektkarte muss beantworten:

- Welche sichtbare Oberflaeche existiert oder ist bewusst blockiert?
- Welche Deliverable-Swarm-Lanes besitzen die naechsten Lieferobjekte?
- Welche Gates stoppen irreversible Aktionen?
- Was ist die naechste sichere Aktion?
- Wird ein wartendes Projekt sauber von aktiven Website- oder Runtime-Lanes getrennt?

## Befehl

```bash
python3 scripts/ops/agent_os_readiness.py
```

Generierte Outputs:

- `outputs/agent_os_readiness/PORTFOLIO_PRODUCT_SURFACE_AUDIT.md`
- `outputs/agent_os_readiness/PORTFOLIO_PRODUCT_SURFACE_AUDIT.json`
- `outputs/agent_os_readiness/PORTFOLIO_PRODUCT_SURFACE_MAP.canvas`

## Gepruefte Projektkarten

- `Project - LIONCOM Dashboard.md`
- `Project - Membership Finanzplattform.md`
- `Project - Utility Wortcluster.md`
- `Project - Utility Websites Portfolio.md`
- `Project - Quellwert.md`

## Uebernahmeregel

Der Audit darf Projektwahrheit lesen und lokale Review-Artefakte schreiben. Er
installiert keine Runtime, erstellt keine Automation, oeffnet keine Provider und
promotet keine Public-Ausgabe. Dauerhafte Findings gehoeren nach Vega-Memory
oder in die passende Projektkarte.
