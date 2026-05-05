from database.db import SessionLocal
from database.tables import Strategy


def save_strategy_to_db(
    strategy: dict,
    mql5_file: str | None = None,
    parent_id: int | None = None,
    generation: int | None = None,
) -> int:
    db = SessionLocal()
    try:
        params = strategy.get("parameters", {})
        row = Strategy(
            name=strategy["name"],
            symbol=strategy.get("symbol", "EURUSD"),
            timeframe=strategy.get("timeframe", "M15"),
            type=strategy.get("strategy_type", strategy.get("type", "ema_rsi")),
            fast_ema=params.get("fast_ema"),
            slow_ema=params.get("slow_ema"),
            rsi_period=params.get("rsi_period"),
            rsi_buy=params.get("rsi_buy", 55),
            rsi_sell=params.get("rsi_sell", 45),
            stop_loss=params.get("stop_loss"),
            take_profit=params.get("take_profit"),
            risk_percent=params.get("risk_percent", 1.0),
            mql5_file=mql5_file,
            parent_id=parent_id,
            generation=generation if generation is not None else strategy.get("generation", 0),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def update_strategy_mql5_file(strategy_id: int, mql5_file: str) -> None:
    db = SessionLocal()
    try:
        row = db.query(Strategy).filter(Strategy.id == strategy_id).first()
        if row is None:
            return
        row.mql5_file = mql5_file
        db.commit()
    finally:
        db.close()
