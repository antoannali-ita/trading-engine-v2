import ast, json, sys
from pathlib import Path
DEST={
'compute_rsi':'engine/indicators.py','compute_atr':'engine/indicators.py','pct_return':'engine/indicators.py','classify_technical_state':'engine/indicators.py','classify_rs':'engine/indicators.py',
'build_entry_plan':'engine/entry.py','trigger_engine':'engine/triggers.py','compute_gross_rr':'engine/risk_reward.py','compute_net_rr':'engine/risk_reward.py','max_shares_by_cap':'engine/sizing.py','position_sizing':'engine/sizing.py',
'value_trap_engine':'engine/value_trap.py','resolve_next_earnings_date':'engine/anomaly.py','detect_corporate_action_inconsistency':'engine/anomaly.py','data_anomaly_engine':'engine/anomaly.py','data_quality_engine':'engine/data_quality.py',
'market_regime_engine':'market/regime.py','fetch_market_hist':'market/regime.py','parse_portfolio_positions':'portfolio/portfolio.py','get_portfolio_sectors':'portfolio/portfolio.py','portfolio_fit_score':'portfolio/portfolio.py','portfolio_heat_engine':'portfolio/heat.py',
'decision_engine':'engine/decision.py','gate_status':'engine/decision.py','operational_state':'engine/decision.py','display_state':'engine/decision.py','prebuy_engine':'engine/prebuy.py','operational_rank_key':'engine/ranking.py','select_ranked':'engine/ranking.py',
'history_health':'state/history.py','get_previous_snapshot':'state/history.py','get_previous_selected_tickers':'state/history.py','init_db':'state/database.py','change_state':'state/change_engine.py','attach_history_states':'state/change_engine.py','json_safe':'state/snapshots.py','save_run':'state/snapshots.py',
'run_tradingview_discovery':'market/universe.py','run_single_tv_lens':'market/universe.py','build_discovery_where':'market/universe.py','passes_survival':'market/universe.py','is_otc_like':'market/universe.py','is_gem_foreign_listing':'market/universe.py','build_universe_exclusion_candidate':'market/universe.py','build_candidate':'market/universe.py','build_candidates':'market/universe.py','get_yfinance_details':'market/data_provider.py',
'generate_html':'reports/email_report.py','build_action_board':'reports/email_report.py','action_needed_text':'reports/email_report.py','tv_chart_url':'reports/email_report.py',
}
for fn in sys.argv[1:]:
 p=Path(fn); tree=ast.parse(p.read_text()); names=[n.name for n in tree.body if isinstance(n,ast.FunctionDef)]
 print(json.dumps([{'function':n,'destination':DEST.get(n,'UNMAPPED')} for n in names],indent=2))
