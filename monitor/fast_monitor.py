from __future__ import annotations
import argparse, json
from pathlib import Path
import sqlite3, yfinance as yf, yaml
from state.state_manager import StateManager
from notifications.whatsapp_client import send_whatsapp

def load_cfg(market):
    root=Path(__file__).resolve().parents[1]
    return {**(yaml.safe_load((root/'config/common.yaml').read_text()) or {}), **(yaml.safe_load((root/f'config/{market}.yaml').read_text()) or {})}

def latest_selected(db_path):
    p=Path(db_path)
    if not p.exists(): return []
    with sqlite3.connect(p) as con:
        row=con.execute('SELECT run_id FROM runs ORDER BY run_ts DESC LIMIT 1').fetchone()
        if not row:return []
        rows=con.execute('SELECT payload_json FROM candidate_snapshots WHERE run_id=? AND selected=1',(row[0],)).fetchall()
    out=[]
    for (s,) in rows:
        try: out.append(json.loads(s))
        except Exception: pass
    return out

def current_price(ticker,market):
    y=ticker if market=='usa' or '.' in ticker else ticker+'.MI'
    try:
        h=yf.Ticker(y).history(period='1d',interval='5m',auto_adjust=True)
        return None if h.empty else float(h['Close'].dropna().iloc[-1])
    except Exception:return None

def main():
    p=argparse.ArgumentParser();p.add_argument('--market',choices=['usa','italy'],required=True);a=p.parse_args();cfg=load_cfg(a.market)
    sm=StateManager(f"data/fast_state_{a.market}.json")
    for c in latest_selected(cfg['db_path']):
        t=c.get('ticker'); px=current_price(t,a.market)
        if px is None: continue
        low=c.get('buy_zone_low'); high=c.get('buy_zone_high'); maxb=c.get('max_buy'); stop=c.get('stop')
        state='NORMAL'
        if stop and px<=stop: state='STOP'
        elif low and high and low<=px<=high: state='IN_BUY_ZONE'
        elif maxb and px>maxb: state='ABOVE_MAX_BUY'
        key=f"{a.market}:{t}:fast_state"
        if sm.changed(key,state):
            print(t,px,state); sm.set(key,state)
            if cfg.get('send_whatsapp') and state in {'STOP','IN_BUY_ZONE'}:
                send_whatsapp(f"{a.market.upper()} {t}: {state} @ {px:.2f}")
if __name__=='__main__': main()
