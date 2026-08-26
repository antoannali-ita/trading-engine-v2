# LAB-FEAT-001 — TradingView Feature Enrichment Layer

**Stato:** DATA COLLECTION / RESEARCH ONLY  
**Production:** FROZEN  
**Principio:** arricchimento passivo, non nuova strategia.

## Obiettivo

Raccogliere metadati TradingView sui segnali già generati dalle strategie Laboratory esistenti per verificare, a posteriori, se singole feature aggiungono capacità informativa. Il layer non genera nuovi trade e non modifica eligibility, score, Entry, Stop, Max Buy, sizing, trigger o decisione.

## Feature candidate iniziali

Valori grezzi/continui: Relative Volume; Relative Strength 1M/3M/6M; distanza percentuale da SMA20/50/200; ATR14 e ATR%; gap%; distanza da massimo/minimo 52 settimane.

Nessuna soglia operativa viene fissata nella fase di raccolta. In particolare non esiste una regola tipo `RelVol > 1.5` nel CORE.

## Benchmark Relative Strength

- USA: `SPY`, definizione `RS-BENCHMARK.v1`.
- Italia: `FTSEMIB`, definizione `RS-BENCHMARK.v1`.

La definizione è versionata prima della raccolta. Un eventuale cambio futuro deve creare una nuova versione e non reinterpretare retroattivamente i record precedenti.

## Metadati obbligatori

Ogni snapshot deve conservare mercato, ticker, strategia/versione, timestamp UTC, provider, versione del feature set, benchmark/versione e metadati sorgente disponibili.

## Metodo sperimentale

1. Il generator esistente produce il segnale senza conoscere LAB-FEAT-001.
2. Il layer raccoglie le feature candidate come metadati.
3. Le paper position restano identiche alla baseline.
4. L'analisi è inizialmente post-hoc e per singola feature.
5. Una feature senza evidence viene mantenuta LAB ONLY o REJECT.
6. Una feature promettente può diventare variante A/B della strategia interessata.
7. Solo dopo evidence, regressione e shadow validation può essere candidata a Production.

## Guardrail

- Non è una nona strategia.
- Non apre paper trade aggiuntivi.
- Non cambia i trade che le strategie avrebbero aperto senza enrichment.
- Non introduce soglie nel CORE.
- Non combina molte feature in un filtro unico durante la prima validazione.
- Production non deve importare il modulo Laboratory di enrichment.

## Stati di promozione

`LAB DATA → POST-HOC → LAB ONLY/REJECT oppure A/B VARIANT → EVIDENCE → SHADOW → PRODUCTION CANDIDATE`

L'ultimo passaggio appartiene a `PROD-001` e rimane congelato durante il Functional Freeze.