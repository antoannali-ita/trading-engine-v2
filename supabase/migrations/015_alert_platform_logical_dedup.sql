-- Alert Platform: collapse operational duplicates by logical condition.
-- Same market+ticker+type+level/range must exist only once while actionable.
-- valid_until is deliberately NOT part of the logical identity.

begin;

-- The previous index treated different expiries as different alerts.
drop index if exists alert_platform.uq_alert_platform_actionable_exact;

-- Keep one operational row per logical alert.
-- Prefer ACTIVE, then the least transitional state, then the furthest expiry,
-- then the most recently updated record.
with ranked as (
    select
        id,
        row_number() over (
            partition by
                market,
                upper(trim(ticker)),
                alert_type,
                threshold,
                threshold_min,
                threshold_max
            order by
                case status::text
                    when 'ACTIVE' then 1
                    when 'CLAIMED' then 2
                    when 'V3_RUNNING' then 3
                    when 'V3_PENDING' then 4
                    when 'V3_RETRY' then 5
                    when 'V3_FAILED' then 6
                    else 99
                end,
                valid_until desc nulls last,
                updated_at desc nulls last,
                created_at desc nulls last,
                id desc
        ) as rn
    from alert_platform.alerts
    where status::text in (
        'ACTIVE', 'CLAIMED', 'V3_RUNNING', 'V3_PENDING', 'V3_RETRY', 'V3_FAILED'
    )
)
delete from alert_platform.alerts a
using ranked r
where a.id = r.id
  and r.rn > 1;

-- Normalize ticker casing/whitespace so future comparisons are deterministic.
update alert_platform.alerts
set ticker = upper(trim(ticker))
where ticker is not null
  and ticker <> upper(trim(ticker));

-- Prevent recurrence. Expiry is metadata of the same logical alert, not identity.
create unique index if not exists uq_alert_platform_actionable_logical
on alert_platform.alerts (
    market,
    ticker,
    alert_type,
    threshold,
    threshold_min,
    threshold_max
) nulls not distinct
where status::text in (
    'ACTIVE', 'CLAIMED', 'V3_RUNNING', 'V3_PENDING', 'V3_RETRY', 'V3_FAILED'
);

comment on index alert_platform.uq_alert_platform_actionable_logical is
'One actionable row per logical alert; valid_until does not create a second operational alert.';

commit;
