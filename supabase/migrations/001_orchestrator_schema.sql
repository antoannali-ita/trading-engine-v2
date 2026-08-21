create extension if not exists pgcrypto;

create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.engine_registry (
  engine_id text primary key,
  repository text not null,
  workflow_file text,
  strategy text not null,
  market text not null,
  horizon text,
  enabled boolean not null default true,
  schedule_type text not null default 'GITHUB_ACTIONS',
  schedule_expression text,
  expected_interval_minutes integer,
  last_run_at timestamptz,
  next_expected_run_at timestamptz,
  status text not null default 'UNKNOWN',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint engine_registry_market_chk check (market in ('USA','ITALY','GLOBAL')),
  constraint engine_registry_status_chk check (status in ('UNKNOWN','HEALTHY','RUNNING','DEGRADED','FAILED','DISABLED'))
);

drop trigger if exists trg_engine_registry_updated_at on public.engine_registry;
create trigger trg_engine_registry_updated_at before update on public.engine_registry
for each row execute function public.set_updated_at();

create table if not exists public.engine_runs (
  run_id text primary key,
  run_timestamp timestamptz not null default now(),
  market text,
  horizon text,
  engine_version text,
  config_version text,
  universe_size integer,
  candidates_count integer,
  notes text
);

alter table public.engine_runs add column if not exists engine_id text;
alter table public.engine_runs add column if not exists strategy text;
alter table public.engine_runs add column if not exists trigger_source text not null default 'SCHEDULE';
alter table public.engine_runs add column if not exists requested_by text;
alter table public.engine_runs add column if not exists started_at timestamptz;
alter table public.engine_runs add column if not exists finished_at timestamptz;
alter table public.engine_runs add column if not exists status text not null default 'SUCCESS';
alter table public.engine_runs add column if not exists duration_seconds numeric(12,3);
alter table public.engine_runs add column if not exists records_processed integer;
alter table public.engine_runs add column if not exists signals_found integer;
alter table public.engine_runs add column if not exists error_message text;
alter table public.engine_runs add column if not exists github_run_id bigint;
alter table public.engine_runs add column if not exists metadata jsonb not null default '{}'::jsonb;
alter table public.engine_runs add column if not exists created_at timestamptz not null default now();
alter table public.engine_runs add column if not exists updated_at timestamptz not null default now();

drop trigger if exists trg_engine_runs_updated_at on public.engine_runs;
create trigger trg_engine_runs_updated_at before update on public.engine_runs
for each row execute function public.set_updated_at();

create index if not exists idx_engine_runs_engine_started on public.engine_runs(engine_id, started_at desc);
create index if not exists idx_engine_runs_market_started on public.engine_runs(market, started_at desc);
create index if not exists idx_engine_runs_status on public.engine_runs(status);

create table if not exists public.signals (
  signal_id text primary key,
  run_id text,
  market text,
  ticker text not null,
  horizon text,
  price numeric,
  status text,
  decision text,
  setup text,
  trigger text,
  score_total numeric,
  entry numeric,
  buy_range_low numeric,
  buy_range_high numeric,
  max_buy numeric,
  stop numeric,
  tp1 numeric,
  tp2 numeric,
  rr_net_tp1 numeric,
  rr_net_tp2 numeric,
  qty integer,
  capital numeric,
  loss_max numeric,
  sma20 numeric,
  sma50 numeric,
  sma200 numeric,
  rsi14 numeric,
  atr14 numeric,
  relative_volume numeric,
  earnings_date date,
  days_to_earnings integer,
  data_quality text,
  reason text,
  raw_data jsonb
);

alter table public.signals add column if not exists engine_id text;
alter table public.signals add column if not exists engine text not null default 'CORE';
alter table public.signals add column if not exists strategy text;
alter table public.signals add column if not exists signal_type text;
alter table public.signals add column if not exists conviction numeric;
alter table public.signals add column if not exists is_actionable boolean not null default false;
alter table public.signals add column if not exists detected_at timestamptz not null default now();
alter table public.signals add column if not exists expires_at timestamptz;
alter table public.signals add column if not exists source_signal_id text;
alter table public.signals add column if not exists metadata jsonb not null default '{}'::jsonb;
alter table public.signals add column if not exists created_at timestamptz not null default now();
alter table public.signals add column if not exists updated_at timestamptz not null default now();

