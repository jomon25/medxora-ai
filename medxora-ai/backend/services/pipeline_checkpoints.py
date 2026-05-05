import json

from database.tables import PipelineCheckpoint


def record_checkpoint(
    db,
    *,
    strategy_name: str,
    stage: str,
    status: str,
    message: str,
    payload: dict | None = None,
):
    checkpoint = (
        db.query(PipelineCheckpoint)
        .filter(
            PipelineCheckpoint.strategy_name == strategy_name,
            PipelineCheckpoint.stage == stage,
        )
        .first()
    )

    if checkpoint is None:
        checkpoint = PipelineCheckpoint(
            strategy_name=strategy_name,
            stage=stage,
            status=status,
            message=message,
            payload_json=json.dumps(payload) if payload is not None else None,
        )
        db.add(checkpoint)
    else:
        checkpoint.status = status
        checkpoint.message = message
        checkpoint.payload_json = json.dumps(payload) if payload is not None else None

    db.commit()
    db.refresh(checkpoint)
    return checkpoint


def list_checkpoints(db, strategy_name: str):
    return (
        db.query(PipelineCheckpoint)
        .filter(PipelineCheckpoint.strategy_name == strategy_name)
        .order_by(PipelineCheckpoint.created_at.asc(), PipelineCheckpoint.id.asc())
        .all()
    )


def latest_checkpoint(db, strategy_name: str):
    return (
        db.query(PipelineCheckpoint)
        .filter(PipelineCheckpoint.strategy_name == strategy_name)
        .order_by(PipelineCheckpoint.updated_at.desc(), PipelineCheckpoint.id.desc())
        .first()
    )
