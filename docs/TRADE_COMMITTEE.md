# LAB-RESEARCH-001 · Trade Committee

## Scopo
Modulo manuale, autonomo e read-only verso Production per una due diligence aggiuntiva immediatamente prima di un eventuale acquisto reale.

Non è una strategia, non sostituisce CORE/Multi-Horizon, non genera ordini e non modifica score, eligibility, entry o segnali Production.

## Flusso
`Candidati Engine -> selezione manuale -> Trade Committee -> APPROVE / WAIT / REJECT -> decisione umana`

La V1 accetta un ticker manuale. La Candidate Queue automatica dai segnali BUY/PRE-BUY è una successiva integrazione, da realizzare senza accoppiare il Committee al CORE.

## Pipeline a 16 check
1. candidato
2. market data
3. data quality
4. fundamental deep dive
5. business quality / management
6. valuation
7. technical / price action
8. volume / relative strength
9. earnings / catalysts
10. news / analyst / insider / 13F
11. market / sector
12. bull case
13. bear case / inversion
14. portfolio risk
15. entry / stop / target
16. final committee

La UI mostra l'avanzamento live e rende espliciti WARNING e dati N/D.

## Run Log / Diagnostics
Ogni avvio del Committee riceve un `run_id` univoco, ad esempio `TC-20260826T213102123456Z-CSCO`.

Stati run:
- `RUNNING`: esecuzione in corso;
- `COMPLETE`: verdetto prodotto;
- `FAILED`: errore reale che impedisce il completamento.

Stati step:
- `COMPLETE`: step coperto;
- `WARNING`: step eseguito ma incompleto per fonte/dato mancante; non è un crash;
- `FAILED`: errore runtime dello step/run.

Il run è considerato terminato correttamente solo quando esiste il risultato finale, lo step 16 è completato e la testata run passa a `COMPLETE`. Se un'eccezione impedisce il verdetto, il run viene marcato `FAILED` con tipo errore, messaggio e traceback sintetico. I WARNING non rendono il run fallito ma riducono la Data Confidence.

Il log corrente è visibile direttamente nella pagina. Quando Supabase è configurato e la migration è applicata, ogni run e ogni step vengono anche persistiti senza sovrascrivere i run precedenti.

Tabelle:
- `trade_committee_runs`: testata, esito, score, confidence, errori e payload finale;
- `trade_committee_run_steps`: dettaglio step-by-step del run.

La pagina mostra gli ultimi run e permette di aprire il dettaglio degli step. Se Supabase o le tabelle non sono disponibili, il Committee continua a funzionare e dichiara esplicitamente che il log è solo locale/sessione.

## Grafico tecnico
La pagina include un grafico interattivo Plotly costruito dai dati prezzo recuperati via `yfinance`.

Mostra:
- candele giornaliere degli ultimi 6 mesi;
- SMA20, SMA50 e SMA200 quando disponibili;
- Entry proposta dal Committee;
- Stop;
- TP1;
- TP2.

Il grafico è solo una visualizzazione degli stessi livelli operativi del Committee e non modifica score, verdict o segnali Production. Se il provider prezzo o Plotly non sono disponibili, il Committee continua a funzionare e mostra un WARNING limitato alla sezione grafico.

## Reference patterns studiati
- AI Berkshire: business quality, moat, management, valuation, inversion, thesis tracking.
- Anthropic Financial Services: earnings, catalysts, equity research, structured review.
- Daily Stock Analysis: orchestrazione, provider resilience, notification patterns.
- AI Hedge Fund: modularità degli specialisti; non viene importato come motore decisionale.
- TradingView / LAB-FEAT-001: tecnica, volume, RS e volatilità come evidenza.

I repository esterni sono reference/possibili fonti di componenti da sottoporre a REUSE/ADAPT/BUILD/REJECT. Nessun framework esterno viene incorporato integralmente senza audit di licenza, dipendenze, sicurezza e compatibilità.

## V1 implementata
- pagina Streamlit `pages/5_Trade_Committee.py`;
- wrapper dashboard `dashboard/pages/5_Trade_Committee.py`;
- orchestratore indipendente `trade_committee/orchestrator.py`;
- persistenza diagnostica `trade_committee/persistence.py`;
- grafico tecnico `trade_committee/charting.py`;
- migration `supabase/migrations/004_trade_committee_run_log.sql`;
- market data e indicatori deterministici via dipendenze già presenti (`yfinance`, numpy);
- visualizzazione Plotly interattiva;
- score separati per Technical, Quality, Valuation e Volume;
- verdict APPROVE / WAIT / REJECT;
- timeline 16 step;
- storico run persistente e dettaglio step;
- guardrail RESEARCH ONLY.

## Limiti V1 dichiarati
La V1 NON pretende ancora una due diligence completa. SEC/13F/Form 4, news multi-provider, analyst cross-check, moat/management qualitativo, Market Health e portfolio correlation restano WARNING/roadmap finché i relativi adapter non sono implementati e validati.

Nessun dato mancante viene inventato.

## Evoluzione prevista
- Candidate Queue alimentata dai segnali `BUY_NOW`, `BUY_LIMIT`, `IN_BUY_ZONE`, `PRE_BUY_HIGH`, `APPROACHING`;
- Data Source Matrix con primary/secondary/fallback e conflict flag;
- adapter SEC/company IR/catalyst/news;
- Bull vs Bear indipendenti e cross-examination;
- confronto strutturato con run precedente dello stesso ticker;
- Trade Plan APPROVED monitorabile, senza broker execution nella fase iniziale;
- misurazione ex-post dell'effettivo valore aggiunto del Committee.

## Guardrail permanente
`ENGINE SCORE != COMMITTEE SCORE != DATA CONFIDENCE`.

Il Committee deve poter contraddire l'Engine. Un APPROVE non equivale a un ordine e resta necessaria una decisione umana.