drop trigger if exists trg_signals_updated_at on public.signals;
create trigger trg_signals_updated_at before update on public.signals
for each row execute function public.set_updated_at();

create index if not exists idx_signals_ticker_detected on public.signals(ticker, detected_at desc);
create index if not exists idx_signals_market_engine_detected on public.signals(market, engine, detected_at desc);
create index if not exists idx_signals_run on public.signals(run_id);
create index if not exists idx_signals_actionable on public.signals(is_actionable, detected_at desc);

create table if not exists public.ai_analysis (
  analysis_id uuid primary key default gen_random_uuid(),
  ticker text not null,
  market text,
  source_signal_id text,
  source_run_id text,
  trigger_reason text,
  provider text,
  model text,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  status text not null default 'PENDING',
  verdict text,
  confidence numeric(5,2),
  alignment text,
  summary text,
  risks jsonb not null default '[]'::jsonb,
  catalysts jsonb not null default '[]'::jsonb,
  entry numeric,
  stop numeric,
  tp1 numeric,
  tp2 numeric,
  raw_payload jsonb not null default '{}'::jsonb,
  error_message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint ai_analysis_status_chk check (status in ('PENDING','RUNNING','SUCCESS','FAILED','SKIPPED')),
  constraint ai_analysis_alignment_chk check (alignment is null or alignment in ('CONFIRM','NEUTRAL','CAUTION','VETO'))
);

drop trigger if exists trg_ai_analysis_updated_at on public.ai_analysis;
create trigger trg_ai_analysis_updated_at before update on public.ai_analysis
for each row execute function public.set_updated_at();

create index if not exists idx_ai_analysis_ticker_completed on public.ai_analysis(ticker, completed_at desc);
create index if not exists idx_ai_analysis_source_signal on public.ai_analysis(source_signal_id);

create table if not exists public.notification_events (
  notification_id uuid primary key default gen_random_uuid(),
  run_id text,
  signal_id text,
  ticker text,
  event_type text not null,
  channel text not null,
  attempted_at timestamptz not null default now(),
  sent_at timestamptz,
  status text not null default 'PENDING',
  provider text,
  destination_masked text,
  provider_message_id text,
  error_message text,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint notification_channel_chk check (channel in ('EMAIL','WHATSAPP','WEBHOOK','OTHER')),
  constraint notification_status_chk check (status in ('PENDING','SENT','FAILED','SKIPPED'))
);

create index if not exists idx_notification_run on public.notification_events(run_id, attempted_at desc);
create index if not exists idx_notification_ticker on public.notification_events(ticker, attempted_at desc);
create index if not exists idx_notification_status on public.notification_events(status, attempted_at desc);

create table if not exists public.manual_run_requests (
  request_id uuid primary key default gen_random_uuid(),
  engine_id text not null,
  market text not null,
  strategy text,
  requested_at timestamptz not null default now(),
  requested_by text,
  send_email boolean not null default true,
  send_whatsapp boolean not null default false,
  status text not null default 'REQUESTED',
  github_run_id bigint,
  run_id text,
  dispatched_at timestamptz,
  started_at timestamptz,
  completed_at timestamptz,
  error_message text,
  request_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint manual_run_market_chk check (market in ('USA','ITALY','GLOBAL')),
  constraint manual_run_status_chk check (status in ('REQUESTED','DISPATCHED','RUNNING','SUCCESS','FAILED','CANCELLED'))
);

drop trigger if exists trg_manual_run_requests_updated_at on public.manual_run_requests;
create trigger trg_manual_run_requests_updated_at before update on public.manual_run_requests
for each row execute function public.set_updated_at();

create index if not exists idx_manual_run_status_requested on public.manual_run_requests(status, requested_at);
create index if not exists idx_manual_run_engine_requested on public.manual_run_requests(engine_id, requested_at desc);

create table if not exists public.system_events (
  event_id uuid primary key default gen_random_uuid(),
  engine_id text,
  run_id text,
  severity text not null default 'INFO',
  event_type text not null,
  message text not null,
  details jsonb not null default '{}'::jsonb,
  occurred_at timestamptz not null default now(),
  constraint system_events_severity_chk check (severity in ('DEBUG','INFO','WARNING','ERROR','CRITICAL'))
);

