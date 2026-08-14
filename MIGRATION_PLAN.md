# Migration Plan — parity first

## Phase A: parità prima di tutto
1. Conservare entrambe le baseline `reference/` congelate.
2. Usare `engine/analyzer.py` come orchestratore centrale, senza cambiare la strategia.
3. Conservare separati i DB/path USA e Italia.
4. Verificare `FUNCTION_MAP.csv`: zero funzioni UNMAPPED e zero destination file mancanti.
5. Eseguire `pytest -q` prima di ogni scan.
6. Eseguire diverse sedute in parallelo OLD vs NEW.
7. Niente schedule automatici, WhatsApp o ordini reali finché la parità non è dimostrata.

## Phase B: estrazione meccanica controllata
Estrarre una funzione/gruppo alla volta dalle baseline verso i moduli dichiarati nel
`FUNCTION_MAP.csv`. Ordine consigliato:
utils -> indicators -> entry -> trigger -> R/R -> sizing -> scoring -> decision ->
portfolio -> market regime -> state/history -> reports.

Per ogni estrazione:
1. implementare nel modulo destinazione;
2. confrontare OLD vs MODULAR sugli stessi input;
3. eseguire unit/parity tests;
4. solo se PASS rendere la funzione modulare ACTIVE;
5. in caso di FAIL mantenere il binding alla baseline.

## Phase C: evoluzioni piattaforma
Solo dopo completa parità:
- eventuale DB unico;
- Signal Log / Trade Journal unificati;
- FAST_MONITOR schedulato;
- WhatsApp;
- backtest/forward test evoluti;
- disattivazione dei vecchi workflow mantenendo rollback.
