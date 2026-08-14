# trading-engine-v2 — PARITY FIRST v2.1

Architettura centrale per USA e Italia costruita con un principio vincolante:
**la Phase A non modifica la strategia finanziaria**.

Le baseline congelate sono:
- `reference/usa_v5_5.py`
- `reference/italy_v1_2.py`

Il runner centrale usa ancora direttamente queste baseline durante la Phase A.
I moduli in `engine/`, `market/`, `portfolio/`, `state/` e `reports/` sono la
mappa di estrazione controllata per la Phase B.

## Correzioni v2.1
- aggiunto `engine/utils.py` con le utility comuni mancanti;
- aggiunto `reports/email_report.py` con binding parity-safe al report della baseline;
- aggiunti controlli automatici sul `FUNCTION_MAP.csv`;
- test che fallisce se una funzione dei monoliti resta senza mapping;
- test che fallisce se una destinazione dichiarata non esiste fisicamente;
- manifest SHA-256 delle due baseline congelate;
- test di parità per utility pure e report binding;
- rimossi cache/test artifact dal pacchetto distribuibile.

## Garanzia Phase A
La pipeline reale esegue ancora il codice originale delle baseline. Questo evita
regressioni durante la migrazione dell'architettura.

## Test
```bash
pip install -r requirements.txt
pytest -q
```

Criterio minimo prima di uno scan: tutti i test devono essere verdi.
Nel pacchetto v2.1: **16 test superati**.

## Run manuale
```bash
python -m monitor.master_scan --market usa
python -m monitor.master_scan --market italy
```

Gli schedule automatici restano disabilitati durante la Phase A.

## Phase A acceptance
A parità di input OLD e NEW devono concordare su:
- Quality / Opportunity Score;
- componenti e penalità;
- technical state / RS;
- Entry / Buy Zone / Max Buy / Stop / TP1 / TP2;
- R/R lordo e netto;
- sizing;
- data quality / anomaly flags;
- trigger;
- 8 gate;
- decisione;
- operational state;
- PRE-BUY dove già presente nella baseline;
- change state con lo stesso storico.

## Phase B
Solo dopo la parità: estrazione fisica delle funzioni dai monoliti, una funzione o
un gruppo alla volta. Ogni estrazione deve superare i parity test prima di diventare
ACTIVE. Solo dopo: DB unico, schedule FAST_MONITOR, WhatsApp e altre evoluzioni.

### v2.2 market-boundary guardrails
Phase A now makes four USA/Italy boundaries explicit in modular helpers: PRE-BUY remains USA-only unless explicitly enabled; Italy financial-sector adjustments cannot leak into USA; missing benchmark history yields RS `N/D`; and GEM filtering is Italy-only. These helpers do not alter the frozen reference engines used by the Phase-A full-scan pipeline.
