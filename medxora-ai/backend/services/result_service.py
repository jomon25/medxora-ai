from database.db import SessionLocal
from database.tables import BacktestResult


def to_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def to_int(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return default


def save_backtest_result(strategy_id: int, metrics: dict):
    db = SessionLocal()
    try:
        result = BacktestResult(
            strategy_id=strategy_id,
            net_profit=to_float(metrics.get("net_profit")),
            gross_profit=to_float(metrics.get("gross_profit"), None),
            gross_loss=to_float(metrics.get("gross_loss"), None),
            max_drawdown=to_float(metrics.get("max_drawdown")),
            total_trades=to_int(metrics.get("total_trades")),
            win_rate=to_float(metrics.get("win_rate")),
            profit_factor=to_float(metrics.get("profit_factor")),
            expected_payoff=to_float(metrics.get("expected_payoff"), None),
            sharpe_ratio=to_float(metrics.get("sharpe_ratio"), None),
            recovery_factor=to_float(metrics.get("recovery_factor"), None),
            monthly_profit=to_float(metrics.get("monthly_profit"), None),
            yearly_profit=to_float(metrics.get("yearly_profit"), None),
            report_file=metrics.get("report_file", ""),
            status=metrics.get("status", "completed"),
        )

        db.add(result)
        db.commit()
        db.refresh(result)
        return result.id
    finally:
        db.close()
