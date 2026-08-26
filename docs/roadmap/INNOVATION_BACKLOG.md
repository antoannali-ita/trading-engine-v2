# Innovation Backlog

Le idee entrano qui prima di entrare nell'architettura Production.

| ID | Idea | Problema che risolverebbe | Evidenza richiesta | Stato |
|---|---|---|---|---|
| INN-001 | Provider market/fundamental aggiuntivi | Gap di copertura/affidabilità | Campi mancanti/stale misurati e confronto provider | IDEA |
| INN-002 | Provider fallback layer | Outage upstream | Failure-rate e semantica fallback deterministica | ANALYSIS |
| INN-003 | Notification event IDs/deduplication | Alert duplicati/silenziosi | Dati di validazione alert | ANALYSIS |
| INN-004 | ETA evidence strategie a intervallo | Tempo di maturità poco chiaro | Più settimane di throughput | APPROVED CONCEPT |
| INN-005 | Vista architetturale sito migliorata | Interpretazione difficile con crescita moduli | Audit UI/navigation | IDEA |
| INN-006 | Redis | Collo di bottiglia runtime/cache | Violazione SLA/runtime misurata | FROZEN |
| INN-007 | Queue/event bus | Necessità affidabilità/disaccoppiamento | Event-loss/throughput dimostrato | FROZEN |
| INN-008 | Portfolio optimiser avanzato | Ottimizzazione rischio cross-position | Storico sufficiente e stime stabili | FROZEN |
| INN-009 | AI enrichment nel flusso operativo | Contesto qualitativo/catalizzatori | Uplift OOS A/B predefinito | LAB ONLY |
| INN-010 | Esecuzione semi-automatica | Ridurre latenza esecuzione manuale | Tutti i maturity gate di execution | DISABLED |
| PROD-001 | TradingView Extended Data in Production (RelVol, RS, SMA distance, ATR, gap, 52W) | Possibile miglioramento trigger/APPROACHING, non ancora dimostrato | LAB-FEAT-001 + evidence per singola feature + regressione + shadow validation | FROZEN |

## LAB-FEAT-001

La raccolta passiva delle candidate feature nel Laboratory è ammessa durante il freeze perché non modifica il CORE e non genera nuovi trade. È documentata in `docs/LAB_FEATURE_ENRICHMENT.md`. Non equivale all'approvazione di `PROD-001`.

## Regola

Un'idea può essere utile senza meritare implementazione. La promozione richiede un problema osservato, un beneficio misurabile o un evidence gate predefinito. Quando una feature viene implementata realmente in Production, il comportamento passa nella documentazione AS-IS mantenendo lo storico della decisione.