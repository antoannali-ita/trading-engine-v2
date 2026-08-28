create table if not exists public.trading_alerts (
  alert_id uuid primary key default gen_random_uuid(),
  ticker text not null,
  market text not null default 'USA',
  condition_type text not null,
  trigger_level numeric not null,
  status text not null default 'ACTIVE',
  source text not null default 'MANUAL',
  note text,
  expires_at timestamptz,
  repeatable boolean not null default false,
  dedup_minutes integer not null default 180,
  tolerance_pct numeric not null default 0.0025,
  last_price numeric,
  last_checked_at timestamptz,
  triggered_at timestamptz,
  last_notification_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb,
  constraint trading_alert_condition_chk check (condition_type in ('PRICE_ABOVE','PRICE_BELOW')),
  constraint trading_alert_status_chk check (status in ('ACTIVE','TRIGGERED','EXPIRED','DISABLED','ERROR')),
  constraint trading_alert_source_chk check (source in ('MANUAL','CHAT','PORTFOLIO','ENGINE','FINECO')),
  constraint trading_alert_market_chk check (market in ('USA','ITALY','GLOBAL')),
  constraint trading_alert_dedup_chk check (dedup_minutes between 0 and 1440),
  constraint trading_alert_tolerance_chk check (tolerance_pct between 0 and 0.10)
);

drop trigger if exists trg_trading_alerts_updated_at on public.trading_alerts;
create trigger trg_trading_alerts_updated_at before update on public.trading_alerts
for each row execute function public.set_updated_at();

create index if not exists idx_trading_alerts_active
  on public.trading_alerts(status, expires_at, ticker);
create index if not exists idx_trading_alerts_ticker
  on public.trading_alerts(ticker, created_at desc);

comment on table public.trading_alerts is
  'Independent Alert Center price rules. Notification channel is WhatsApp only.';
comment on column public.trading_alerts.dedup_minutes is
  'Suppresses an equivalent WhatsApp already accepted recently, including Fineco-origin events.';
