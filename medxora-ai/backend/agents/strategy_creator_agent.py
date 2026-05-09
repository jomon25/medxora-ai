from services.agentic_foundation import add_event

def run(mission_id:str,plan:dict)->dict:
    s={"id":f"strat_{mission_id.split('_')[-1]}","name":"EURUSD M5 RSI Trend","symbol":plan["symbol"],"timeframe":plan["timeframe"],"status":"candidate","params":{"ema_fast":20,"ema_slow":50,"rsi":14,"atr_sl":1.5,"atr_tp":2.0}}
    add_event(mission_id,"Strategy Creator Agent","completed","strategy_generation","Strategy JSON generated","success",s)
    return s
