-- Dashboard / orchestrator performance indexes and compact operational views.
-- Safe to run after 001_orchestrator_schema.sql. All statements are idempotent.

create index if not exists idx_signals_engine_detected_desc
  on public.signals(engine, detected_at desc);

create index if not exists idx_signals_market_ticker_detected_desc
  on public.signals(market, ticker, detected_at desc);

create index if not exists idx_signals_actionable_detected_desc
  on public.signals(is_actionable, detected_at desc)
  where is_actionable = true;

create index if not exists idx_engine_runs_status_started_desc
  on public.engine_runs(status, started_at desc);

create index if not exists idx_engine_runs_trigger_started_desc
  on public.engine_runs(trigger_source, started_at desc);

create index if not exists idx_ai_analysis_status_completed_desc
  on public.ai_analysis(status, completed_at desc);

create index if not exists idx_ai_analysis_market_ticker_started_desc
  on public.ai_analysis(market, ticker, started_at desc);

create index if not exists idx_manual_run_pending
  on public.manual_run_requests(requested_at)
  where status = 'REQUESTED';

create index if not exists idx_notification_signal_channel_status
  on public.notification_events(signal_id, channel, status);

create index if not exists idx_performance_strategy_outcome_created_desc
  on public.performance(strategy, outcome, created_at desc);

create index if not exists idx_performance_ticker_created_desc
  on public.performance(ticker, created_at desc);

create or replace view public.v_dashboard_latest_confluence as
select distinct on (market, ticker)
  signal_id,
  run_id,
  market,
  ticker,
  signal_type,
  decision,
  conviction,
  is_actionable,
  detected_at,
  metadata
from public.signals
where engine = 'ORCHESTRATOR'
order by market, ticker, detected_at desc;

create or replace view public.v_dashboard_recent_ai as
select
  analysis_id,
  ticker,
  market,
  source_signal_id,
  trigger_reason,
  status,
  alignment,
  confidence,
  verdict,
  summary,
  entry,
  stop,
  tp1,
  tp2,
  started_at,
  completed_at,
  error_message
from public.ai_analysis
where started_at >= now() - interval '30 days';

create or replace view public.v_dashboard_performance_summary as
select
  strategy,
  market,
  outcome,
  count(*) as observations,
  round(avg(pnl_pct), 4) as avg_pnl_pct,
  round((percentile_cont(0.5) within group (order by pnl_pct))::numeric, 4) as median_pnl_pct,
  round(avg(max_drawdown_pct), 4) as avg_drawdown_pct,
  round(avg(max_favorable_excursion_pct), 4) as avg_mfe_pct,
  round((100.0 * avg(case when pnl_pct > 0 then 1 else 0 end))::numeric, 2) as win_rate_pct
from public.performance
where pnl_pct is not null
group by strategy, market, outcome;

comment on view public.v_dashboard_latest_confluence is 'Latest orchestrator confluence per market/ticker for dashboard reads.';
comment on view public.v_dashboard_recent_ai is 'Recent TradingAgents results for dashboard reads.';
comment on view public.v_dashboard_performance_summary is 'Aggregated strategy performance by market and evaluation horizon.';
