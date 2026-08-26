# System Components Catalogue

**Version:** 1.0 baseline  
**Note:** this catalogue is intentionally maintained at responsibility level; exact functions remain discoverable in source and `FUNCTION_MAP.csv`.

| Area | Component/path | Responsibility |
|---|---|---|
| Baseline | `reference/usa_v5_5.py` | Frozen USA behavioural reference/oracle |
| Baseline | `reference/italy_v1_2.py` | Frozen Italy behavioural reference/oracle |
| Migration | `FUNCTION_MAP.csv` | Maps reference top-level functions to modular destinations |
| CORE | `engine/analyzer.py` | Full-scan orchestration/assembly and market-specific normalisation |
| CORE | `engine/scoring.py` | Score components and quality/opportunity calculations |
| CORE | `engine/entry.py` | Entry geometry / Buy Zone / Max Buy / structural levels |
| CORE | `engine/risk_reward.py` | Gross/net R/R calculations |
| CORE | `engine/sizing.py` | Position sizing/capital/risk calculations |
| CORE | `engine/triggers.py` | Trigger state logic |
| CORE | `engine/prebuy.py` | Pre-buy/readiness logic |
| CORE | `engine/decision.py` | Decision/display-state responsibilities |
| CORE | `engine/value_trap.py` | Value-trap/sector-aware handling |
| CORE | `engine/anomaly.py` | Data/earnings anomaly sanitation |
| CORE | `engine/utils.py` | Shared utility parity functions |
| Market | `market/` | Universe, data-provider, benchmark/regime responsibilities |
| State | `state/` | Database/history/snapshot/change-state responsibilities |
| Portfolio | `portfolio/` | Portfolio context/heat responsibilities |
| Reports | `reports/email_report.py` | Report binding/generation surface |
| Notifications | `notifications/` | Email/WhatsApp delivery clients |
| Monitor | `monitor/master_scan.py` | CLI/production entry point for broad scan |
| Monitor | `monitor/fast_monitor.py` | CLI/production entry point for fast candidate monitoring |
| Config | `config/` | USA/Italy runtime strategy/market configuration |
| Workflows | `.github/workflows/` | Scheduling/manual dispatch, runtime environment and pre-run tests |
| Tests | `tests/` | Integrity, parity, regression, UI/production behaviour checks |
| Laboratory | Laboratory modules/pages | Opportunity/paper/evidence/verdict research surfaces |

## Dependency rule

Production entry points should orchestrate rather than duplicate trading rules. Strategy logic belongs in CORE/reference during migration; notification clients deliver states rather than inventing them; Laboratory observes/tests rather than silently mutating current CORE behaviour.

## Audit rule

When a component is physically extracted from `reference/` into an independent module, update this catalogue, `FUNCTION_MAP.csv`, technical architecture, parity tests and version history together.