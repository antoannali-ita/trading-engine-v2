# Trading Engine Control Center

Dashboard Streamlit del progetto Trading Engine V2.

## Avvio locale

```bash
pip install -r requirements.txt
export SUPABASE_URL=...
export SUPABASE_SECRET_KEY=...
export DASHBOARD_PASSWORD=...
streamlit run dashboard/app.py
```

## Secret richiesti

- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY`
- `DASHBOARD_PASSWORD` opzionale ma raccomandato

La service role Supabase viene usata solo dal processo server-side Streamlit e non deve essere inserita in JavaScript client-side o repository.

## Schermate

1. **Overview** - stato complessivo, health motori, confluenze, frequenza run.
2. **Motori** - registry, scheduler, ultimo/prossimo run, stato calcolato.
3. **Segnali** - filtri per mercato/engine/ticker, segnali actionable e livelli operativi.
4. **TradingAgents** - analisi AI, alignment, verdict, livelli e stato esecuzione.
5. **Run & Log** - storico engine_runs e richieste manuali.
6. **Esegui ora** - inserisce una riga `manual_run_requests`; l'orchestratore esegue il dispatch GitHub.
7. **Performance** - risultati storici prodotti dal performance worker.
8. **Notifiche** - email/WhatsApp tentati, inviati, falliti o saltati.
9. **Architettura** - diagramma live della catena applicativa.

## Deploy

Il codice è pronto per Streamlit Community Cloud o un runtime Streamlit equivalente. Configurare i secret nel runtime di deploy. Non esporre `SUPABASE_SECRET_KEY` nel browser.
