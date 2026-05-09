from services.agentic_foundation import add_event

def run(mission_id:str,plan:dict,strategy:dict,metrics:dict,decision:dict,mql5:dict)->str:
    report=f"# Mission {mission_id}\nChampion: {strategy['id']}\nSharpe: {metrics['metrics']['sharpe_ratio']}\nDecision: {decision['approved']}\nMQL5: {mql5['file_path']}"
    add_event(mission_id,"Report Agent","completed","report_generation","Final report generated","success",{"length":len(report)})
    return report
