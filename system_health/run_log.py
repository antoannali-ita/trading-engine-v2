from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any


def _env(name: str) -> str:
    return str(os.getenv(name) or "").strip()


def _endpoint(path: str) -> str:
    return f"{_env('SUPABASE_URL').rstrip('/')}/rest/v1/{path}"


def _headers(prefer: str | None = None) -> dict[str, str]:
    key = _env("SUPABASE_SECRET_KEY")
    out = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if prefer:
        out["Prefer"] = prefer
    return out


def _request(method: str, path: str, payload: dict[str, Any] | None = None, prefer: str | None = None) -> None:
    if not _env("SUPABASE_URL") or not _env("SUPABASE_SECRET_KEY"):
        print("RUN_LOG skipped: Supabase credentials unavailable")
        return
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(_endpoint(path), data=body, headers=_headers(prefer), method=method)
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        print(f"RUN_LOG best-effort HTTP {exc.code}: {detail}")
    except Exception as exc:
        print(f"RUN_LOG best-effort error: {type(exc).__name__}: {exc}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _key(args: argparse.Namespace) -> str:
    run_id = args.github_run_id or _env("GITHUB_RUN_ID") or "local"
    attempt = args.github_run_attempt or _env("GITHUB_RUN_ATTEMPT") or "1"
    suffix = args.component or args.market or "main"
    return args.run_key or f"{args.module}:{run_id}:{attempt}:{suffix}"


def start(args: argparse.Namespace) -> None:
    key = _key(args)
    payload = {
        "run_key": key,
        "module": args.module,
        "component": args.component,
        "workflow": args.workflow or _env("GITHUB_WORKFLOW") or None,
        "market": args.market,
        "status": "RUNNING",
        "trigger_source": args.trigger_source or _env("GITHUB_EVENT_NAME") or None,
        "github_run_id": args.github_run_id or _env("GITHUB_RUN_ID") or None,
        "github_run_attempt": args.github_run_attempt or _env("GITHUB_RUN_ATTEMPT") or None,
        "started_at": _now(),
        "message": args.message,
        "metadata": {},
    }
    _request("POST", "system_run_log?on_conflict=run_key", payload, "resolution=merge-duplicates,return=minimal")
    print(f"RUN_LOG START {key}")


def finish(args: argparse.Namespace) -> None:
    key = _key(args)
    mapping = {"SUCCESS": "OK", "OK": "OK", "FAILURE": "ERROR", "ERROR": "ERROR", "CANCELLED": "CANCELLED", "CANCELED": "CANCELLED", "SKIPPED": "SKIPPED"}
    status = mapping.get(str(args.status or "OK").upper(), "ERROR")
    payload = {
        "status": status,
        "finished_at": _now(),
        "processed_count": max(0, args.processed),
        "action_count": max(0, args.actions),
        "sent_count": max(0, args.sent),
        "skipped_count": max(0, args.skipped),
        "error_count": max(0, args.errors if args.errors is not None else (1 if status == "ERROR" else 0)),
        "message": args.message,
    }
    _request("PATCH", f"system_run_log?run_key=eq.{urllib.parse.quote(key, safe='')}", payload, "return=minimal")
    print(f"RUN_LOG FINISH {key} status={status}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("start", "finish"):
        q = sub.add_parser(name)
        q.add_argument("--module", required=True)
        q.add_argument("--component")
        q.add_argument("--workflow")
        q.add_argument("--market")
        q.add_argument("--run-key")
        q.add_argument("--github-run-id")
        q.add_argument("--github-run-attempt")
        q.add_argument("--trigger-source")
        q.add_argument("--message")
        if name == "finish":
            q.add_argument("--status", default="OK")
            q.add_argument("--processed", type=int, default=0)
            q.add_argument("--actions", type=int, default=0)
            q.add_argument("--sent", type=int, default=0)
            q.add_argument("--skipped", type=int, default=0)
            q.add_argument("--errors", type=int)
    return p


def main() -> int:
    args = build_parser().parse_args()
    try:
        start(args) if args.command == "start" else finish(args)
    except Exception as exc:
        print(f"RUN_LOG non-fatal failure: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
