from services.agentic_foundation import add_event

def run(mission_id:str,payload:dict)->dict:
    plan={"symbol":payload.get("symbol","EURUSD"),"timeframe":payload.get("timeframe","M5"),"style":"trend+rsi","constraints":{"max_drawdown":payload.get("max_drawdown",15),"target_sharpe":payload.get("target_sharpe",1.2),"min_trades":payload.get("min_trades",50)}}
    add_event(mission_id,"Mission Planner Agent","completed","mission_planning","Mission plan extracted","success",plan)
    return plan
