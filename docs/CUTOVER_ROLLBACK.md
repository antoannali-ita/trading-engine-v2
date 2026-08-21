# Cutover / Rollback Runbook

## Obiettivo
Portare in produzione l'architettura orchestrata senza modificare la logica finanziaria dei motori e mantenendo un rollback semplice.

## Ordine di cutover
1. Eseguire `supabase/migrations/002_dashboard_performance_optimization.sql`.
2. Verificare secret richiesti nei tre repository.
3. Unire TradingAgents PR di integrazione.
4. Unire Multi-Horizon PR di integrazione.
5. Unire Trading Engine V2 PR dell'orchestratore.
6. Avviare manualmente un CORE USA e un CORE ITALY.
7. Verificare `engine_runs`, `signals`, `v_engine_health`.
8. Avviare manualmente FAST USA/ITALY durante sessione regolare.
9. Verificare dispatch Multi-Horizon e successivo risultato in Supabase.
10. Verificare dispatch TradingAgents solo su confluenze qualificate.
11. Verificare una sola notifica finale per `signal_id`/canale.
12. Pubblicare la dashboard Streamlit e verificare `ESEGUI ORA`.

## Criteri GO
- Nessuna regressione sui risultati CORE/FAST rispetto alla baseline.
- Run con stato SUCCESS e nessun errore persistente.
- Nessuna email/WhatsApp duplicata.
- Multi-Horizon non modifica i risultati originali dei motori.
- TradingAgents parte solo sui candidati qualificati.
- Dashboard legge dati coerenti con Supabase.
- Manual run completa il ciclo REQUESTED -> DISPATCHED -> RUNNING -> SUCCESS/FAILED.

## Rollback rapido
1. Disabilitare il workflow `orchestrator_tick.yml` o ripristinare il commit precedente in `trading-engine-v2`.
2. Riattivare, se necessario, le notifiche dirette dei motori legacy.
3. Ripristinare i branch/main ai commit pre-cutover tramite revert dei merge commit.
4. Non eliminare le nuove tabelle Supabase: sono additive e non impediscono ai motori legacy di funzionare.
5. Conservare `engine_runs`, `signals`, `system_events` e `notification_events` per analizzare la causa.

## Principio
Il rollback applicativo deve precedere qualsiasi rollback dati. Le migration 001/002 sono additive: rimuovere tabelle o indici durante un incidente aumenta il rischio senza alcun vantaggio operativo.
