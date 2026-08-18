from __future__ import annotations

import argparse
import os
from pathlib import Path

import yaml

from engine.analyzer import run_full_scan
from notifications.email_client import send_email


def load_cfg(market):
    root = Path(__file__).resolve().parents[1]
    common = yaml.safe_load((root / "config/common.yaml").read_text()) or {}
    specific = yaml.safe_load(
        (root / f"config/{market.lower()}.yaml").read_text()
    ) or {}
    return {**common, **specific}


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--market",
        choices=["usa", "italy"],
        required=True,
    )
    p.add_argument(
        "--no-persist",
        action="store_true",
    )
    a = p.parse_args()

    cfg = load_cfg(a.market)
    result = run_full_scan(
        cfg,
        persist=not a.no_persist,
    )

    if result.get("skipped"):
        print(
            f"SKIP {a.market}: "
            f"{result.get('skip_reason')} "
            f"{result.get('session')}"
        )
        return

    selected = result["selected"]
    ref = result.get("reference")

    print(
        f"{a.market.upper()} "
        f"candidates={len(result['candidates'])} "
        f"selected={len(selected)}"
    )

    for c in selected[:5]:
        print(
            c.get("ticker"),
            c.get("decision"),
            c.get("opportunity_score", c.get("score")),
            c.get("display_state"),
        )

    if cfg.get("send_email") and ref is not None:
        html = ref.generate_html(
            selected,
            result["rejected"],
            result["regime"],
            result["removed_fields"],
            result["dropped"],
        )

        # ------------------------------------------------------------
        # IDENTIFICAZIONE ENGINE / REPOSITORY
        # ------------------------------------------------------------
        footer = f"""
        <hr style="margin-top:30px;border:0;border-top:1px solid #cccccc;">
        <div style="
            font-family:Arial,sans-serif;
            font-size:12px;
            line-height:1.6;
            color:#777777;
            margin-top:12px;
        ">
            <strong>ENGINE SOURCE</strong><br>
            SOURCE: trading-engine-v2<br>
            ENGINE: CORE 3-6M<br>
            MARKET: {a.market.upper()}<br>
            REPO: antoannali-ita/trading-engine-v2<br>
            MODE: CORE PRODUCTION
        </div>
        """

        html += footer

        subject = (
            f"[CORE][{a.market.upper()}] "
            f"Trading Engine v2 | "
            f"{len(selected)} selected"
        )

        if cfg.get("dry_run"):
            subject = "[DRY RUN] " + subject

        send_email(
            subject,
            html,
            is_html=True,
        )


if __name__ == "__main__":
    main()
