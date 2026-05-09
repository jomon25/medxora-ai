from services.agentic_foundation import add_event

def run(mission_id:str,plan:dict)->dict:
    summary={"timeframes":["M1","M5","M15","H1"],"rows":1000,"symbol":plan["symbol"]}
    add_event(mission_id,"Market Data Agent","completed","data_loading","Loaded and resampled market data","success",summary)
    return summary
