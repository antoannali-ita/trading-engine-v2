# Changelog

## v2.1 parity-first
- Corretto gap `engine/utils.py` segnalato in audit.
- Corretto gap `reports/email_report.py` segnalato in audit.
- Aggiunti test di completezza mapping e destination files.
- Aggiunto manifest SHA-256 delle baseline.
- Aggiunti parity test per utility e report binding.
- Nessuna modifica a scoring, soglie, trigger, entry, sizing, R/R o Decision Engine.

## v2.2 - Market-boundary guardrails
- Added explicit Phase-A guardrails preventing USA PRE-BUY presentation from leaking into Italy.
- Added Italy-only financial-sector adjustment helper; USA is never implicitly treated with Italy financial exceptions.
- Added explicit RS fallback to `N/D` when benchmark history is unavailable.
- Added Italy-only GEM/foreign-listing exclusion helper.
- Added four dedicated boundary test files covering PRE-BUY, financials, RS benchmark failures and GEM filtering.
- No frozen baseline, scoring formula, threshold, entry/RR, trigger, sizing or decision rule was changed.
