# Trade Committee · Source Research & Video Audit

**Versione:** 1.0  
**Data:** 27/08/2026  
**Stato:** RESEARCH / DESIGN INPUT  
**Ambito:** LAB-RESEARCH-001 Trade Committee  

> Questo documento conserva la ricerca che ha portato al Trade Committee. Le fonti esterne sono reference architetturali e informative: nessun progetto esterno viene incorporato integralmente senza audit di licenza, sicurezza, dipendenze, qualità dati e compatibilità.

## 1. Obiettivo

Il Trade Committee deve essere un modulo manuale e indipendente, eseguito solo sui candidati realmente vicini a un acquisto. Deve rispondere a una domanda semplice: **con le informazioni disponibili oggi, comprerei davvero questo titolo, a quale prezzo e con quale rischio?**

Non è una nuova strategia alpha, non sostituisce Production/Multi-Horizon, non deve generare ordini e deve poter contraddire il segnale dell'Engine.

Principio di audit permanente:

`CHECK -> FONTE -> DATO -> CALCOLO/REASONING -> ESITO -> CONFIDENCE`

Un check può essere dichiarato COMPLETE solo se la funzione dichiarata è realmente eseguita. Un'etichetta attraversata dal codice non equivale a una due diligence completata.

---

## 2. Materiale video riesaminato

Sono stati riesaminati 8 video WhatsApp del 26/08/2026, sequenza 17:23-17:29. I video sono materiale promozionale/social e quindi **non sono considerati prova dell'efficacia finanziaria**. Sono usati per identificare progetti, pattern architetturali e idee da verificare sulle fonti originali.

### V01 · 17:23 · AI Berkshire

Elementi visibili: repository GitHub `xbtlin/ai-berkshire`, struttura a skill/agent, ricerca value, più prospettive di investimento, report e strumenti di audit.

**Idea utile per noi:** non copiare un “investitore famoso”, ma adottare disciplina di ricerca: più punti di vista indipendenti, inversion test, data-confidence, cross-check dei numeri, conclusione obbligatoria e riproducibilità.

**Da non copiare alla cieca:** performance dichiarate dal progetto e personificazione degli investitori non sono evidenza di alpha. Per il nostro Committee contano processo e verificabilità, non il personaggio.

### V02 · 17:24 · Anthropic Financial Services / agent templates

Elementi visibili: workflow finanziari, analisi di portafoglio, modello/valuation, earnings transcript, guidance, margin, capex, analyst-style output.

**Idea utile:** skill specializzate e output strutturati; earnings/catalyst research separata dalla pura tecnica; ogni deliverable deve avere fonti e human review.

### V03 · 17:25 · Plugin finanziari / GitHub / Claude

Elementi visibili: installazione/selezione di plugin finanziari da repository, workflow `/morning notes`, dati aggiornati e report.

**Idea utile:** architettura ad adapter/skill. Il nostro Trade Committee deve poter cambiare provider senza cambiare il Verdict Engine. I provider devono stare dietro interfacce stabili.

### V04 · 17:26 · Morning Note / Catalyst Calendar

Elementi visibili: market morning note, portafoglio allegato, catalyst calendar, report sintetico periodico.

**Idea utile:** Market Health e Catalyst Calendar devono essere moduli reali, non testo generico. Per un singolo titolo servono earnings, eventi societari e macro-eventi realmente rilevanti nel nostro orizzonte.

### V05 · 17:27 · Daily Stock Analysis

Elementi visibili: repository `ZhuLinsen/daily_stock_analysis`, lavoro schedulato/background, indicatori tecnici, segnale, dashboard decisionale.

**Idea utile:** provider resilience, task status/progress, output operativo compatto, anti-chasing rule, separazione tra raccolta dati e sintesi AI, notifiche solo quando utili.

### V06 · 17:28 · AI Hedge Fund

Elementi visibili: schema multi-agent con Market/Social/News/Fundamentals, team Bullish/Bearish, risk manager, portfolio manager ed execution; fonti rappresentate nel diagramma includono Yahoo Finance, social/news e dati fondamentali.

**Idea utile:** specialisti indipendenti e soprattutto **Bull vs Bear + Risk** prima del verdetto. Non serve importare l'intero framework: ci interessa il pattern di separazione delle responsabilità e cross-examination.

### V07 · 17:28:59 · Catalyst Calendar

Elementi visibili: skill/template per creare un calendario catalyst da holdings, scelta dell'orizzonte, earnings e macro events, output Excel/weekly note/live HTML.

**Idea utile:** per il Committee il calendario deve essere focalizzato sul ticker e sull'orizzonte 3-6 mesi; earnings imminenti devono essere un gate/risk flag, non un semplice campo informativo.

