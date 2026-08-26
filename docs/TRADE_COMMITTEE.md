# LAB-RESEARCH-001 · Trade Committee

## Scopo
Modulo manuale, autonomo e read-only verso Production per una due diligence aggiuntiva immediatamente prima di un eventuale acquisto reale.

Non è una strategia, non sostituisce CORE/Multi-Horizon, non genera ordini e non modifica score, eligibility, entry o segnali Production.

Flusso:

`Candidato -> selezione manuale -> Trade Committee -> APPROVE / WAIT / REJECT -> decisione umana`

## Principio V2
La V1 mostrava 16 step ma alcuni erano soltanto parziali o placeholder. La V2 applica una regola più rigorosa:

`CHECK -> FONTE -> DATO -> CALCOLO -> ESITO -> CONFIDENCE`

Ogni check viene classificato `REAL`, `PARTIAL`, `N/A` oppure `N/D`. La pagina non dichiara più completato un controllo che non è stato realmente eseguito.

## Pipeline V2
1. **Market & Technical** — Yahoo Finance + calcoli Python: OHLCV, SMA20/50/200, RSI14, MACD, ATR14, RVOL, supporti/resistenze.
2. **Data Quality / Cross-check** — TradingView Screener come seconda fonte quando disponibile + controlli aritmetici Decimal su Market Cap e P/E.
3. **Fundamental Deep Dive** — Yahoo Finance: market cap, P/E, forward P/E, PEG, EV/EBITDA, ROE/ROA, liquidità, debito, cash flow, growth, margini, short/ownership.
4. **Business Quality / Financial Strength** — check deterministici su ROE, Current Ratio, D/E, OCF, FCF, crescita e margini. Moat e management qualitativi non vengono inventati.
5. **Valuation** — P/E, forward P/E, PEG, EV/EBITDA e FCF yield con controlli aritmetici.
6. **Earnings / Catalyst Window** — data earnings e storia recente quando disponibile; earnings ravvicinati entrano nei gate.
7. **News / Analyst / Insider / Ownership** — Yahoo Finance: news, analyst consensus/target, insider transactions, institutional holders, short float e days-to-cover quando disponibili.
8. **Official Filings** — SEC EDGAR per emittenti USA: 10-K, 10-Q, 8-K e Form 4 recenti. Il 13F non viene falsamente attribuito al singolo emittente.
9. **Market / Sector / Relative Strength** — SPY per USA, FTSE MIB per Italia; ETF settoriale USA quando disponibile; RS 1m/3m/6m.
10. **Portfolio Context** — lettura read-only di `config/production_portfolio.json`: posizione già presente e peso stimato sullo snapshot.
11. **Entry / Stop / Target / Sizing** — struttura 20 giorni + ATR, resistenze 60/120 giorni, capitale 2.500 USD e commissione Fineco 18 USD per lato.
12. **Bull / Bear / Inversion Review** — sintesi avversariale dei risultati reali precedenti e identificazione delle condizioni che invalidano l'acquisto.

## Fonti V2
| Dominio | Fonte primaria | Secondaria | Nota |
|---|---|---|---|
| Prezzi/volumi | Yahoo Finance / yfinance | TradingView Screener | nessuna SLA gratuita |
| Tecnica | calcolo Python su OHLCV | TradingView | deterministico |
| Fundamentals | Yahoo Finance | controlli aritmetici | SEC resta fonte regolatoria per filings |
| Filings USA | SEC EDGAR | Company IR futura | 10-K/10-Q/8-K/Form 4 |
| Earnings | Yahoo Finance | IR futura | evento usato come gate |
| News/analisti | Yahoo Finance | provider web futuro | copertura dipende dal ticker |
| Insider/istituzionali | Yahoo Finance + SEC Form 4 | 13F dedicato futuro | 13F resta separato |
| Market/RS | SPY / FTSEMIB.MI + sector ETF | — | benchmark coerente col mercato |
| Portfolio | config Production interna | — | read-only |

## Grafico
La pagina include un grafico Plotly interattivo con:
- candele ultimi 6 mesi;
- SMA20/50/200;
- volume;
- Entry;
- Stop;
- TP1;
- TP2.

Il grafico è solo visualizzazione e non modifica il verdetto.

## UI
La vista principale è volutamente compatta:
- verdict;
- Committee Score;
- Data Confidence;
- prezzo;
- copertura reale;
- grafico;
- piano operativo;
- motivi pro/contro.

Gli approfondimenti sono organizzati in tab: Fondamentali, Catalizzatori & ownership, SEC/Mercato, Portafoglio & Data Quality.

Il precedente **Run Log / Diagnostics persistente è stato rimosso dalla pagina e dal flusso operativo** perché ridondante per l'uso manuale. La vecchia migration Supabase resta nel repository come storico di migrazione e non viene più richiamata dalla UI V2.

## Scoring e gate
`ENGINE SCORE != COMMITTEE SCORE != DATA CONFIDENCE`.

Il Committee Score combina tecnica, volumi, qualità finanziaria, valutazione, market context, sentiment e portfolio fit. La Data Confidence dipende dalla copertura reale delle fonti.

Gate V2 principali:
- `Prezzo < SMA50 < SMA200` -> niente APPROVE;
- earnings entro 7 giorni -> niente APPROVE;
- Data Confidence <70% -> niente APPROVE;
- R/R netto TP1 <1.5 -> niente APPROVE.

Un APPROVE non equivale a un ordine reale.

## Pattern open-source adottati
La V2 incorpora/adatta principi verificati dai progetti studiati nei video:
- **AI Berkshire (MIT)**: financial rigor, data confidence, inversion/red flags, decisione non evasiva;
- **Daily Stock Analysis**: provider abstraction, output operativo, progress del task;
- **AI Hedge Fund (MIT)**: separazione Bull/Bear/Risk come pattern, non motore di execution;
- **Anthropic Financial Services**: architettura a skill/adapter/provider, senza dipendere dai connector enterprise a pagamento.

Non è stato copiato integralmente nessun framework esterno. I componenti sono stati riscritti/adattati dietro interfacce del progetto. La ricerca completa è in `docs/research/TRADE_COMMITTEE_SOURCE_RESEARCH.md`.

## Limiti ancora aperti
- moat e management qualitativi richiedono una research layer con fonti esplicite;
- 13F per superinvestitori richiede un adapter dedicato e non può essere dedotto dai soli institutional holders;
- Company IR e transcript earnings non sono ancora adapter primari;
- news cross-provider non è ancora implementato;
- sector concentration del portfolio è ancora parziale;
- Candidate Queue automatica dai segnali Engine resta una successiva integrazione read-only.

## Guardrail permanente
`RESEARCH ONLY · nessun ordine reale · nessuna modifica al CORE Production`.
