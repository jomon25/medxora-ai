import json

from database.tables import (
    AgentMemory,
    EvolutionLesson,
    FailedStrategyReason,
    StrategyReflection,
)


def _dump(payload):
    return json.dumps(payload) if payload is not None else None


def _load(payload_json):
    if not payload_json:
        return None
    try:
        return json.loads(payload_json)
    except Exception:
        return None


def store_agent_memory(
    db,
    *,
    strategy_name: str | None,
    agent_name: str,
    category: str,
    memory_text: str,
    confidence: float | None = None,
    payload: dict | None = None,
):
    row = AgentMemory(
        strategy_name=strategy_name,
        agent_name=agent_name,
        category=category,
        memory_text=memory_text,
        confidence=confidence,
        payload_json=_dump(payload),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_agent_memory(
    db,
    *,
    agent_name: str | None = None,
    strategy_name: str | None = None,
    category: str | None = None,
    limit: int = 20,
):
    query = db.query(AgentMemory)
    if agent_name:
        query = query.filter(AgentMemory.agent_name == agent_name)
    if strategy_name:
        query = query.filter(AgentMemory.strategy_name == strategy_name)
    if category:
        query = query.filter(AgentMemory.category == category)
    return query.order_by(AgentMemory.created_at.desc()).limit(limit).all()


def recall_similar_memories(
    db,
    *,
    agent_name: str,
    strategy: dict,
    category: str = "decision",
    limit: int = 5,
):
    params = strategy.get("parameters", {})
    fast = float(params.get("fast_ema", 0) or 0)
    slow = float(params.get("slow_ema", 0) or 0)
    risk = float(params.get("risk_percent", 0) or 0)

    candidates = list_agent_memory(
        db,
        agent_name=agent_name,
        category=category,
        limit=max(limit * 8, 20),
    )

    scored = []
    for row in candidates:
        payload = _load(row.payload_json) or {}
        row_strategy = payload.get("strategy") or {}
        row_params = row_strategy.get("parameters") or {}
        if not row_params:
            continue

        row_fast = float(row_params.get("fast_ema", 0) or 0)
        row_slow = float(row_params.get("slow_ema", 0) or 0)
        row_risk = float(row_params.get("risk_percent", 0) or 0)
        distance = (
            abs(fast - row_fast) / 12.0
            + abs(slow - row_slow) / 30.0
            + abs(risk - row_risk) / 0.5
        )

        same_symbol = row_strategy.get("symbol") == strategy.get("symbol")
        same_tf = row_strategy.get("timeframe") == strategy.get("timeframe")
        if same_symbol:
            distance -= 0.2
        if same_tf:
            distance -= 0.2

        scored.append({
            "row": row,
            "payload": payload,
            "distance": round(distance, 4),
        })

    return [
        item
        for item in sorted(scored, key=lambda x: x["distance"])[:limit]
    ]


def store_strategy_reflection(
    db,
    *,
    strategy_name: str,
    reflection_type: str,
    summary: str,
    details: dict | None = None,
):
    row = StrategyReflection(
        strategy_name=strategy_name,
        reflection_type=reflection_type,
        summary=summary,
        details_json=_dump(details),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def store_evolution_lesson(
    db,
    *,
    strategy_name: str,
    parameter: str,
    lesson: str,
    delta: float | None = None,
    parent_score: float | None = None,
    child_score: float | None = None,
):
    row = EvolutionLesson(
        strategy_name=strategy_name,
        parameter=parameter,
        delta=delta,
        parent_score=parent_score,
        child_score=child_score,
        lesson=lesson,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def store_failed_reason(
    db,
    *,
    strategy_name: str,
    stage: str,
    reason: str,
    details: dict | None = None,
):
    row = FailedStrategyReason(
        strategy_name=strategy_name,
        stage=stage,
        reason=reason,
        details_json=_dump(details),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
