# Parity checklist

## Integrità strutturale obbligatoria
- [ ] `FUNCTION_MAP.csv`: nessuna funzione delle baseline senza mapping.
- [ ] Nessuna riga classificata `UNMAPPED`.
- [ ] Ogni destination file dichiarato esiste fisicamente.
- [ ] SHA-256 delle baseline coincide con `BASELINE_SHA256.txt`.
- [ ] `pytest -q` tutto verde.

## OLD vs NEW su input identico
- Quality Score: exact
- Opportunity Score: exact
- Score components/penalties: exact
- Technical state / RS: exact
- Entry / Buy Zone / Max Buy / Stop / TP1 / TP2: <0.2% tolerance
- Gross/Net R/R: <0.05 tolerance
- Sizing: exact con stesso env/config
- Data Quality / anomaly flags: exact
- Trigger: exact
- 8 gates: exact
- Decision: exact
- Operational state: exact
- PRE-BUY: exact dove la baseline lo implementa (USA v5.5)
- Change state: exact con stesso DB history

## Edge cases USA
CSCO, TSM, WDC, BUD, MU, un DATA_REVIEW, un caso `TRADING_CAPITAL=0`.

## Edge cases Italia
TEN, STLAM, un finanziario, 1LOGN/1NFLX esclusi, un caso earnings sanitation,
un titolo normale senza anomalie.

## v2.2 market-boundary guardrails
- [ ] Italy normalized output never introduces PRE-BUY while `prebuy_enabled: false`.
- [ ] Financial-sector special treatment can be activated only for `market: ITALY`.
- [ ] Missing benchmark history produces RS `N/D`, never an exception or synthetic RS value.
- [ ] GEM regex exclusion is active only for `market: ITALY`.
