-- Alert Platform cutover: remove exact active duplicates and prevent them recurring.
-- Safe by design: this migration does NOT drop public.trading_alerts yet.
-- The legacy table is retained until the new worker is verified in production.

begin;

-- Keep the most recently updated row for an exact logical duplicate.
-- Cast enum-backed fields to text before COALESCE/UPPER.
with ranked as (
    select
        id,
        row_number() over (
            partition by
                upper(coalesce(market::text, '')),
                upper(coalesce(ticker::text, '')),
                upper(coalesce(alert_type::text, '')),
                threshold,
                threshold_min,
                threshold_max,
                valid_until
            order by updated_at desc nulls last, created_at desc nulls last, id desc
        ) as rn
    from alert_platform.alerts
    where upper(coalesce(status::text, '')) in ('ACTIVE', 'CLAIMED', 'V3_PENDING', 'V3_RETRY')
)
delete from alert_platform.alerts a
using ranked r
where a.id = r.id
  and r.rn > 1;

-- Prevent new exact duplicates among actionable rows.
-- COALESCE sentinels are outside valid price ranges and only normalize NULLs.
create unique index if not exists uq_alert_platform_actionable_exact
on alert_platform.alerts (
    upper(coalesce(market::text, '')),
    upper(coalesce(ticker::text, '')),
    upper(coalesce(alert_type::text, '')),
    coalesce(threshold, -999999999::numeric),
    coalesce(threshold_min, -999999999::numeric),
    coalesce(threshold_max, -999999999::numeric),
    coalesce(valid_until, 'infinity'::timestamptz)
)
where upper(coalesce(status::text, '')) in ('ACTIVE', 'CLAIMED', 'V3_PENDING', 'V3_RETRY');

comment on index alert_platform.uq_alert_platform_actionable_exact is
'Prevents exact duplicate actionable alerts while preserving distinct conditions/ranges/expiries.';

commit;