### V08 · 17:29 · Deep Dive / Bull vs Bear

Elementi visibili: market-health dashboard, institutional-style company deep dive con business model, financials, growth drivers, balance sheet, valuation e management; schema Bull vs Bear con cross-examination e “honest lean”.

**Idea utile:** questa è la reference più vicina alla UX finale desiderata: prima snapshot sintetico, poi deep dive, poi due tesi opposte, infine verdict. La pagina non deve ripetere gli stessi dati in più sezioni.

---

## 3. Fonti originali verificate

### 3.1 AI Berkshire

Repository: `xbtlin/ai-berkshire`.

Dal README originale emergono pattern utili:
- decisione forzata invece di conclusioni evasive;
- prospettive indipendenti e conflittuali;
- information richness / confidence;
- inversion test e red flags;
- cross-check dei dati finanziari;
- calcoli deterministici con strumenti dedicati;
- ricerca riproducibile;
- agenti paralleli con sintesi finale.

**Decisione:** `ADAPT`, non importare come motore decisionale.

### 3.2 Anthropic Financial Services

Repository ufficiale: `anthropics/financial-services`.

La struttura ufficiale separa:
- Agents;
- Skills;
- Commands;
- Connectors;
- managed-agent wrappers.

I vertical plugin includono financial analysis, equity research, investment banking, private equity e wealth management. I connector citati ufficialmente includono provider enterprise come Daloopa, Morningstar, S&P Global, FactSet, Moody's, MT Newswires, Aiera, LSEG e PitchBook. Molti richiedono abbonamento/entitlement separato.

**Decisione:** `ADAPT` per architettura e workflow. Non basare la V2 su provider enterprise a pagamento se esiste un'alternativa affidabile gratuita/low-cost.

### 3.3 Daily Stock Analysis

Repository reference osservato nel video: `ZhuLinsen/daily_stock_analysis`; è stata verificata una copia pubblica coerente `realcxm/ZhuLinsen-daily_stock_analysis`.

Il README dichiara:
- market data: AkShare, Tushare, Baostock, YFinance;
- news search: Tavily, SerpAPI, Bocha;
- AI: Gemini + provider OpenAI-compatible;
- GitHub Actions;
- WebUI con analisi asincrona e task status;
- technical + volume/chip + sentiment/news + market review;
- regola anti-chasing e livelli buy/stop/target.

**Decisione:** `REUSE/ADAPT` di pattern di orchestrazione, provider abstraction, task progress e notification discipline; audit del codice prima di riusare moduli.

### 3.4 AI Hedge Fund

Repository: `virattt/ai-hedge-fund`, licenza MIT dichiarata dal progetto.

Il progetto attuale si presenta come proof-of-concept/research e usa Financial Datasets per prezzi/fondamentali/earnings più un LLM provider. Supporta backtest e modelli/strategie pluggable.

**Decisione:** `ADAPT` per specialisti, bull/bear/risk e backtestability. `REJECT` dell'idea di usarlo direttamente come motore di ordini reali.

---

## 4. Data Source Matrix proposta

La tabella distingue ciò che serve al Committee da ciò che oggi esiste nella V1.

| Dominio | Dati/check | Primary candidata | Secondary/Fallback | Costo/nota | Stato V1 | Decisione |
|---|---|---|---|---|---|---|
| Price/Volume | OHLCV, volume | Yahoo/yfinance | provider alternativo da validare | gratuito, non SLA | presente | KEEP + fallback |
| Technical | SMA, RSI, ATR, RVOL | calcolo Python su OHLCV | TradingView solo cross-check/manuale | deterministico | presente | KEEP |
| Relative Strength | vs SPY/benchmark | calcolo nostro | TradingView/LAB-FEAT-001 | benchmark per mercato | parziale | BUILD |
| Fundamentals | market cap, PE, FCF, ROE, growth | Yahoo/yfinance | SEC/company filings | Yahoo non è fonte primaria regolatoria | presente/parziale | HARDEN |
| SEC filings | 10-K, 10-Q, 8-K | SEC EDGAR | Company IR | gratuito | assente | BUILD |
| Insider | Form 4 | SEC EDGAR | provider aggregatore | gratuito | assente | BUILD |
| 13F | institutional/superinvestors | SEC 13F | Dataroma/WhaleWisdom come supporto | ritardato | assente | BUILD |
| Earnings | data evento | Yahoo + Company IR | Nasdaq/exchange calendar da validare | cross-check richiesto | presente | HARDEN |
| Earnings content | revenue/EPS/guidance/margins | Company IR + filing | transcript provider | transcript può essere paywalled | assente | BUILD |
| News/Catalyst | news recenti/materiali | Company IR/SEC + news search | Tavily/SerpAPI/provider | costi/rate limit variabili | assente | BUILD |
| Analysts | consensus/targets/revisions | provider verificabile | Yahoo/TradingView manual cross-check | licenze da verificare | assente | EVALUATE |
| Business/Moat | business model, competition | filings + IR | web research | reasoning con fonti | pseudo/parziale | BUILD |
| Management | capital allocation, track record | filings, proxy, IR | web research | qualitativo, source-required | pseudo/parziale | BUILD |
| Market Health | SPY/VIX/rates/sector | market feeds | FRED/benchmark ETF | dipende dal dato | assente | BUILD |
| Portfolio Risk | overlap, sector, heat | nostro DB Production | Fineco/manual reconciliation | interno | assente | BUILD |
| Trade Plan | entry/stop/TP/RR | nostro engine | ATR/structure | deve rispettare CORE | presente semplificato | REWORK |

