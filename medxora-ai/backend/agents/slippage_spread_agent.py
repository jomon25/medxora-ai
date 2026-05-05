"""
Slippage & Spread Agent — models realistic execution costs (spread × trades)
and re-scores strategies based on net-of-cost profitability.
"""


TYPICAL_SPREADS_PIPS = {
    "EURUSD": 0.8,
    "GBPUSD": 1.2,
    "USDJPY": 0.9,
    "AUDUSD": 1.0,
    "USDCAD": 1.3,
    "NZDUSD": 1.5,
    "USDCHF": 1.1,
    "XAUUSD": 25.0,
    "US30":   2.5,
}

SLIPPAGE_BY_TIMEFRAME = {
    "M1":  2.5,
    "M5":  1.8,
    "M15": 1.2,
    "M30": 1.0,
    "H1":  0.8,
    "H4":  0.5,
    "D1":  0.3,
}

PIP_VALUE_USD = {
    "EURUSD": 10.0,
    "GBPUSD": 10.0,
    "USDJPY":  9.0,
    "AUDUSD": 10.0,
    "USDCAD":  7.6,
    "NZDUSD": 10.0,
    "USDCHF":  9.5,
    "XAUUSD":  1.0,
}


def _pip_value(symbol: str) -> float:
    return PIP_VALUE_USD.get(symbol, 10.0)


def _spread_pips(symbol: str) -> float:
    return TYPICAL_SPREADS_PIPS.get(symbol, 1.5)


def _slippage_pips(timeframe: str) -> float:
    return SLIPPAGE_BY_TIMEFRAME.get(timeframe, 1.0)


def run_slippage_spread_agent(strategy: dict, metrics: dict | None = None) -> dict:
    p = strategy.get("parameters", {})
    symbol = strategy.get("symbol", "EURUSD")
    timeframe = strategy.get("timeframe", "M15")

    sl_points = float(p.get("stop_loss", 300) or 300)
    tp_points = float(p.get("take_profit", 600) or 600)
    risk_pct = float(p.get("risk_percent", 1.0) or 1.0)

    total_trades = int((metrics or {}).get("total_trades", 100) or 100)
    gross_profit = float((metrics or {}).get("net_profit", 0) or 0)
    net_profit_raw = float((metrics or {}).get("net_profit", 0) or 0)

    pip_val = _pip_value(symbol)
    spread_pips = _spread_pips(symbol)
    slip_pips = _slippage_pips(timeframe)
    total_execution_cost_pips = spread_pips + slip_pips

    # Cost per trade in USD (assuming standard lot 0.1 for estimation)
    lot_size = 0.1
    cost_per_trade_usd = total_execution_cost_pips * pip_val * lot_size

    # Total execution cost for observed trades
    total_cost_usd = cost_per_trade_usd * total_trades

    # Net profit after costs
    net_after_costs = net_profit_raw - total_cost_usd

    # Cost as % of gross profit
    cost_drag_pct = abs(total_cost_usd / net_profit_raw * 100) if net_profit_raw != 0 else 0

    # Break-even spread: how much spread can the strategy absorb?
    tp_in_pips = tp_points / 10.0
    sl_in_pips = sl_points / 10.0
    breakeven_spread = tp_in_pips * 0.10

    spread_ok = spread_pips <= breakeven_spread
    profitable_after_costs = net_after_costs > 0

    evidence = [
        f"Symbol: {symbol} | Spread: {spread_pips} pips | Slippage: {slip_pips} pips/trade",
        f"Total execution cost: {total_execution_cost_pips:.1f} pips = ${cost_per_trade_usd:.2f}/trade",
        f"Total cost over {total_trades} trades: ${total_cost_usd:.2f}",
        f"Net profit before costs: ${net_profit_raw:.2f} | After costs: ${net_after_costs:.2f}",
        f"Cost drag: {cost_drag_pct:.1f}% of gross profit",
        f"TP {tp_in_pips:.0f} pips vs spread {spread_pips} pips (break-even limit: {breakeven_spread:.1f} pips)",
    ]

    if not profitable_after_costs and net_profit_raw > 0:
        decision, risk_level, review_state = "reject", "high", "Rejected"
        confidence = 0.88
        reason = (
            f"Strategy is NOT profitable after execution costs. "
            f"Gross profit ${net_profit_raw:.0f} → net ${net_after_costs:.0f} after "
            f"${total_cost_usd:.0f} in spread+slippage costs. Increase TP or reduce trade frequency."
        )
    elif cost_drag_pct > 50:
        decision, risk_level, review_state = "needs_evolution", "high", "Needs Evolution"
        confidence = 0.82
        reason = (
            f"Execution costs consume {cost_drag_pct:.0f}% of profit. "
            f"Spread {spread_pips} pips on {symbol} is too large relative to TP {tp_in_pips:.0f} pips. "
            "Increase take-profit target or switch to higher timeframe."
        )
    elif cost_drag_pct > 25 or not spread_ok:
        decision, risk_level, review_state = "needs_retest", "medium", "Needs Retest"
        confidence = 0.70
        reason = (
            f"Moderate cost drag: {cost_drag_pct:.0f}% of profit eaten by spread+slippage. "
            f"Net after costs: ${net_after_costs:.0f}. Acceptable but worth optimizing TP."
        )
    else:
        decision, risk_level, review_state = "approve", "low", "Approved"
        confidence = 0.82
        reason = (
            f"Execution costs are manageable: {cost_drag_pct:.0f}% cost drag, "
            f"${total_cost_usd:.0f} total over {total_trades} trades. "
            f"Strategy remains profitable at ${net_after_costs:.0f} net."
        )

    return {
        "agent": "Slippage & Spread Agent",
        "decision": decision,
        "confidence": confidence,
        "risk_level": risk_level,
        "reason": reason,
        "evidence": evidence,
        "data": {
            "symbol": symbol,
            "timeframe": timeframe,
            "spread_pips": spread_pips,
            "slippage_pips": slip_pips,
            "total_execution_cost_pips": total_execution_cost_pips,
            "cost_per_trade_usd": round(cost_per_trade_usd, 2),
            "total_cost_usd": round(total_cost_usd, 2),
            "net_profit_before_costs": round(net_profit_raw, 2),
            "net_profit_after_costs": round(net_after_costs, 2),
            "cost_drag_pct": round(cost_drag_pct, 1),
            "profitable_after_costs": profitable_after_costs,
            "total_trades": total_trades,
        },
        "review_state": review_state,
    }
