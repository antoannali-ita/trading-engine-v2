# LAB-RESEARCH-001 · Trade Committee

## Scopo
Modulo manuale, autonomo e read-only verso Production per una due diligence aggiuntiva immediatamente prima di un eventuale acquisto reale.

Non è una strategia, non sostituisce CORE/Multi-Horizon, non genera ordini e non modifica score, eligibility, entry o segnali Production.

## Principio architetturale

**Il Trade Committee non produce un secondo Stock Score. Valida l'affidabilità e la validità operativa della trade proposta dal CORE.**

Le tre grandezze restano separate:

`ENGINE SCORE != TRADE VALIDATION SCORE != CORE DATA CONFIDENCE`

Quando è disponibile uno snapshot CORE, entry, Max Buy, stop, TP1, TP2, R/R, trigger e stato operativo sono authoritative e non vengono ricalcolati dal Committee. Il Committee usa dati esterni/locali solo come cross-check, enrichment e ricerca di invalidazioni.

Senza snapshot CORE il modulo resta utilizzabile come manual research, ma non deve simulare un secondo CORE né produrre un APPROVE operativo.

## BUGFIX-TC-001 · 27/08/2026

### Root cause
La V1 richiedeva contemporaneamente:

`committee_score >= 75 AND technical >= 65 AND warning_count <= 1`

ma generava strutturalmente più WARNING per adapter non ancora implementati. APPROVE risultava quindi irraggiungibile per costruzione.

### Correzione
- eliminato il gate sul conteggio grezzo dei WARNING;
- introdotta una tassonomia esplicita di check;
- introdotta una lista chiusa di HARD VETO;
- gli enrichment mancanti non bloccano APPROVE e non riducono la Core Data Confidence;
- introdotto lo snapshot CORE con hash/versione;
- Trade Validation Score sostituisce il concetto di secondo stock score del Committee;
- aggiunti test di raggiungibilità APPROVE e test simmetrici sugli hard veto;
- aggiunta fixture storica CRUS per regressione del bug;
- RSI cross-check normalizzato a Wilder;
- RVOL intraday marcato come parziale e non penalizzato come full-session.

## Tassonomia check

| Classe | Significato | Effetto |
|---|---|---|
| `COMPLETE` | check core eseguito correttamente | nessuna penalità |
| `HARD_VETO` | condizione esplicitamente bloccante | impedisce APPROVE |
| `CORE_WARNING` | dato core importante incompleto | riduce Core Data Confidence, porta tipicamente a WAIT_DATA |
| `SOFT_WARNING` | informazione utile ma non decisiva | piccola penalità di confidence |
| `ENRICHMENT_ND` | 13F/insider/analyst/news o enrichment non disponibile | non blocca e non riduce Core Data Confidence |
| `FAILED` | errore reale del check | forte penalità / review |

### Regola strutturale
**Tutto ciò che non appartiene all'enum HARD VETO non può bloccare automaticamente APPROVE.**

L'estensione dell'enum HARD VETO richiede nella stessa PR:
1. modifica dell'enum;
2. test dedicato;
3. documentazione del motivo.

## Hard veto ufficiali
- `PRICE_DATA_CONFLICT`
- `CORPORATE_ACTION`
- `EARNINGS_LT_7D`
- `TRIGGER_INVALID`
- `PRICE_ABOVE_MAX_BUY`
- `RR_NET_LT_MIN`
- `LIQUIDITY`
- `POSITION_SIZE`
- `CRITICAL_DATA_STALE`
- `CORE_HARD_VETO`

Il Committee può aggiungere un veto ulteriore, ma non può cancellare un veto già presente nel CORE.

## Snapshot CORE
Lo snapshot è immutabile e hashato. Campi principali:
- ticker / mercato / versione engine;
- Engine/Opportunity Score;
- stato tecnico e RS;
- entry ideale / Buy Zone / Max Buy;
- stop / TP1 / TP2;
- R/R netto;
- trigger e motivo;
- size/capitale/rischio;
- data quality e anomalie;
- corporate action;
- earnings date/days;
- decisione/stato operativo;
- gate falliti e veto CORE.

