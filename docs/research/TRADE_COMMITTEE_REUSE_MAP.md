# Trade Committee · Open-Source Reuse Map

**Data:** 27/08/2026  
**Ambito:** LAB-RESEARCH-001 / Trade Committee V2  
**Regola:** riusare pattern e componenti solo dopo verifica di licenza, dipendenze, fonte dati e compatibilità con l'architettura esistente.

## 1. Repository verificati

| Progetto | Repository verificato | Licenza | Cosa prendiamo | Modalità |
|---|---|---|---|---|
| AI Berkshire | `xbtlin/ai-berkshire` | MIT | financial rigor, data confidence, inversion/red flags, struttura investment-team/earnings review | ADAPT |
| Daily Stock Analysis | `realcxm/ZhuLinsen-daily_stock_analysis` (fork pubblico coerente col progetto mostrato) | MIT | provider abstraction, task progress, dashboard compatta, fallback discipline | ADAPT |
| AI Hedge Fund | `virattt/ai-hedge-fund` | MIT | separazione specialisti, Bull/Bear/Risk, pluggable models | ADAPT |
| Anthropic Financial Services | pattern mostrato nei video e documentato nella ricerca | da verificare per singolo repository/plugin | architettura skill/adapter/provider | PATTERN ONLY finché upstream/licenza non sono verificati |

## 2. Moduli/pattern AI Berkshire adottati

Riferimenti verificati nel repository:
- `tools/financial_rigor.py`
- `skills/investment-team.md`
- `skills/earnings-team.md`
- `skills/earnings-review.md`
- `skills/investment-research.md`
- `skills/financial-data.md`

### Adattamento nel nostro progetto

| Pattern originale | Implementazione nostra |
|---|---|
| verifica market cap e valuation | `trade_committee/rigor.py` |
| cross validation fonti | `trade_committee/rigor.py` + `tradingview_crosscheck()` |
| information richness / confidence | `coverage` + `data_confidence` in `orchestrator.py` |
| inversion/red flags | `quality_assessment()` + Bull/Bear/Inversion step |
| decisione obbligatoria | `APPROVE / WAIT / REJECT` |
| fonti insufficienti -> dichiararle | `REAL / PARTIAL / N/A / N/D` |

Il codice è stato riscritto/adattato per lo stack del Trading Engine; non viene importato integralmente il framework AI Berkshire.

## 3. Pattern Daily Stock Analysis adottati

Dal progetto sono stati adottati i principi:
- provider separati dal layer di analisi;
- analisi manuale di un singolo ticker;
- progress visibile durante il task;
- output finale orientato alla decisione;
- fallback senza trasformare errori/provider mancanti in dati inventati.

Nel nostro progetto:
- provider/check: `trade_committee/research_checks.py`;
- orchestrazione: `trade_committee/orchestrator.py`;
- UI/progress: `pages/5_Trade_Committee.py`.

Non viene importato il sistema di notifiche del progetto esterno perché il Trade Committee è manuale e on-demand.

## 4. Pattern AI Hedge Fund adottati

Il progetto dichiara esplicitamente finalità educational/research. Non viene usato come motore di trading.

Adottiamo solo:
- separazione tra analisi dei dati, tesi bullish, tesi bearish e risk review;
- idea che il verdetto finale debba sintetizzare specialisti/check differenti;
- guardrail che impediscono a una sola metrica di dominare il risultato.

La V2 implementa una prima versione deterministica del Bull/Bear/Inversion Review. Un eventuale layer LLM multi-agent resta futuro e dovrà essere testato separatamente.

## 5. Componenti costruiti nella V2

### `trade_committee/research_checks.py`
Adapter e check concreti:
- Yahoo Finance / yfinance;
- TradingView Screener (cross-check secondario);
- SEC EDGAR;
- benchmark SPY / FTSEMIB.MI;
- ETF settoriali USA;
- portafoglio Production read-only;
- earnings, news, analyst consensus, insider transactions, institutional holders;
- technical, RS, quality, valuation e trade plan.

### `trade_committee/rigor.py`
Calcoli con `Decimal` per:
- coerenza market cap;
- coerenza P/E;
- cross-validation tra fonti.

### `trade_committee/charting.py`
Grafico Plotly:
- candlestick 6 mesi;
- SMA20/50/200;
- volume;
- Entry/Stop/TP1/TP2.

### `trade_committee/orchestrator.py`
Pipeline a 12 check reali/parziali con:
- fonte esplicita;
- coverage status;
- Data Confidence;
- gate;
- Committee Score;
- verdict.

## 6. Cosa NON abbiamo ancora importato/implementato

- 13F completo per superinvestitori: richiede un adapter dedicato per manager/filing e mapping delle holdings;
- transcript earnings e guidance extraction da Company IR;
- true moat/management research con fonti web/filings;
- news multi-provider Tavily/SerpAPI/altro;
- multi-agent LLM indipendenti;
- Candidate Queue automatica dall'Engine;
- sector concentration live del portfolio.

Questi punti restano backlog e non vengono dichiarati come check `REAL`.

## 7. Regola di licenza

AI Berkshire, Daily Stock Analysis e AI Hedge Fund risultano MIT nei repository verificati. Se in futuro viene copiato un blocco sostanziale di codice invece di riscriverne il pattern, il copyright notice e la licenza MIT originaria devono essere conservati secondo i termini della licenza.

Per Anthropic Financial Services non viene importato codice finché upstream e licenza del componente specifico non sono verificati.
