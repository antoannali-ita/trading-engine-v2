from __future__ import annotations
import csv
from pathlib import Path

def append_signal(row: dict,path='data/signal_log.csv'):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True); exists=p.exists()
    fields=sorted(row.keys())
    with p.open('a',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields)
        if not exists:w.writeheader()
        w.writerow({k:row.get(k) for k in fields})