create index if not exists idx_system_events_occurred on public.system_events(occurred_at desc);
create index if not exists idx_system_events_engine on public.system_events(engine_id, occurred_at desc);
create index if not exists idx_system_events_severity on public.system_events(severity, occurred_at desc);

create table if not exists public.performance (
  performance_id uuid primary key default gen_random_uuid(),
  engine_id text not null,
  strategy text,
  market text,
  ticker text,
  signal_id text,
  period_start timestamptz,
  period_end timestamptz,
  outcome text,
  entry_price numeric,
  exit_price numeric,
  pnl_amount numeric,
  pnl_pct numeric,
  max_drawdown_pct numeric,
  max_favorable_excursion_pct numeric,
  holding_minutes integer,
  metrics jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_performance_engine_period on public.performance(engine_id, period_end desc);
create index if not exists idx_performance_signal on public.performance(signal_id);

insert into public.engine_registry (
  engine_id, repository, workflow_file, strategy, market, horizon, enabled,
  schedule_type, expected_interval_minutes, status
)
values
  ('CORE_USA', 'antoannali-ita/trading-engine-v2', 'master_scan.yml', 'CORE', 'USA', '3-6M', true, 'GITHUB_ACTIONS', null, 'UNKNOWN'),
  ('CORE_ITALY', 'antoannali-ita/trading-engine-v2', 'master_scan.yml', 'CORE', 'ITALY', '3-6M', true, 'GITHUB_ACTIONS', null, 'UNKNOWN'),
  ('FAST_USA', 'antoannali-ita/trading-engine-v2', 'fast_monitor.yml', 'FAST', 'USA', 'INTRADAY', true, 'GITHUB_ACTIONS', null, 'UNKNOWN'),
  ('FAST_ITALY', 'antoannali-ita/trading-engine-v2', 'fast_monitor.yml', 'FAST', 'ITALY', 'INTRADAY', true, 'GITHUB_ACTIONS', null, 'UNKNOWN')
on conflict (engine_id) do update set
  repository = excluded.repository,
  workflow_file = excluded.workflow_file,
  strategy = excluded.strategy,
  market = excluded.market,
  horizon = excluded.horizon,
  updated_at = now();

create or replace view public.v_engine_health as
select
  er.engine_id,
  er.repository,
  er.strategy,
  er.market,
  er.horizon,
  er.enabled,
  er.expected_interval_minutes,
  er.last_run_at,
  er.next_expected_run_at,
  er.status as registry_status,
  lr.run_id as last_run_id,
  lr.started_at as last_started_at,
  lr.finished_at as last_finished_at,
  lr.status as last_run_status,
  lr.duration_seconds,
  lr.signals_found,
  case
    when not er.enabled then 'DISABLED'
    when lr.run_id is null then 'UNKNOWN'
    when lr.status = 'RUNNING' then 'RUNNING'
    when lr.status = 'FAILED' then 'FAILED'
    when er.expected_interval_minutes is not null
         and coalesce(lr.finished_at, lr.started_at, lr.run_timestamp)
             < now() - make_interval(mins => er.expected_interval_minutes * 2)
      then 'STALE'
    else 'HEALTHY'
  end as computed_health
from public.engine_registry er
left join lateral (
  select r.*
  from public.engine_runs r
  where r.engine_id = er.engine_id
  order by coalesce(r.started_at, r.run_timestamp, r.created_at) desc
  limit 1
) lr on true;

alter table public.engine_registry enable row level security;
alter table public.engine_runs enable row level security;
alter table public.signals enable row level security;
alter table public.ai_analysis enable row level security;
alter table public.notification_events enable row level security;
alter table public.manual_run_requests enable row level security;
alter table public.system_events enable row level security;
alter table public.performance enable row level security;

-- No anon/authenticated policies here intentionally. Use the service role only
-- from server-side code. Never expose SUPABASE_SECRET_KEY in browser JavaScript.

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'fk_engine_runs_engine') then
    alter table public.engine_runs
      add constraint fk_engine_runs_engine foreign key (engine_id)
      references public.engine_registry(engine_id)
      on update cascade on delete set null not valid;
  end if;

  if not exists (select 1 from pg_constraint where conname = 'fk_signals_run') then
    alter table public.signals
      add constraint fk_signals_run foreign key (run_id)
      references public.engine_runs(run_id)
      on update cascade on delete set null not valid;
  end if;
end
$$;
