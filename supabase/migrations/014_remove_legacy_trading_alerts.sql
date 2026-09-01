-- Final alert cutover cleanup.
-- alert_platform.alerts is now the single operational source of truth.
-- This migration archives the legacy public.trading_alerts rows, then removes the live legacy table.

begin;

-- Preserve the legacy rows for audit/recovery without keeping a second live alert source.
create table if not exists public.trading_alerts_legacy_archive
as table public.trading_alerts with no data;

insert into public.trading_alerts_legacy_archive
select legacy.*
from public.trading_alerts legacy
where not exists (
    select 1
    from public.trading_alerts_legacy_archive archived
    where archived.alert_id = legacy.alert_id
);

comment on table public.trading_alerts_legacy_archive is
'Archived snapshot of the retired public.trading_alerts Alert Center table. Read-only historical data; not an operational alert source.';

-- The application and worker now use alert_platform.alerts only.
drop table public.trading_alerts;

commit;
