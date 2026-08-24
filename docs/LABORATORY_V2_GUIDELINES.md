# Laboratory V2 — Linee guida operative e di lettura

## Scopo

Il Laboratory è un ambiente di ricerca e validazione quantitativa separato da Production.
Non genera ordini reali e non deve essere interpretato come una lista di BUY.
Il suo obiettivo è trasformare segnali e strategie in esperimenti misurabili, confrontabili e migliorabili.

## Pipeline

MARKET → STRATEGIES → SIGNAL → TIER A/B/C → PAPER / SHADOW OUTCOME → COSTI + PERFORMANCE → STRATEGY × TIER → MATURITY → CANDIDATE_REVIEW → HUMAN VALIDATION → eventuale Production.

Production rimane separata e non viene modificata automaticamente dal Laboratory.

## Tier

### A — quasi-production
Baseline di qualità più elevata. Richiede Data Quality GREEN e gate più severi. È comunque paper trading.

### B — experimental
Accetta alcuni gate più permissivi per verificare se le soglie severe eliminano opportunità valide. Data Quality YELLOW è ammessa e deve essere evidenziata.

### C — RESEARCH ONLY / NON OPERATIONAL
Controfattuale sperimentale. Può accettare trigger ancora WAITING e R/R inferiore ai livelli normalmente operativi.
Non deve mai essere presentato come BUY, PRE-BUY operativo o candidato diretto a ordine reale.

## Data Quality

- RED: veto per A/B/C.
- YELLOW: ammesso solo B/C con flag esplicito.
- GREEN: eleggibile per A/B/C in base alle rispettive regole.

I blocchi dati devono restare separati dai blocchi di policy.

## Gate Analysis

La dashboard deve distinguere:

- DATA GATES: qualità dati, ATR invalido, prezzo/entry incoerenti, dati mancanti.
- POLICY GATES: score, trigger, R/R, estensione/MaxBuy, earnings.

I fallimenti devono essere leggibili separatamente per Tier A, Tier B, Tier C e LEGACY_STRICT.
Un segnale che fallisce A ma passa B non è genericamente "bloccato": è A-fail / B-pass.

LEGACY_STRICT è diagnostico. Non va descritto come misura completa di "alpha perso".

## Shadow outcomes

Tre popolazioni:

1. ACCEPTED_PAPER: paper trade completo.
2. REJECTED_C_VALID_DATA: nessuna posizione aperta, ma tracking T0/D+1/D+3/D+5/D+10/D+20, MFE e MAE.
3. DATA_REJECT: può essere registrato per diagnostica, ma è escluso dalle statistiche di performance.

Questo riduce il bias del confronto tra vecchi e nuovi gate senza aprire migliaia di posizioni virtuali.

## Risk identity

Ogni esperimento conserva:

- risk_key = EQUITY:TICKER
- experiment_key = TICKER:STRATEGY:TIER

Lo stesso ticker può essere testato da strategie diverse, ma il rischio sottostante rimane aggregabile tramite risk_key.

## Cost model

Mostrare sempre Gross e Net separati.

Scenario Fineco conservativo/storico:
- 12 USD per eseguito
- 24 USD round trip

Scenario scontato comunicato dall'utente:
- 9,90 USD per eseguito
- 19,80 USD round trip
- verificare la tariffa quando effettivamente applicata al conto

Lo slippage è una stima di ricerca e deve restare separato dalle commissioni.

Metriche consigliate:
- Gross P&L
- Net P&L 12
- Net P&L 9.90
- Gross PF
- Net PF 12
- Net PF 9.90
- Cost Drag
- Win Rate
- Avg Net Return
- Max Drawdown

## Maturità statistica

La maturità è calcolata per Strategy × Tier:

- N < 10: UNDERTESTED
- 10 ≤ N < 30: EARLY
- 30 ≤ N < 50: DEVELOPING
- N ≥ 50: EVALUABLE

Non dividere inizialmente anche per settore per attribuire lo stato principale: le celle diventerebbero troppo sottili.
Il settore resta una dimensione analitica secondaria finché il campione non è sufficiente.

La UI deve dichiarare che possono servire diverse settimane per rendere valutabile una singola combinazione Strategy × Tier.

## Lifecycle della strategia

Il Laboratory può mostrare stati descrittivi come UNDERTESTED, EARLY, DEVELOPING, EVALUABLE, REVIEW o CANDIDATE_REVIEW.

CANDIDATE_REVIEW significa solo che una combinazione merita revisione umana.
Non equivale a promozione automatica in Production.

Qualsiasi eventuale promozione deve passare da review umana e da evidenza leggibile: N, Net PF, Win Rate, drawdown, regime, forward paper e stabilità dei risultati.

## Le tre pagine principali

### Laboratory Control
Risponde: "Il Laboratory sta lavorando e dove si blocca?"
Mostra funnel per sessione, A/B/C, conversione, DATA/POLICY gates, confronto con LEGACY_STRICT e shadow population.

### Paper Portfolio
Risponde: "Cosa stiamo realmente sperimentando?"
Mostra ticker, strategy, tier, RiskKey, ExperimentKey, entry, ideal entry, qty, notional, stop, TP1/TP2, Gross/Net R/R, costi, P&L e stato.
Tier C deve essere visivamente marcato RESEARCH ONLY / NON OPERATIVO.

### Research / Evolution
Risponde: "Cosa stiamo imparando?"
Mostra statistiche Strategy × Tier, maturità, Gross/Net PF, cost drag, win rate, drawdown, shadow outcomes e backtest come contesto.
Nessun verdetto automatico di promozione.

## Principio finale

Il Laboratory non deve massimizzare il numero di BUY. Deve massimizzare la qualità dell'apprendimento.
Più esperimenti sono utili solo se rimangono tracciabili, separati per strategia/tier, con costi realistici e motivi di pass/fail leggibili.
