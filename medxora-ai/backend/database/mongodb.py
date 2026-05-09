import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "medxora_ai")

if not MONGODB_URI:
    print("WARNING: MONGODB_URI is not configured")
    client = None
    db = None
else:
    client = AsyncIOMotorClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    db = client[MONGODB_DB_NAME]

if db is not None:
    strategies_collection = db["strategies"]
    backtests_collection = db["backtests"]
    agent_runs_collection = db["agent_runs"]
    agent_memory_collection = db["agent_memory"]
    mql5_exports_collection = db["mql5_exports"]
    risk_verdicts_collection = db["risk_verdicts"]
    strategy_evolution_collection = db["strategy_evolution"]
else:
    strategies_collection = None
    backtests_collection = None
    agent_runs_collection = None
    agent_memory_collection = None
    mql5_exports_collection = None
    risk_verdicts_collection = None
    strategy_evolution_collection = None


async def init_mongodb_indexes():
    if db is None:
        print("MongoDB not configured. Skipping index creation.")
        return False

    try:
        await strategies_collection.create_index([("strategy_id", ASCENDING)], unique=True)
        await strategies_collection.create_index([("created_at", DESCENDING)])
        await strategies_collection.create_index([("symbol", ASCENDING), ("timeframe", ASCENDING)])

        await backtests_collection.create_index([("strategy_id", ASCENDING)])
        await backtests_collection.create_index([("created_at", DESCENDING)])

        await agent_runs_collection.create_index([("run_id", ASCENDING)], unique=True)
        await agent_runs_collection.create_index([("created_at", DESCENDING)])
        await agent_runs_collection.create_index([("agent_name", ASCENDING)])

        await agent_memory_collection.create_index([("memory_id", ASCENDING)], unique=True)
        await agent_memory_collection.create_index([("created_at", DESCENDING)])
        await agent_memory_collection.create_index([("symbol", ASCENDING), ("timeframe", ASCENDING)])

        await mql5_exports_collection.create_index([("strategy_id", ASCENDING)])
        await mql5_exports_collection.create_index([("created_at", DESCENDING)])

        await risk_verdicts_collection.create_index([("strategy_id", ASCENDING)])
        await risk_verdicts_collection.create_index([("created_at", DESCENDING)])

        await strategy_evolution_collection.create_index([("parent_strategy_id", ASCENDING)])
        await strategy_evolution_collection.create_index([("child_strategy_id", ASCENDING)])

        print("MongoDB indexes initialized")
        return True

    except Exception as e:
        print(f"MongoDB index initialization failed, but app will continue: {e}")
        return False
