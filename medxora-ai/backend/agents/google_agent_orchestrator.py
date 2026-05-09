from datetime import datetime
from uuid import uuid4

from agents.mongodb_memory_agent import run_mongodb_memory_agent
from agents.google_mission_planner_agent import run_google_mission_planner_agent
from agents.google_risk_judge_agent import run_google_risk_judge_agent
from agents.google_mql5_review_agent import run_google_mql5_review_agent

from database.mongodb import (
    strategies_collection,
    agent_runs_collection,
    agent_memory_collection,
    risk_verdicts_collection,
    mql5_exports_collection,
)


def now_iso():
    return datetime.utcnow().isoformat()


async def save_agent_run(agent_name: str, mission_id: str, input_data: dict, output_data: dict, model: str = "gemini-2.5-flash"):
    run = {
        "run_id": f"run_{uuid4().hex[:12]}",
        "mission_id": mission_id,
        "agent_name": agent_name,
        "input": input_data,
        "output": output_data,
        "status": "completed",
        "model": model,
        "created_at": now_iso(),
    }
    await agent_runs_collection.insert_one(run)
    run.pop("_id", None)
    return run


async def run_google_medxora_mission(
    mission: str,
    symbol: str = "EURUSD",
    timeframe: str = "M5",
    risk_profile: str = "low"
):
    mission_id = f"mission_{uuid4().hex[:12]}"
    timeline = []

    memory_output = await run_mongodb_memory_agent(symbol, timeframe)
    timeline.append("MongoDB Memory Agent retrieved previous strategies and lessons")

    planner_output = await run_google_mission_planner_agent(
        mission=mission,
        symbol=symbol,
        timeframe=timeframe,
        risk_profile=risk_profile,
        memory_context=memory_output
    )
    await save_agent_run(
        "Google Gemini Mission Planner Agent",
        mission_id,
        {"mission": mission, "memory_context": memory_output},
        planner_output
    )
    timeline.append("Google Gemini Mission Planner Agent created structured strategy plan")

    plan = planner_output.get("result", {})
    strategy_id = f"strat_{uuid4().hex[:12]}"

    strategy_doc = {
        "strategy_id": strategy_id,
        "name": plan.get("mission_title", f"{symbol} {timeframe} Gemini Strategy"),
        "symbol": plan.get("symbol", symbol),
        "timeframe": plan.get("timeframe", timeframe),
        "strategy_type": plan.get("strategy_type", "hybrid"),
        "status": "draft",
        "indicators": plan.get("indicators", []),
        "entry_rules": plan.get("entry_rules", []),
        "exit_rules": plan.get("exit_rules", []),
        "risk_rules": plan.get("risk_rules", []),
        "validation_plan": plan.get("validation_plan", []),
        "mql5_design_notes": plan.get("mql5_design_notes", []),
        "agent_source": "Google Gemini Mission Planner Agent",
        "robustness_score": 0,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }

    await strategies_collection.insert_one(strategy_doc.copy())
    timeline.append("Strategy plan saved into MongoDB strategies collection")

    risk_output = await run_google_risk_judge_agent(strategy_doc)
    risk_result = risk_output.get("result", {})

    risk_doc = {
        "risk_verdict_id": f"risk_{uuid4().hex[:12]}",
        "strategy_id": strategy_id,
        "verdict": risk_result.get("verdict", "NEEDS_EVOLUTION"),
        "risk_score": risk_result.get("risk_score", 50),
        "robustness_score": risk_result.get("robustness_score", 50),
        "strengths": risk_result.get("main_strengths", []),
        "risks": risk_result.get("main_risks", []),
        "rejection_reason": risk_result.get("rejection_reason", ""),
        "improvement_plan": risk_result.get("improvement_plan", []),
        "judge_friendly_explanation": risk_result.get("judge_friendly_explanation", ""),
        "created_at": now_iso(),
    }

    await risk_verdicts_collection.insert_one(risk_doc.copy())
    await save_agent_run("Google Gemini Risk Judge Agent", mission_id, {"strategy": strategy_doc}, risk_output)
    timeline.append("Google Gemini Risk Judge Agent saved risk verdict")

    mql5_output = await run_google_mql5_review_agent(strategy_doc)
    mql5_result = mql5_output.get("result", {})

    mql5_doc = {
        "export_id": f"mql5_{uuid4().hex[:12]}",
        "strategy_id": strategy_id,
        "filename": f"{strategy_id}.mq5",
        "code": "// MQL5 Expert Advisor code will be generated from this strategy plan",
        "compile_status": "not_compiled",
        "review": mql5_result,
        "notes": mql5_result.get("mql5_design_checklist", []),
        "created_at": now_iso(),
    }

    await mql5_exports_collection.insert_one(mql5_doc.copy())
    await save_agent_run("Google Gemini MQL5 Review Agent", mission_id, {"strategy": strategy_doc}, mql5_output)
    timeline.append("Google Gemini MQL5 Review Agent saved MQL5 review")

    memory_doc = {
        "memory_id": f"mem_{uuid4().hex[:12]}",
        "memory_type": "google_agent_mission",
        "symbol": symbol,
        "timeframe": timeframe,
        "content": f"Google Gemini mission {mission_id} created strategy {strategy_id} with verdict {risk_doc['verdict']}",
        "tags": ["google-ai", "gemini", "mongodb", "agent-memory", "medxora"],
        "importance": 0.95,
        "created_at": now_iso(),
    }

    await agent_memory_collection.insert_one(memory_doc)
    timeline.append("Final mission memory saved into MongoDB")

    return {
        "success": True,
        "mission_id": mission_id,
        "strategy_id": strategy_id,
        "partner_track": "MongoDB",
        "google_ai": "Gemini",
        "mongodb_saved": True,
        "risk_verdict": risk_doc["verdict"],
        "agent_timeline": timeline,
        "strategy": strategy_doc,
        "risk": risk_doc,
        "mql5_review": mql5_doc
    }