### Regola provider

Per ogni dato critico definire:
1. primary;
2. secondary;
3. freshness timestamp;
4. conflict flag;
5. fallback behavior;
6. confidence contribution.

Mai trasformare `N/D` in un numero inventato.

---

## 5. Audit dei 16 step attuali

| # | Step V1 | Realtà attuale | Giudizio |
|---:|---|---|---|
| 1 | Caricamento candidato | ticker manuale | REALE |
| 2 | Market Data | 1y OHLCV via yfinance | REALE |
| 3 | Data Quality / indicatori | SMA/RSI/ATR/RVOL calcolati | REALE |
| 4 | Fundamental Deep Dive | subset di campi `Ticker.info` | PARZIALE, non “deep dive” |
| 5 | Business Quality / Management | score da metriche finanziarie; moat/management N/D | PSEUDO/PARZIALE |
| 6 | Valuation | soprattutto Forward PE + PEG | PARZIALE |
| 7 | Technical / Price Action | prezzo vs SMA + RSI | REALE ma semplice |
| 8 | Volume / Relative Strength | soprattutto RVOL; RS benchmark non completa | PARZIALE |
| 9 | Earnings & Catalyst Calendar | data earnings | PARZIALE |
| 10 | News / Analyst / Insider / 13F | non implementato | NON IMPLEMENTATO |
| 11 | Market & Sector | non implementato | NON IMPLEMENTATO |
| 12 | Bull Case | derivato dagli score precedenti | REALE ma non indipendente |
| 13 | Bear Case / Inversion | derivato dagli score precedenti | REALE ma non indipendente |
| 14 | Portfolio Risk | non collegato a Production | NON IMPLEMENTATO |
| 15 | Entry / Stop / Target | formula ATR semplificata | REALE ma da riallineare al CORE |
| 16 | Final Committee | weighted score + gate | REALE, ma dipende da input incompleti |

**Conclusione audit:** la dicitura `16/16 analisi completata` è fuorviante. Deve diventare copertura reale, ad esempio `9 reali / 4 parziali / 3 non implementati`, oppure equivalente calcolato dinamicamente.

---

## 6. Architettura V2 proposta

```text
Production / Multi-Horizon
        |
        | candidati BUY / PRE-BUY
        v
Candidate Queue (read-only)
        |
        | selezione manuale
        v
TRADE COMMITTEE ORCHESTRATOR
        |
        +--> Market & Technical Adapter
        +--> Fundamentals / SEC Adapter
        +--> Earnings & Catalyst Adapter
        +--> News / Analyst Adapter
        +--> Insider / 13F Adapter
        +--> Business / Management Research
        +--> Market & Sector Context
        +--> Portfolio Risk Adapter (nostro DB)
        |
        v
Evidence Store + Source Matrix
        |
        +--> Bull Analyst
        +--> Bear Analyst
        +--> Risk Reviewer
        |
        v
Verdict Engine
 APPROVE / WAIT / REJECT
        |
        v
Trade Plan manuale
```

### Separazione obbligatoria

- **Data adapters** raccolgono fatti.
- **Deterministic analytics** calcolano indicatori, ratios, R/R.
- **Research reasoning** interpreta solo dati con fonte.
- **Bull/Bear** devono poter arrivare a conclusioni diverse.
- **Risk reviewer** non deve essere lo stesso processo che ha costruito la tesi bullish.
- **Verdict Engine** sintetizza e applica gate predefiniti.

---

## 7. UX della pagina

La pagina principale deve rispondere in pochi secondi a:

1. Lo comprerei?
2. A quale prezzo?
3. Quanto rischio?
4. Perché sì?
5. Perché no?
6. Quanto sono affidabili i dati?

### Vista principale

