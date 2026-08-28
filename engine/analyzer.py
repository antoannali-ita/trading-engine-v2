from __future__ import annotations
import importlib, os
from typing import Any, Dict, List, Tuple
from engine.models import AnalysisResult
from engine.market_rules import presentation_state, prebuy_enabled
from engine.factor_ranker import rank_candidates
from market.session import status as market_session_status

ENV_MAP = {
    "commission_per_side":"COMMISSION_PER_SIDE", "min_price":"MIN_PRICE",
    "min_market_cap":"MIN_MARKET_CAP", "min_avg_dollar_volume":"MIN_AVG_DOLLAR_VOLUME",
    "min_avg_dollar_volume_soft":"MIN_AVG_DOLLAR_VOLUME_SOFT", "min_score_watch":"MIN_SCORE_WATCH",
    "min_score_buy":"MIN_SCORE_BUY", "min_net_rr_normal":"MIN_NET_RR_NORMAL",
    "min_net_rr_caution":"MIN_NET_RR_CAUTION", "min_net_rr_riskoff":"MIN_NET_RR_RISKOFF",
    "min_net_rr_tp1":"MIN_NET_RR_TP1", "max_limit_distance_pct":"MAX_LIMIT_DISTANCE_PCT",
    "max_limit_distance_atr":"MAX_LIMIT_DISTANCE_ATR", "score_marginal_gap":"SCORE_MARGINAL_GAP",
    "db_path":"__DB_PATH_NOT_ENV__", "snapshot_dir":"__SNAPSHOT_DIR_NOT_ENV__",
}

_DECISION_RANK_COMPAT = {
    "BUY_NOW": 6,
    "BUY_LIMIT": 5,
    "WAIT": 4,
    "WATCH": 3,
    "AVOID": 1,
    "DATA_INSUFFICIENT": 0,
}

def load_reference(cfg: Dict[str, Any]):
    # Set strategy env vars before import because baselines read configuration at module import time.
    for key, env in ENV_MAP.items():
        if env.startswith("__"): continue
        if key in cfg and cfg[key] is not None:
            os.environ[env] = str(cfg[key])
    reference = importlib.import_module(cfg["reference_module"])

    # Compatibility guard for the frozen Italy v1.2 baseline. The ranking helper
    # references DECISION_RANK, but that constant was accidentally omitted when
    # the operational-ranking block was ported from USA. Injecting the identical
    # mapping restores execution without changing thresholds, scores or decisions.
    if cfg.get("reference_module") == "reference.italy_v1_2" and not hasattr(reference, "DECISION_RANK"):
        reference.DECISION_RANK = dict(_DECISION_RANK_COMPAT)

    return reference

def normalize_candidate(reference, market: str, c: Dict[str, Any], cfg: Dict[str, Any] | None = None) -> Dict[str, Any]:
    c=dict(c)
    cfg = cfg or {"market": market, "prebuy_enabled": market.upper() == "USA"}

    # Presentation guardrail for Italy Phase A.
    # The frozen Italy v1.2 baseline can label a candidate BUY_LIMIT when all
    # score/RR/sizing gates pass even though the live price is still ABOVE
    # Max Buy (provided it is within MAX_LIMIT_DISTANCE). That is useful for
    # ranking but too aggressive as a user-facing action: no order should look
    # ready while the engine itself says NON INSEGUIRE / trigger WAITING.
    # Keep the frozen baseline untouched and downgrade only the normalized
    # operational output to APPROACHING until price <= Max Buy.
    if (
        str(market).lower() == "italy"
        and c.get("decision") == "BUY_LIMIT"
        and bool(c.get("above_max_buy"))
    ):
        dist_pct = c.get("distance_to_max_buy_pct")
        c["decision"] = "WATCH"
        c["operational_state"] = "APPROACHING"
        c["limit_ready"] = False
        c["veto_reasons"] = [
            f"NON INSEGUIRE: attendere prezzo <= Max Buy"
            + (f" ({dist_pct:+.1f}%)" if isinstance(dist_pct, (int, float)) else "")
        ]

    # Phase-A boundary guardrail: do not silently add USA PRE-BUY semantics to Italy.
    c["display_state"] = presentation_state(reference, cfg, c)
    if prebuy_enabled(cfg) and hasattr(reference,"prebuy_engine"):
        c.update(reference.prebuy_engine(c))
    return c

