MAX_STOP_LOSS = 800        # points
MIN_TAKE_PROFIT = 200     # points
MAX_RISK_PERCENT = 2.0
MIN_REWARD_RATIO = 1.5    # TP / SL
MAX_RSI_BUY = 68
MIN_RSI_SELL = 32


def check_risk(strategy: dict) -> dict:
    """
    Validate strategy parameters against risk rules.
    Returns {"passed": bool, "issues": [str], "warnings": [str]}.
    """
    p = strategy.get("parameters", {})
    issues = []
    warnings = []

    sl = p.get("stop_loss", 0)
    tp = p.get("take_profit", 0)
    risk = p.get("risk_percent", 0)
    fast = p.get("fast_ema", 0)
    slow = p.get("slow_ema", 0)
    rsi_buy = p.get("rsi_buy", 55)
    rsi_sell = p.get("rsi_sell", 45)

    if sl > MAX_STOP_LOSS:
        issues.append(f"Stop loss {sl} pts exceeds max {MAX_STOP_LOSS} pts")

    if tp < MIN_TAKE_PROFIT:
        issues.append(f"Take profit {tp} pts below min {MIN_TAKE_PROFIT} pts")

    if risk > MAX_RISK_PERCENT:
        issues.append(f"Risk {risk}% exceeds max {MAX_RISK_PERCENT}%")

    if sl > 0 and tp / sl < MIN_REWARD_RATIO:
        issues.append(f"Reward/Risk ratio {tp/sl:.2f} below min {MIN_REWARD_RATIO}")

    if fast >= slow:
        issues.append(f"Fast EMA {fast} must be less than Slow EMA {slow}")

    if rsi_buy > MAX_RSI_BUY:
        warnings.append(f"RSI buy level {rsi_buy} is very high (chasing momentum)")

    if rsi_sell < MIN_RSI_SELL:
        warnings.append(f"RSI sell level {rsi_sell} is very low (chasing momentum)")

    if slow - fast < 10:
        warnings.append(f"EMA gap {slow - fast} pts is narrow — may cause whipsaws")

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
    }


def check_strategy_risk(strategy: dict) -> dict:
    """
    Compatibility helper for the final pipeline pack.
    Returns a simple status/message shape while preserving the richer checks.
    """
    result = check_risk(strategy)
    if result["passed"]:
        message = "Risk checks passed"
        if result["warnings"]:
            message = f"Risk checks passed with warnings: {result['warnings'][0]}"
        return {
            "status": "approved",
            "message": message,
            **result,
        }

    return {
        "status": "rejected",
        "message": "; ".join(result["issues"]),
        **result,
    }
