from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import yaml

from engine.analyzer import run_full_scan
from monitor.supabase_persistence import persist_scan
from notifications.email_client import send_email
from orchestrator.runtime import RunTracker, record_notification
from state.high_conviction_store import persist_high_conviction


def load_cfg(market):
    root = Path(__file__).resolve().parents[1]
    common = yaml.safe_load((root / "config/common.yaml").read_text()) or {}
    specific = yaml.safe_load((root / f"config/{market.lower()}.yaml").read_text()) or {}
    return {**common, **specific}


def _enrich_presentation_fields(market: str, ref, selected):
    enriched = []
    for original in selected:
        c = dict(original)
        if market == "usa" and ref is not None and hasattr(ref, "prebuy_engine"):
            try:
                c.update(ref.prebuy_engine(c))
            except Exception as exc:
                print(f"WARN prebuy enrichment {c.get('ticker')}: {type(exc).__name__}: {exc}")
        enriched.append(c)
    return enriched


def _failure_run_id(market: str) -> str:
    return datetime.now(timezone.utc).strftime(f"CORE_{market.upper()}_ERROR_%Y%m%dT%H%M%SZ")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--market", choices=["usa", "italy"], required=True)
    p.add_argument("--no-persist", action="store_true")
    a = p.parse_args()

    cfg = load_cfg(a.market)
    engine_id = f"CORE_{a.market.upper()}"

    try:
        result = run_full_scan(cfg, persist=not a.no_persist)
    except Exception as exc:
        if not a.no_persist:
            tracker = RunTracker.start(engine_id, a.market, "CORE", _failure_run_id(a.market))
            tracker.event("SCAN_FAILED", str(exc), severity="ERROR", details={"exception": type(exc).__name__})
            tracker.finish("FAILED", error_message=f"{type(exc).__name__}: {exc}")
        raise

    if result.get("skipped"):
        print(f"SKIP {a.market}: {result.get('skip_reason')} {result.get('session')}")
        return

    run_id = result.get("run_id") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tracker = None if a.no_persist else RunTracker.start(engine_id, a.market, "CORE", run_id)

    try:
        if not a.no_persist:
            persist_scan(result, cfg)

        selected = result["selected"]
        ref = result.get("reference")

        if not a.no_persist:
            hc_selected = _enrich_presentation_fields(a.market, ref, selected)
            hc = persist_high_conviction(
                result.get("run_id"),
                a.market,
                hc_selected,
                reference=ref,
                regime=result.get("regime"),
            )
            print(
                "CORE_HIGH_CONVICTION "
                f"market={a.market.upper()} written={hc.get('written', 0)} "
                f"skipped={hc.get('skipped', False)} reason={hc.get('reason') or 'OK'}"
            )

        print(f"{a.market.upper()} candidates={len(result['candidates'])} selected={len(selected)}")
        for c in selected[:5]:
            print(c.get("ticker"), c.get("decision"), c.get("opportunity_score", c.get("score")), c.get("display_state"))

        if cfg.get("send_email") and ref is not None:
            html = ref.generate_html(selected, result["rejected"], result["regime"], result["removed_fields"], result["dropped"])
            footer = f"""
            <hr style="margin-top:30px;border:0;border-top:1px solid #cccccc;">
            <div style="font-family:Arial,sans-serif;font-size:12px;line-height:1.6;color:#777777;margin-top:12px;">
                <strong>ENGINE SOURCE</strong><br>
                SOURCE: trading-engine-v2<br>
                ENGINE: CORE 3-6M<br>
                MARKET: {a.market.upper()}<br>
                REPO: antoannali-ita/trading-engine-v2<br>
                MODE: CORE PRODUCTION
            </div>
            """
            html += footer
            subject = f"[CORE][{a.market.upper()}] Trading Engine v2 | {len(selected)} selected"
            if cfg.get("dry_run"):
                subject = "[DRY RUN] " + subject
            try:
                send_email(subject, html, is_html=True)
                if not a.no_persist:
                    record_notification(
                        run_id=run_id,
                        event_type="CORE_REPORT",
                        channel="EMAIL",
                        status="SENT",
                        provider="GMAIL",
                        payload={"market": a.market.upper(), "selected": len(selected)},
                    )
            except Exception as exc:
                if not a.no_persist:
                    record_notification(
                        run_id=run_id,
                        event_type="CORE_REPORT",
                        channel="EMAIL",
                        status="FAILED",
                        provider="GMAIL",
                        error_message=f"{type(exc).__name__}: {exc}",
                    )
                raise

        if tracker is not None:
            tracker.finish(
                "SUCCESS",
                records_processed=len(result.get("candidates") or []),
                signals_found=len(selected),
            )
    except Exception as exc:
        if tracker is not None:
            tracker.event("RUN_FAILED", str(exc), severity="ERROR", details={"exception": type(exc).__name__})
            tracker.finish("FAILED", error_message=f"{type(exc).__name__}: {exc}")
        raise


if __name__ == "__main__":
    main()
