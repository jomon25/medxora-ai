from database.mongodb import (
    agent_memory_collection,
    strategies_collection,
    risk_verdicts_collection,
    backtests_collection,
)


async def run_mongodb_memory_agent(symbol: str = "EURUSD", timeframe: str = "M5"):
    memories = await agent_memory_collection.find(
        {"symbol": symbol, "timeframe": timeframe},
        {"_id": 0}
    ).sort("created_at", -1).limit(5).to_list(length=5)

    strategies = await strategies_collection.find(
        {"symbol": symbol, "timeframe": timeframe},
        {"_id": 0}
    ).sort("created_at", -1).limit(5).to_list(length=5)

    risk_verdicts = await risk_verdicts_collection.find(
        {},
        {"_id": 0}
    ).sort("created_at", -1).limit(5).to_list(length=5)

    backtests = await backtests_collection.find(
        {"symbol": symbol, "timeframe": timeframe},
        {"_id": 0}
    ).sort("created_at", -1).limit(5).to_list(length=5)

    return {
        "agent": "MongoDB Memory Agent",
        "symbol": symbol,
        "timeframe": timeframe,
        "memories_found": len(memories),
        "strategies_found": len(strategies),
        "risk_verdicts_found": len(risk_verdicts),
        "backtests_found": len(backtests),
        "memories": memories,
        "strategies": strategies,
        "risk_verdicts": risk_verdicts,
        "backtests": backtests,
        "recommendation": "Use MongoDB memory to avoid repeated failed strategy patterns and reuse successful strategy lessons."
    }