Il campo `core_snapshot_hash` permette di dimostrare quale identico input CORE ha prodotto un determinato verdetto del Committee.

## Trade Thesis Validation
I 20 punti di validazione della tesi CORE sono deterministici:
- trigger CORE ancora valido: 6;
- prezzo non oltre Max Buy: 4;
- stop coerente sotto entry: 4;
- R/R netto TP2 >= minimo: 4;
- nessuna rottura di struttura/trigger dichiarata dal CORE: 2.

Non esiste una voce soggettiva tipo "price action deteriorata" assegnata a giudizio libero.

## Data Confidence
Modello iniziale versionato: `PATCH_1_PROVISIONAL_WEIGHTS_V1`.

Pesi provvisori:
- CORE_WARNING: -12;
- SOFT_WARNING: -4;
- ENRICHMENT_ND: 0.

Sono valori provvisori da calibrare solo dopo una raccolta sufficiente di run reali. Qualunque modifica futura richiede versione nuova del modello, non aggiustamenti silenziosi.

La UI/output espone separatamente:
- `Core Data Confidence`;
- `Enrichment Coverage`.

Mancanza di 13F o insider non deve far sembrare inaffidabile un prezzo o un earnings core verificato.

## Pipeline corrente
1. Market data corrente come cross-check.
2. Data Quality / TradingView cross-check.
3. Fundamental Deep Dive.
4. Business Quality / Financial Strength.
5. Valuation.
6. Earnings / Catalyst Window.
7. News / Analyst / Insider / Ownership (enrichment).
8. Official Filings SEC.
9. Market / Sector / Relative Strength.
10. Portfolio Context.
11. CORE Trade Plan, authoritative quando snapshot presente.
12. Trade Thesis Validation.

## Tecnica: RSI e RVOL
- RSI14 di cross-check usa Wilder/RMA, coerente con la semantica standard di TradingView.
- Durante la sessione cash USA, il volume giornaliero corrente è parziale. Il raw RVOL viene conservato come `relative_volume_partial`, ma non viene penalizzato come se fosse un dato full-day.
- A sessione chiusa viene usato `relative_volume` full-session.

Questi dati restano cross-check. Se lo snapshot CORE è presente, non sostituiscono i valori authoritative del motore.

## Trade Plan e Fineco
Quando lo snapshot CORE è presente, il Committee usa direttamente il piano CORE.

Il piano locale di fallback è solo diagnostico e usa:
- capitale massimo posizione: 2.500 USD;
- commissione Fineco USA: 12 USD per lato;
- nessun ordine automatico.

## Stati finali
Gli stati usati dal policy layer sono:
- `APPROVE`
- `APPROVE_WITH_WARNING`
- `WAIT_CORE`
- `WAIT_DATA`
- `REJECT_HARD_VETO`
- `REJECT_COMMITTEE`

Le nomenclature devono restare condivise tra policy, UI, persistence, test e documentazione. Nuovi sinonimi non vanno introdotti localmente.

## Test di regressione obbligatori
- candidato perfetto può raggiungere APPROVE;
- enrichment mancante non blocca APPROVE;
- hard veto blocca sempre APPROVE;
- più CORE_WARNING senza hard veto portano almeno a WAIT, non a reject automatico per accumulo;
- RVOL intraday non viene penalizzato come full-session;
- RSI Wilder resta bounded/coerente;
- snapshot CORE è hashabile e immutabile;
- fixture storica CRUS documenta la classe di regressione che ha originato BUGFIX-TC-001.

## Evoluzione successiva
Dopo il bugfix strutturale:
1. collegare stabilmente Candidate Queue/CORE snapshot al flusso UI;
2. completare adapter Company IR, transcript, 13F e Form4 avanzato;
3. raccogliere almeno 30-50 run reali;
4. misurare falsi reject/falsi approve;
5. solo allora calibrare soglie e pesi del Validation Score/Data Confidence.

Non si calibrano soglie su una pipeline logicamente distorta.

## Guardrail permanente
`RESEARCH ONLY · nessun ordine reale · il Committee valida il CORE e non lo sostituisce`.
