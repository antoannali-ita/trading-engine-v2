# Storico versioni

## V1.2 LAB-FEAT-001 — 26/08/2026

**Tipo modifica:** Laboratory research-only. Nessuna modifica alla logica Production/CORE.

### Decisione

TradingView Extended Data viene trattato come **Feature Enrichment Layer trasversale**, non come nuova strategia. Il Laboratory può raccogliere valori grezzi sulle strategie esistenti; `PROD-001` resta FROZEN.

### Guardrail

- nessun nuovo trade generato;
- nessuna modifica a score, Entry, Stop, Max Buy, sizing, trigger o decisione;
- nessuna soglia RelVol/RS inventata nella fase di raccolta;
- analisi iniziale post-hoc e una feature alla volta;
- benchmark RS versionati: USA `SPY`, Italia `FTSEMIB`;
- provider, timestamp e versione definizione conservati nei record;
- eventuale promozione: LAB DATA → A/B → EVIDENCE → SHADOW → Production candidate.

## Documentazione V1.1 ITA — 26/08/2026

**Tipo modifica:** documentale, nessuna modifica alla logica di trading.

### Obiettivo

Rendere la baseline utilizzabile come documentazione operativa permanente in italiano, mantenendo in lingua originale soltanto identificatori tecnici, nomi dei file, tecnologie e stati del motore.

### Modifiche V1.1

- indice della documentazione tradotto e ampliato;
- spiegazione in italiano dei domini CORE, Laboratory e Production;
- descrizione esplicita della differenza AS-IS / TO-BE;
- ciclo documentale delle modifiche rappresentato con diagramma Mermaid;
- catalogo componenti tradotto e arricchito con spiegazioni delle responsabilità;
- mantenimento dei nomi reali di file/funzioni/stati per garantire corrispondenza con il codice;
- nessuna variazione delle regole decisionali, dei parametri strategici o dei workflow Production.

## Documentation Baseline V1.0 — 26/08/2026

Prima memoria funzionale e tecnica permanente di Trading Engine v2: separazione CORE/Laboratory/Production, parity-first, Master Scan/Fast Monitor, decisioni/Entry/RR/sizing, notifiche, freeze governance, ENGINE HEALTH vs STRATEGY EVIDENCE, bug/fix, debito tecnico, AS-IS, TO-BE e ADR.

## Politica

Ogni cambiamento materiale di codice o configurazione aggiorna la documentazione interessata nello stesso ciclo. `VERSION_HISTORY.md` registra cosa cambia; ADR il perché; `BUG_FIX_REGISTER.md` i difetti; TO-BE/Innovation conserva proposte non ancora Production.

Una nuova versione documentale non deve far apparire implementato un elemento che esiste soltanto nella roadmap.