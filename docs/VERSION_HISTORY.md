# Storico versioni

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

### Obiettivo

Creare la prima memoria funzionale e tecnica permanente, a livello repository, di Trading Engine v2.

### Contenuto acquisito nella V1.0

- separazione CORE / Laboratory / Production;
- migrazione parity-first e ruolo dei reference congelati;
- responsabilità di Master Scan e Fast Monitor;
- concetti funzionali di decisione, Entry, R/R e sizing;
- validazione delle notifiche;
- collegamento alla Functional Freeze Governance;
- principio `ENGINE HEALTH` vs `STRATEGY EVIDENCE`;
- registro iniziale bug/fix;
- registro iniziale debito tecnico/ottimizzazioni;
- diagrammi AS-IS;
- architettura TO-BE e Innovation Backlog separati;
- framework ADR.

## Politica delle modifiche dalla V1.0

Ogni cambiamento materiale di codice o configurazione deve aggiornare la documentazione interessata nello stesso ciclo di sviluppo.

- `VERSION_HISTORY.md` registra **cosa è cambiato**.
- Gli ADR registrano **perché è stata presa o modificata una decisione importante**.
- `BUG_FIX_REGISTER.md` registra **difetti, causa, correzione e protezione di regressione**.
- I documenti TO-BE/Innovation conservano **idee e proposte** finché non vengono approvate, implementate o respinte.

## Versionamento documentale

- **1.0.x / 1.1.x** — correzioni, traduzioni e chiarimenti documentali senza modifica funzionale del sistema.
- **1.x** — evoluzioni materiali del sistema documentate senza sostituzione dell'architettura fondamentale.
- **2.0** — milestone architetturale maggiore. Candidato naturale: CORE realmente modulare e indipendente dopo il completamento della migrazione PARITY.

## Regola

Una nuova versione documentale non deve far apparire come implementato un elemento che esiste soltanto nella roadmap. Lo storico deve permettere di ricostruire lo stato del sistema e le decisioni dell'epoca senza dover recuperare conversazioni esterne al repository.