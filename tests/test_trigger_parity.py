import ast
from pathlib import Path

def load_function(path,name):
    tree=ast.parse(Path(path).read_text())
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    mod=ast.Module(body=[node],type_ignores=[]); from typing import Dict, Any; ns={'Dict':Dict,'Any':Any}
    exec(compile(mod,str(path),'exec'),ns)
    return ns[name]

def test_trigger_confirmed_positive_candle_volume():
    trigger_engine=load_function('reference/usa_v5_5.py','trigger_engine')
    c={'technical_state':'HEALTHY_PULLBACK','in_buy_zone':True,'price':101,'last_open':100,'prev_close':100.5,'ma20':102,'relative_volume':0.9}
    assert trigger_engine(c)['trigger_state']=='CONFIRMED'

def test_trigger_invalid_downtrend():
    trigger_engine=load_function('reference/usa_v5_5.py','trigger_engine')
    assert trigger_engine({'technical_state':'SEVERE_DOWNTREND'})['trigger_state']=='INVALID'