- Ticker / prezzo / timestamp dati
- Engine Score (se disponibile)
- Committee Score
- Data Confidence
- Verdict
- grafico candlestick 6-12m con SMA20/50/200, Entry, Stop, TP1, TP2, earnings marker
- trade plan: Entry ideale, Buy Range, Max Buy, Stop, TP1, TP2, R/R, Qty
- 3 motivi sì
- 3 motivi no
- 3 condizioni di invalidazione
- **Copertura analisi** compatta

### Approfondimenti in tab/expander

- Fundamentals & Valuation
- Technical / Volume / RS
- Earnings & Catalysts
- Business / Moat / Management
- News / Analyst / Insider / 13F
- Market / Sector
- Portfolio Risk
- Bull vs Bear / Cross-examination
- Sources & Data Quality
- Diagnostics (solo tecnico)

### Da eliminare dalla vista principale

- JSON grezzo;
- timeline ripetitiva dei 16 step;
- SMA ripetute se già chiare nel grafico;
- earnings duplicati in più sezioni;
- guardrail ripetuti;
- bull/bear duplicati;
- run log tecnico esteso.

Il log persistente può restare nel DB per audit/debug, ma la UI operativa deve mostrare solo `RUNNING / COMPLETE / PARTIAL / FAILED` e gli errori realmente azionabili.

---

## 8. Cosa sfruttare davvero dai progetti studiati

### REUSE / ADAPT prioritario

1. **Provider abstraction e fallback** da Daily Stock Analysis.
2. **Task progress asincrono** e stato run leggibile.
3. **Skill/adapter separation** da Anthropic Financial Services.
4. **Bull/Bear/Risk separation** da AI Hedge Fund.
5. **Inversion, red flags, data richness/confidence** da AI Berkshire.
6. **Catalyst calendar** come gate reale.
7. **Source-attribution** per ogni conclusione qualitativa.
8. **Cross-check deterministico** dei numeri importanti.

### REJECT / evitare

1. Copiare score o soglie senza backtest/evidenza.
2. Usare performance dichiarate dai repository come prova di efficacia.
3. Importare framework completi dentro Production.
4. Lasciare un LLM decidere entry/stop/size senza guardrail deterministici.
5. Dipendere da provider enterprise non disponibili al nostro ambiente.
6. Presentare un check come COMPLETE quando la fonte manca.
7. Aggiungere decine di agenti solo perché “multi-agent” suona sofisticato.

---

## 9. Piano di implementazione suggerito

### P0 · Correttezza e trasparenza
- sostituire `16/16` con Coverage Matrix reale;
- pulizia UI e rimozione ridondanze;
- grafico operativo;
- classificazione `REAL / PARTIAL / NOT IMPLEMENTED / FAILED`;
- source/timestamp per i dati;
- Data Confidence derivata dalla copertura reale.

### P1 · Fonti gratuite/ufficiali ad alto valore
- SEC EDGAR: 10-K/10-Q/8-K/Form 4/13F;
- Company IR: earnings release, guidance, investor presentation;
- benchmark/market context;
- portfolio adapter interno;
- RS vs benchmark reale.

### P2 · Research enrichment
- news/catalyst search multi-provider;
- analyst consensus/revisions se licenza/fonte adeguata;
- business/moat/management con source-attributed reasoning;
- Bull vs Bear indipendenti + cross-examination.

### P3 · Misurazione del valore aggiunto
- confrontare decisione Engine vs Committee;
- registrare false conferme / false rejection;
- misurare outcome ex-post;
- promuovere solo check che aggiungono informazione misurabile.

---

## 10. Regole di governance

- Trade Committee resta **RESEARCH ONLY** finché non esiste evidenza sufficiente.
- Nessun ordine broker automatico.
- Nessun nuovo provider entra senza documentazione di licenza/costo/rate limit.
- Nessuna soglia entra nel Verdict Engine perché “sembra ragionevole”: deve essere predefinita o validata.
- Un WARNING non è un errore runtime, ma deve ridurre confidence se riguarda una dimensione rilevante.
- Un check non implementato non può contribuire positivamente allo score.
- Ogni cambiamento deve aggiornare questo documento e `docs/TRADE_COMMITTEE.md`.

---

## 11. Conclusione

I video contengono idee utili, ma il valore non è “far fare trading all'AI”. Il valore per il nostro sistema è costruire **una due diligence manuale, verificabile, modulare e contraddittoria** sopra candidati già selezionati dal motore.

La V1 attuale è un prototipo valido dell'orchestrazione, ma non è ancora il Committee completo descritto dai 16 nomi degli step. La V2 deve prima rendere onesta la copertura e poi aggiungere, una per volta, fonti e moduli reali.
