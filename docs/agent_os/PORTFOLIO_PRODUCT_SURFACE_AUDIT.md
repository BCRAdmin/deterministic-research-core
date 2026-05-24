# Portfolio-Produktoberflächen-Audit

Status: aktive lokale v1
Scope: LIONCOM / Membership / Utility / Quellwert / Vega-Vivi-Lieferoberflächen
Runtime-Änderungen: keine

## Zweck

Dieser Audit ist der wiederholbare Test, ob unsere Projektarbeit wie ein
sichtbares Produktsystem funktioniert und nicht nur als interne Agentenleistung.

Jede kanonische Projektkarte muss beantworten:

- Welche sichtbare Oberfläche existiert oder ist bewusst blockiert?
- Welche Deliverable-Swarm-Lanes besitzen die nächsten Lieferobjekte?
- Welche Gates stoppen irreversible Aktionen?
- Was ist die nächste sichere Aktion?
- Wird ein wartendes Projekt sauber von aktiven Website- oder Runtime-Lanes getrennt?

## Befehl

```bash
python3 scripts/ops/agent_os_readiness.py
```

Generierte Outputs:

- `outputs/agent_os_readiness/PORTFOLIO_PRODUCT_SURFACE_AUDIT.md`
- `outputs/agent_os_readiness/PORTFOLIO_PRODUCT_SURFACE_AUDIT.json`
- `outputs/agent_os_readiness/PORTFOLIO_PRODUCT_SURFACE_MAP.canvas`

## Geprüfte Projektkarten

- `Project - LIONCOM Dashboard.md`
- `Project - Membership Finanzplattform.md`
- `Project - Utility Wortcluster.md`
- `Project - Utility Websites Portfolio.md`
- `Project - Quellwert.md`

## Übernahmeregel

Der Audit darf Projektwahrheit lesen und lokale Review-Artefakte schreiben. Er
installiert keine Runtime, erstellt keine Automation, oeffnet keine Provider und
promotet keine Public-Ausgabe. Dauerhafte Findings gehoeren nach Vega-Memory
oder in die passende Projektkarte.
