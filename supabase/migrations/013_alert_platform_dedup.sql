-- Alert Platform cutover: remove exact actionable duplicates and prevent them recurring.
-- Safe by design: this migration does NOT drop public.trading_alerts yet.
-- The legacy table is retained until the new worker is verified in production.

begin;

-- Keep the most recently updated row for an exact logical duplicate.
-- Use native column types directly: enum -> text casts are not IMMUTABLE and therefore
-- are unsuitable inside PostgreSQL index expressions/predicates.
with ranked as (
    select
        id,
        row_number() over (
            partition by
                market,
                ticker,
                alert_type,
                threshold,
                threshold_min,
                threshold_max,
                valid_until
            order by updated_at desc nulls last, created_at desc nulls last, id desc
        ) as rn
    from alert_platform.alerts
    where status in ('ACTIVE', 'CLAIMED', 'V3_PENDING', 'V3_RETRY')
)
delete from alert_platform.alerts a
using ranked r
where a.id = r.id
  and r.rn > 1;

-- Prevent new exact duplicates among actionable rows.
-- PostgreSQL/Supabase supports NULLS NOT DISTINCT, so NULL threshold/range/date values
-- are treated as equal without COALESCE casts or sentinel values.
create unique index if not exists uq_alert_platform_actionable_exact
on alert_platform.alerts (
    market,
    ticker,
    alert_type,
    threshold,
    threshold_min,
    threshold_max,
    valid_until
) nulls not distinct
where status in ('ACTIVE', 'CLAIMED', 'V3_PENDING', 'V3_RETRY');

comment on index alert_platform.uq_alert_platform_actionable_exact is
'Prevents exact duplicate actionable alerts while preserving distinct conditions/ranges/expiries.';

commit;