def run_full_scan(cfg: Dict[str, Any], persist: bool=True) -> Dict[str, Any]:
    reference=load_reference(cfg)

    # Session gating is mandatory for every market. Previously USA silently bypassed
    # this block because only the Italy reference exposed a session helper.
    s = market_session_status(reference=reference, market=cfg["market"])
    enforce = bool(cfg.get("enforce_market_session", True))
    force = bool(cfg.get("force_run_outside_session", False))
    # Preserve frozen-reference flags when they exist, but never default USA to OPEN.
    enforce = getattr(reference, "ENFORCE_MARKET_SESSION", enforce)
    force = getattr(reference, "FORCE_RUN_OUTSIDE_SESSION", force)
    if enforce and not force and not s.get("market_session_open"):
        return {
            "market": cfg["market"],
            "skipped": True,
            "skip_reason": "market_closed",
            "session": s,
            "selected": [],
            "candidates": [],
        }

    reference.init_db()
    history=reference.history_health()
    previous=set(reference.get_previous_selected_tickers())
    regime=reference.market_regime_engine()
    regime.update(reference.portfolio_heat_engine())
    regime.update(history)
    df, removed=reference.run_tradingview_discovery()
    if df.empty:
        return {"market":cfg["market"],"skipped":False,"regime":regime,"selected":[],"candidates":[],"rejected":[],"removed_fields":removed,"dropped":[],"factor_ranker":{"enabled":bool(cfg.get("factor_ranker_enabled",False)),"pool_size":0,"revision_enriched":0}}

    candidates=reference.build_candidates(df, regime)

    # Factor Ranker is a research pre-selector, not a fourth trading engine.
    # It improves candidate quality using momentum/RS, quality/profitability,
    # growth and estimate revisions. Existing CORE decisions, trade plan, R/R,
    # sizing and vetoes remain authoritative and are not recalculated here.
    factor_result = rank_candidates(candidates, cfg)
    candidates = factor_result["candidates"]
    selection_pool = factor_result["selection_pool"]
    selected, _ = reference.select_ranked(selection_pool)
    rejected = [c for c in candidates if not c.get("passes_survival")]

    actionable=[c for c in selected if c.get("decision") in {"BUY_NOW","BUY_LIMIT"}]
    if len(actionable)>regime["max_new_buys"]:
        allowed={c["ticker"] for c in actionable[:regime["max_new_buys"]]}
        for c in selected:
            if c.get("decision") in {"BUY_NOW","BUY_LIMIT"} and c["ticker"] not in allowed:
                c["decision"]="WAIT"; c.setdefault("veto_reasons",[]).append("Cap nuovi BUY imposto dal Market Regime")
    reference.attach_history_states(candidates)
    selected=[normalize_candidate(reference,cfg["market"],c,cfg) for c in selected]
    current={c["ticker"] for c in selected}; dropped=sorted(previous-current)
    run_id=None; json_path=None
    if persist:
        from datetime import datetime, timezone
        run_id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        json_path=str(reference.save_run(run_id,regime,candidates,selected,removed,dropped))
    return {
        "market":cfg["market"],
        "skipped":False,
        "reference":reference,
        "regime":regime,
        "selected":selected,
        "candidates":candidates,
        "rejected":rejected,
        "removed_fields":removed,
        "dropped":dropped,
        "run_id":run_id,
        "json_path":json_path,
        "factor_ranker":{
            "enabled":factor_result.get("enabled",False),
            "version":factor_result.get("version"),
            "pool_size":factor_result.get("pool_size",len(selection_pool)),
            "eligible_count":factor_result.get("eligible_count"),
            "revision_enriched":factor_result.get("revision_enriched",0),
        },
    }

def analyze_ticker_from_candidate(cfg: Dict[str,Any], candidate: Dict[str,Any]) -> AnalysisResult:
    reference=load_reference(cfg)
    return AnalysisResult.from_candidate(cfg["market"], normalize_candidate(reference,cfg["market"],candidate,cfg))
