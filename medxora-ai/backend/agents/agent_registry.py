from __future__ import annotations
from pathlib import Path
from agents.base_agent import BaseAgent

CORE_ORDER = [
"mission_planner_agent","data_quality_agent","market_regime_agent","strategy_creator_agent","mql5_code_agent","backtest_agent",
"risk_judge_agent","walk_forward_agent","monte_carlo_agent","evolution_agent","portfolio_allocation_agent","report_explainability_agent"
]

class FnAgent(BaseAgent):
    def __init__(self, metadata, fn):
        super().__init__(metadata); self.fn = fn
    def run(self, payload, context):
        return self.fn(payload, context)

def _simple(metadata_id,name,goal,tools,input_t,output_t,memory,actions,fn):
    return FnAgent({"id":metadata_id,"name":name,"goal":goal,"tools":tools,"input_type":input_t,"output_type":output_t,"memory_scope":memory,"actions":actions}, fn)

def _make_agents():
    agents = {}
    agents["mission_planner_agent"] = _simple("mission_planner_agent","Mission Planner Agent","Parse mission into constraints",["prompt_parser","requirement_extractor"],"mission_text","mission_plan","past missions",["parse","extract_constraints"],lambda p,c:{"symbol":p.get("symbol","EURUSD"),"timeframe":p.get("timeframe","M5"),"strategy_style":"trend+rsi","indicators":["ema","rsi","atr"],"risk_constraints":{},"max_drawdown":p.get("max_drawdown",15),"target_sharpe":p.get("target_sharpe",1.2),"minimum_trades":p.get("min_trades",50),"spread_filter":2.0,"session_filter":"london_newyork","data_source":p.get("data_source","uploaded_tick_data"),"use_walk_forward":p.get("use_walk_forward",True),"use_monte_carlo":True,"use_evolution":p.get("use_evolution",True),"confidence":0.88})
    agents["data_quality_agent"] = _simple("data_quality_agent","Data Quality Agent","Validate dataset quality",["csv_schema_detector","spread_analyzer"],"dataset","data_quality_report","dataset stats",["detect_schema","validate_rows"],lambda p,c:{"rows_loaded":1000,"valid_rows":995,"invalid_rows":5,"missing_values":0,"duplicate_rows":1,"date_range":"2020-01-01..2020-02-01","average_spread":1.2,"max_spread":4.2,"warnings":[],"approved_for_backtest":True,"confidence":0.8})
    agents["market_regime_agent"] = _simple("market_regime_agent","Market Regime Agent","Classify market regime",["volatility_detector","trend_strength_detector"],"ohlcv","market_regime_report","regime history",["classify_regime"],lambda p,c:{"regimes":["trending","low_volatility"],"trend_strength":0.63,"volatility":"moderate","risk_sessions":["rollover"],"confidence":0.77})
    agents["strategy_creator_agent"] = _simple("strategy_creator_agent","Strategy Creator Agent","Build strategy json",["rule_builder","parameter_initializer"],"mission+regime","strategy_json","past rejected strategies",["generate_strategy"],lambda p,c:{"id":f"strat_{c.get('mission_id','001').split('_')[-1]}","name":"EURUSD M5 Adaptive RSI Trend","symbol":"EURUSD","timeframe":"M5","indicators":["EMA(20,50)","RSI(14)","ATR(14)"],"parameters":{"ema_fast":20,"ema_slow":50},"entry_rules":["ema_fast>ema_slow","rsi>55"],"exit_rules":["atr_sl_tp"],"risk_rules":["max_one_trade"],"spread_filter":2.0,"session_filter":"london_newyork","generated_by_agent":"Strategy Creator Agent","confidence":0.84})
    for aid,name in [("mql5_code_agent","MQL5 Code Agent"),("backtest_agent","Backtest Agent"),("risk_judge_agent","Risk Judge Agent"),("walk_forward_agent","Walk-Forward Agent"),("monte_carlo_agent","Monte Carlo Agent"),("evolution_agent","Evolution Agent"),("portfolio_allocation_agent","Portfolio Allocation Agent"),("report_explainability_agent","Report & Explainability Agent")]:
        agents[aid]=_simple(aid,name,name,["toolkit"],"input","output","memory",["run"],lambda p,c:{"result":"ok","confidence":0.75})
    return agents

AGENTS = _make_agents()

def list_all_agents(): return [a.snapshot() for a in AGENTS.values()]
def get_agent(agent_id): return AGENTS.get(agent_id)
def get_core_agents(): return [AGENTS[k].snapshot() for k in CORE_ORDER if k in AGENTS]
def get_strategy_specialists():
    return [{"id":p.stem,"name":p.stem.replace('_',' ').title(),"class":"strategy_specialist"} for p in Path(__file__).parent.glob('*_agent.py') if p.stem not in AGENTS]
def get_agent_status(): return [{"id":a.meta['id'],"name":a.meta['name'],"status":a.status,"current_task":a.current_task,"confidence":a.confidence,"time_used_ms":a.time_used_ms,"cost_used":a.cost_used} for a in AGENTS.values()]
def run_agent(agent_id, payload, context):
    agent = AGENTS.get(agent_id)
    if not agent: raise KeyError(agent_id)
    return agent.execute(context.get('mission_id','manual_mission'), payload or {}, context or {})
