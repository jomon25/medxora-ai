"""
services/mcp_service.py
MongoDB MCP Integration for MedXora AI.
Stores strategy memory, agent logs, and mission observations.
Falls back to local SQLite when MongoDB is not configured.
"""
import os, json
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from database.tables import MCPEvent, StrategyMemory
from services.logger import log_info, log_warn

_MONGODB_URI = os.getenv("MONGODB_URI", "")


def _get_mongo_collection(collection_name: str):
    """Get MongoDB collection if configured, else return None."""
    if not _MONGODB_URI:
        return None
    try:
        from pymongo import MongoClient
        client = MongoClient(_MONGODB_URI, serverSelectionTimeoutMS=3000)
        db = client["medxora_ai"]
        return db[collection_name]
    except Exception as e:
        log_warn("mcp_service", f"MongoDB unavailable: {e}")
        return None


def save_strategy_memory(db: Session, strategy_data: dict, mission_id: int | None = None) -> dict:
    """Save strategy metrics to memory (MongoDB + local SQLite fallback)."""
    strategy_name = strategy_data.get("strategy_name", "unknown")

    local = StrategyMemory(
        strategy_name=strategy_name,
        pair=strategy_data.get("pair", "EURUSD"),
        timeframe=strategy_data.get("timeframe", "M15"),
        sharpe=strategy_data.get("sharpe"),
        drawdown=strategy_data.get("drawdown"),
        win_rate=strategy_data.get("win_rate"),
        profit_factor=strategy_data.get("profit_factor"),
        risk_status=strategy_data.get("risk_status", "unknown"),
        mql5_exported=str(strategy_data.get("mql5_exported", False)).lower(),
        mission_id=mission_id,
        tags_json=json.dumps(strategy_data.get("tags", [])),
    )
    db.add(local)

    event = MCPEvent(
        mission_id=mission_id, event_type="save_memory",
        payload_json=json.dumps(strategy_data),
        source="local",
    )

    col = _get_mongo_collection("strategy_memory")
    if col:
        try:
            record = {**strategy_data, "created_at": datetime.now(timezone.utc).isoformat(), "mission_id": mission_id}
            result = col.insert_one(record)
            event.source = "mongodb"
            event.response_json = json.dumps({"inserted_id": str(result.inserted_id)})
            log_info("mcp_service", f"Saved strategy '{strategy_name}' to MongoDB")
        except Exception as e:
            event.response_json = json.dumps({"error": str(e)})
            log_warn("mcp_service", f"MongoDB write failed: {e}")
    else:
        event.response_json = json.dumps({"saved": "local_sqlite"})

    db.add(event)
    db.commit()
    return {"status": "saved", "source": event.source, "strategy_name": strategy_name}


def search_strategies(db: Session, query: dict, mission_id: int | None = None) -> list:
    """Search stored strategy memory by criteria."""
    event = MCPEvent(mission_id=mission_id, event_type="search", payload_json=json.dumps(query), source="local")

    col = _get_mongo_collection("strategy_memory")
    if col:
        try:
            mongo_query = {}
            if query.get("pair"): mongo_query["pair"] = query["pair"]
            if query.get("min_sharpe"): mongo_query["sharpe"] = {"$gte": query["min_sharpe"]}
            if query.get("max_drawdown"): mongo_query["drawdown"] = {"$lte": query["max_drawdown"]}
            if query.get("risk_status"): mongo_query["risk_status"] = query["risk_status"]
            results = list(col.find(mongo_query, {"_id": 0}).limit(20))
            event.source = "mongodb"
            event.response_json = json.dumps({"count": len(results)})
            db.add(event); db.commit()
            return results
        except Exception as e:
            log_warn("mcp_service", f"MongoDB search failed: {e}")

    q = db.query(StrategyMemory)
    if query.get("pair"): q = q.filter(StrategyMemory.pair == query["pair"])
    if query.get("min_sharpe"): q = q.filter(StrategyMemory.sharpe >= query["min_sharpe"])
    if query.get("max_drawdown"): q = q.filter(StrategyMemory.drawdown <= query["max_drawdown"])
    if query.get("risk_status"): q = q.filter(StrategyMemory.risk_status == query["risk_status"])
    results = [m.as_dict() for m in q.order_by(StrategyMemory.created_at.desc()).limit(20).all()]
    event.response_json = json.dumps({"count": len(results)})
    db.add(event); db.commit()
    return results


def save_agent_log(db: Session, log_data: dict, mission_id: int | None = None) -> dict:
    """Save agent reasoning log to MCP."""
    event = MCPEvent(
        mission_id=mission_id, event_type="log",
        payload_json=json.dumps(log_data), source="local",
    )
    col = _get_mongo_collection("agent_logs")
    if col:
        try:
            col.insert_one({**log_data, "created_at": datetime.now(timezone.utc).isoformat()})
            event.source = "mongodb"
        except Exception: pass
    db.add(event); db.commit()
    return {"status": "logged", "source": event.source}


def observe_mission(db: Session, mission_id: int, observation: dict) -> dict:
    """Record a mission observation event."""
    event = MCPEvent(
        mission_id=mission_id, event_type="observe",
        payload_json=json.dumps(observation), source="local",
    )
    col = _get_mongo_collection("mission_observations")
    if col:
        try:
            col.insert_one({**observation, "mission_id": mission_id, "created_at": datetime.now(timezone.utc).isoformat()})
            event.source = "mongodb"
        except Exception: pass
    db.add(event); db.commit()
    return {"status": "observed", "source": event.source}


def get_mcp_status() -> dict:
    """Return MCP connection status."""
    mongo_ok = False
    mongo_detail = "MONGODB_URI not configured"
    if _MONGODB_URI:
        col = _get_mongo_collection("strategy_memory")
        if col is not None:
            try:
                col.find_one({})
                mongo_ok = True
                mongo_detail = "MongoDB connected"
            except Exception as e:
                mongo_detail = f"MongoDB error: {e}"
    return {
        "mongodb": {"status": "connected" if mongo_ok else "fallback", "detail": mongo_detail},
        "local_sqlite": {"status": "active", "detail": "Always available as fallback"},
        "active_source": "mongodb" if mongo_ok else "local_sqlite",
    }
