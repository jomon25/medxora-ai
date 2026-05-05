import json

from database.tables import (
    AgentMemory,
    EvolutionLesson,
    FailedStrategyReason,
    StrategyReflection,
)


def _dump(payload):
    return json.dumps(payload) if payload is not None else None


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
