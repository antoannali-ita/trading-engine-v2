# Catalogo dei componenti di sistema

**Versione:** 1.1 ITA  
**Baseline:** 26/08/2026  
**Nota:** il catalogo descrive responsabilità e confini dei componenti. Le singole funzioni restano verificabili nel sorgente e in `FUNCTION_MAP.csv`.

| Area | Componente / path | Responsabilità |
|---|---|---|
| Baseline | `reference/usa_v5_5.py` | Oracle comportamentale USA congelato utilizzato durante la fase PARITY |
| Baseline | `reference/italy_v1_2.py` | Oracle comportamentale Italia congelato utilizzato durante la fase PARITY |
| Migrazione | `FUNCTION_MAP.csv` | Mappa le funzioni principali dei reference verso i moduli destinazione della nuova architettura |
| CORE | `engine/analyzer.py` | Orchestrazione del full scan, assemblaggio risultati e normalizzazioni specifiche USA/Italia |
| CORE | `engine/scoring.py` | Calcolo delle componenti di score e delle misure di qualità/opportunità |
| CORE | `engine/entry.py` | Geometria dell'ingresso: Entry, Buy Zone, Max Buy e livelli strutturali |
| CORE | `engine/risk_reward.py` | Calcolo del rapporto rischio/rendimento lordo e netto |
| CORE | `engine/sizing.py` | Position sizing, capitale allocato e rischio monetario della posizione |
| CORE | `engine/triggers.py` | Logica degli stati di trigger e conferma del setup |
| CORE | `engine/prebuy.py` | Logica PRE-BUY/readiness e avvicinamento alle condizioni operative |
| CORE | `engine/decision.py` | Responsabilità relative alla decisione e allo stato mostrato all'utente |
| CORE | `engine/value_trap.py` | Gestione dei segnali di value trap e controlli sensibili al settore |
| CORE | `engine/anomaly.py` | Sanitizzazione di anomalie dati/earnings e protezione da input incoerenti |
| CORE | `engine/utils.py` | Utility condivise necessarie anche alla compatibilità PARITY |
| Market | `market/` | Universo titoli, provider, benchmark e market regime |
| State | `state/` | Database/storico, snapshot e gestione dei cambi di stato |
| Portfolio | `portfolio/` | Contesto portafoglio, esposizione e portfolio heat |
| Reports | `reports/email_report.py` | Generazione/binding del report operativo inviato via email |
| Notifications | `notifications/` | Client di consegna Email e WhatsApp. Devono notificare decisioni, non crearle |
| Monitor | `monitor/master_scan.py` | Entry point CLI/Production del Master Scan completo |
| Monitor | `monitor/fast_monitor.py` | Entry point CLI/Production del monitoraggio rapido dei candidati rilevanti |
| Config | `config/` | Configurazione runtime comune e specifica per USA/Italia |
| Workflows | `.github/workflows/` | Avvio manuale/schedulato, ambiente runtime, test pre-run e orchestrazione Production |
| Tests | `tests/` | Test di integrità, parity, regressione, comportamento UI e Production |
| Laboratory | moduli/pagine Laboratory | Ricerca: opportunity, paper position, evidence, verdict e dashboard |
| Orchestrator | `orchestrator/` | Coordinamento tra segnali/motori e persistenza condivisa; include integrazione Supabase |

## Regola delle dipendenze

Gli entry point di Production devono **orchestrare** e non duplicare le regole di trading. Durante la migrazione, la logica strategica appartiene al CORE o ai reference congelati. I client di notifica devono consegnare lo stato prodotto dal motore e non inventare una decisione propria. Il Laboratory deve osservare, misurare e sperimentare senza modificare silenziosamente il comportamento del CORE.

## Lettura funzionale dei principali domini

### `reference/`
Contiene gli oracle comportamentali utilizzati per verificare che la modularizzazione non alteri involontariamente le decisioni. Non rappresenta l'architettura finale desiderata: è una rete di sicurezza temporanea della fase PARITY.

### `engine/`
È la destinazione della modularizzazione del CORE. L'obiettivo è separare responsabilità oggi concentrate nei reference in componenti più piccoli, testabili e manutenibili, preservando la parità decisionale prima di introdurre modifiche strategiche.

### `monitor/`
Espone i processi operativi. `master_scan.py` serve al controllo ampio, mentre `fast_monitor.py` è destinato a verifiche più frequenti dei candidati già interessanti. I monitor non devono diventare un secondo motore strategico parallelo.

### `state/` e `orchestrator/`
Gestiscono memoria operativa e persistenza. Il progetto utilizza anche Supabase quando sono configurati `SUPABASE_URL` e `SUPABASE_SECRET_KEY`; in assenza delle credenziali il client può operare senza persistenza Supabase dove previsto dal codice.

### `notifications/`
Contiene i canali di consegna. Email e WhatsApp sono superfici Production: un errore di notifica non deve essere confuso con la qualità della strategia, ma va comunque rilevato da `ENGINE HEALTH`.

### Laboratory
È intenzionalmente separato dal CORE. Produce evidence e paper results. Le sue conclusioni possono motivare una futura modifica, ma non devono cambiare automaticamente una regola operativa.

## Regola di audit

Quando una funzione viene realmente estratta da `reference/` e resa indipendente in un modulo:

1. aggiornare questo catalogo;
2. aggiornare `FUNCTION_MAP.csv`;
3. aggiornare `TECHNICAL_ARCHITECTURE.md`;
4. aggiornare o aggiungere i test di parity/regressione;
5. registrare il cambiamento in `VERSION_HISTORY.md`;
6. creare/aggiornare un ADR se cambia un confine architetturale significativo.

La documentazione deve descrivere il codice esistente, non quello che speriamo esista.