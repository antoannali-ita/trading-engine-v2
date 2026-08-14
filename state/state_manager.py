from __future__ import annotations
import json
from pathlib import Path
class StateManager:
    def __init__(self,path="data/notification_state.json"):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        try: self.state=json.loads(self.path.read_text()) if self.path.exists() else {}
        except Exception: self.state={}
    def changed(self,key,value): return self.state.get(key)!=value
    def set(self,key,value): self.state[key]=value; self.path.write_text(json.dumps(self.state,indent=2,ensure_ascii=False))
