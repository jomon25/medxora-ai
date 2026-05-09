from services.agentic_foundation import add_event

def run(mission_id:str,metrics:dict,constraints:dict)->dict:
    m=metrics["metrics"]; ok=(m["max_drawdown_pct"]<=constraints.get("max_drawdown",15) and m["sharpe_ratio"]>=constraints.get("target_sharpe",1.2) and m["total_trades"]>=constraints.get("min_trades",50) and m["profit_factor"]>=1.2 and m["robustness_score"]>=70)
    decision={"approved":ok,"reasons":[] if ok else ["Constraints not met"]}
    add_event(mission_id,"Risk Judge Agent","completed","risk_judgement","Approved champion" if ok else "Rejected strategy","decision",decision)
    return decision
