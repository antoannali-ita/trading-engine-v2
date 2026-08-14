def evaluate_trade(entry, exit_price, shares, round_trip_commission=0.0):
    if not entry or not exit_price or shares<=0:return None
    gross=(exit_price-entry)*shares; net=gross-round_trip_commission
    return {'gross_pnl':gross,'net_pnl':net,'return_pct':(net/(entry*shares))*100}
