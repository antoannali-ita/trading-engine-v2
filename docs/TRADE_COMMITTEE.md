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
- market data e indicatori deterministici via dipendenze già presenti (`yfinance`, numpy);
- score separati per Technical, Quality, Valuation e Volume;
- verdict APPROVE / WAIT / REJECT;
- timeline 16 step;
- guardrail RESEARCH ONLY.

## Limiti V1 dichiarati
La V1 NON pretende ancora una due diligence completa. SEC/13F/Form 4, news multi-provider, analyst cross-check, moat/management qualitativo, Market Health, portfolio correlation e persistenza Supabase dei run sono esposti come WARNING o roadmap finché i relativi adapter non sono implementati e validati.

Nessun dato mancante viene inventato.

## Evoluzione prevista
- Candidate Queue alimentata dai segnali `BUY_NOW`, `BUY_LIMIT`, `IN_BUY_ZONE`, `PRE_BUY_HIGH`, `APPROACHING`.
- Data Source Matrix con primary/secondary/fallback e conflict flag.
- adapter SEC/company IR/catalyst/news.
- Bull vs Bear indipendenti e cross-examination.
- persistenza `committee_runs` e confronto con run precedente.
- Trade Plan APPROVED monitorabile, senza broker execution nella fase iniziale.
- misurazione ex-post dell'effettivo valore aggiunto del Committee.

## Guardrail permanente
`ENGINE SCORE != COMMITTEE SCORE != DATA CONFIDENCE`.

Il Committee deve poter contraddire l'Engine. Un APPROVE non equivale a un ordine e resta necessaria una decisione umana.
