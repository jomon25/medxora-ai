import json

from database.db import SessionLocal
from database.tables import StrategyFilter


def run_pre_backtest_filter(strategy: dict) -> dict:
    params = strategy.get("parameters", {})
    timeframe = strategy.get("timeframe", "M15")
    fast_ema = float(params.get("fast_ema", 0) or 0)
    slow_ema = float(params.get("slow_ema", 0) or 0)
    stop_loss = float(params.get("stop_loss", 0) or 0)
    take_profit = float(params.get("take_profit", 0) or 0)
    risk_percent = float(params.get("risk_percent", 0) or 0)
    rsi_buy = float(params.get("rsi_buy", 0) or 0)
    rsi_sell = float(params.get("rsi_sell", 0) or 0)

    reward_risk = take_profit / stop_loss if stop_loss > 0 else 0
    reasons = []

    if fast_ema >= slow_ema:
        reasons.append("Fast EMA must be below slow EMA")
    if take_profit < stop_loss * 1.5:
        reasons.append("Reward/risk below 1.5")
    if risk_percent > 2:
        reasons.append("Risk percent above 2")
    if stop_loss > 800:
        reasons.append("Stop loss above 800")
    if take_profit > 3000:
        reasons.append("Take profit above 3000")
    if rsi_buy <= 50:
        reasons.append("RSI buy must be above 50")
    if rsi_sell >= 50:
        reasons.append("RSI sell must be below 50")
    if (rsi_buy - rsi_sell) < 8:
        reasons.append("RSI band spread below 8")
    if timeframe == "M1" and stop_loss < 120:
        reasons.append("M1 stop loss too small")
    if reward_risk < 1.5:
        reasons.append("Expected reward/risk below 1.5")

    checks = 10
    score = max(0, round(100 - (len(reasons) / checks) * 100, 2))
    risk_level = _risk_level(score)
    return {
        "approved": not reasons,
        "score": score,
        "reasons": reasons,
        "risk_level": risk_level,
        "stage": "pre",
        "reward_risk": round(reward_risk, 2),
    }


def run_post_backtest_filter(metrics: dict) -> dict:
    net_profit = float(metrics.get("net_profit", 0) or 0)
    profit_factor = float(metrics.get("profit_factor", 0) or 0)
    max_drawdown = float(metrics.get("max_drawdown", 999) or 999)
    total_trades = float(metrics.get("total_trades", 0) or 0)
    win_rate = float(metrics.get("win_rate", 0) or 0)
    sharpe_ratio = float(metrics.get("sharpe_ratio", 0) or 0)

    reasons = []
    if net_profit <= 0:
        reasons.append("Net profit must be positive")
    if profit_factor < 1.3:
        reasons.append("Profit factor below 1.3")
    if max_drawdown > 10:
        reasons.append("Drawdown above 10%")
    if total_trades < 30:
        reasons.append("Total trades below 30")
    if win_rate < 52:
        reasons.append("Win rate below 52%")
    if sharpe_ratio <= 0.5:
        reasons.append("Sharpe ratio must exceed 0.5")

    checks = 6
    score = max(0, round(100 - (len(reasons) / checks) * 100, 2))
    risk_level = _risk_level(score)
    return {
        "approved": not reasons,
        "score": score,
        "reasons": reasons,
        "risk_level": risk_level,
        "stage": "post",
    }


def filter_check(strategy: dict | None = None, metrics: dict | None = None) -> dict:
    if strategy and metrics:
        pre = run_pre_backtest_filter(strategy)
        post = run_post_backtest_filter(metrics)
        approved = pre["approved"] and post["approved"]
        reasons = pre["reasons"] + post["reasons"]
        score = round((pre["score"] + post["score"]) / 2, 2)
        return {
            "approved": approved,
            "score": score,
            "reasons": reasons,
            "risk_level": _risk_level(score),
        }
    if strategy:
        result = run_pre_backtest_filter(strategy)
        return {
            "approved": result["approved"],
            "score": result["score"],
            "reasons": result["reasons"],
            "risk_level": result["risk_level"],
        }
    if metrics:
        result = run_post_backtest_filter(metrics)
        return {
            "approved": result["approved"],
            "score": result["score"],
            "reasons": result["reasons"],
            "risk_level": result["risk_level"],
        }
    return {
        "approved": False,
        "score": 0,
        "reasons": ["No strategy or metrics supplied"],
        "risk_level": "high",
    }


def save_filter_result(strategy_id: int, filter_result: dict, stage: str) -> int:
    db = SessionLocal()
    try:
        row = StrategyFilter(
            strategy_id=strategy_id,
            approved="true" if filter_result.get("approved") else "false",
            score=filter_result.get("score"),
            risk_level=filter_result.get("risk_level"),
            reasons_json=json.dumps(filter_result.get("reasons", [])),
            stage=stage,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def _risk_level(score: float) -> str:
    if score >= 80:
        return "low"
    if score >= 55:
        return "medium"
    return "high"
