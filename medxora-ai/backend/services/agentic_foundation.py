from __future__ import annotations
import json, sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / 'database' / 'strategies.db'
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_demo_db():
    c = conn(); cur = c.cursor()
    cur.executescript('''
CREATE TABLE IF NOT EXISTS missions (id TEXT PRIMARY KEY,user_prompt TEXT,symbol TEXT,timeframe TEXT,status TEXT,current_stage TEXT,progress INTEGER,config_json TEXT,result_json TEXT,created_at TEXT,updated_at TEXT);
CREATE TABLE IF NOT EXISTS agents (id TEXT PRIMARY KEY,name TEXT,role TEXT,status TEXT,current_task TEXT,confidence REAL,last_message TEXT,updated_at TEXT);
CREATE TABLE IF NOT EXISTS strategies (id TEXT PRIMARY KEY,mission_id TEXT,name TEXT,symbol TEXT,timeframe TEXT,status TEXT,strategy_json TEXT,metrics_json TEXT,score REAL,created_at TEXT,updated_at TEXT);
CREATE TABLE IF NOT EXISTS backtests (id TEXT PRIMARY KEY,mission_id TEXT,strategy_id TEXT,status TEXT,symbol TEXT,timeframe TEXT,metrics_json TEXT,trades_json TEXT,equity_curve_json TEXT,drawdown_curve_json TEXT,daily_pnl_json TEXT,monthly_pnl_json TEXT,created_at TEXT,completed_at TEXT);
CREATE TABLE IF NOT EXISTS evolution_runs (id TEXT PRIMARY KEY,mission_id TEXT,parent_strategy_id TEXT,child_strategy_id TEXT,generation INTEGER,mutation_json TEXT,before_metrics_json TEXT,after_metrics_json TEXT,decision TEXT,created_at TEXT);
CREATE TABLE IF NOT EXISTS agent_events (id INTEGER PRIMARY KEY AUTOINCREMENT,mission_id TEXT,agent TEXT,status TEXT,stage TEXT,message TEXT,event_type TEXT,details_json TEXT,timestamp TEXT,agent_id TEXT,agent_name TEXT,confidence REAL DEFAULT 0,time_used_ms INTEGER DEFAULT 0,cost_used REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS mql5_exports (id TEXT PRIMARY KEY,mission_id TEXT,strategy_id TEXT,filename TEXT,file_path TEXT,code_preview TEXT,status TEXT,created_at TEXT);
CREATE TABLE IF NOT EXISTS api_keys (id TEXT PRIMARY KEY,provider TEXT,key_name TEXT,encrypted_value TEXT,is_active INTEGER,created_at TEXT,updated_at TEXT);
CREATE TABLE IF NOT EXISTS strategy_versions (id TEXT PRIMARY KEY,strategy_id TEXT,mission_id TEXT,parent_strategy_id TEXT,version INTEGER,name TEXT,mutation_type TEXT,mutation_summary TEXT,changed_parameters_json TEXT,created_by_agent TEXT,reason_for_change TEXT,metrics_before_json TEXT,metrics_after_json TEXT,decision TEXT,rejection_reason TEXT,is_champion INTEGER DEFAULT 0,created_at TEXT);
CREATE TABLE IF NOT EXISTS human_approvals (id TEXT PRIMARY KEY,mission_id TEXT,strategy_id TEXT,approval_type TEXT,status TEXT,requested_by_agent TEXT,risk_summary_json TEXT,approval_message TEXT,approved_by TEXT,approved_at TEXT,rejected_at TEXT,created_at TEXT);
''')
    c.commit(); c.close()

def now(): return datetime.utcnow().isoformat()

def add_event(mission_id,agent,status,stage,message,event_type='info',details=None,agent_id=None,agent_name=None,confidence=0.0,time_used_ms=0,cost_used=0.0):
    c=conn(); c.execute('INSERT INTO agent_events(mission_id,agent,status,stage,message,event_type,details_json,timestamp,agent_id,agent_name,confidence,time_used_ms,cost_used) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',(mission_id,agent,status,stage,message,event_type,json.dumps(details or {}),now(),agent_id,agent_name or agent,float(confidence or 0),int(time_used_ms or 0),float(cost_used or 0))); c.commit(); c.close()

def get_events(mid):
    c=conn(); r=[dict(x) for x in c.execute('SELECT * FROM agent_events WHERE mission_id=? ORDER BY id',(mid,)).fetchall()]; c.close(); return r

def normalize_id(s): return s.get('id') or s.get('strategy_id') or str(s.get('_id'))
