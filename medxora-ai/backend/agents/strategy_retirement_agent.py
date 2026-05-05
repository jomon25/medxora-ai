"""
Strategy Retirement Agent — automatically archives strategies whose live
performance diverges from backtest expectations.

Checks: live vs backtest profit, drawdown expansion, and stagnation.
"""

from datetime import datetime, timezone


RETIREMENT_RULES = {
    "profit_divergence":   {"threshold": 0.50, "label": "Live profit < 50% of backtest expectation"},
    "drawdown_expansion":  {"threshold": 1.50, "label": "Live drawdown > 150% of backtest drawdown"},
    "win_rate_drop":       {"threshold": 0.80, "label": "Live win rate < 80% of backtest win rate"},
    "profit_factor_drop":  {"threshold": 0.75, "label": "Live profit factor < 75% of backtest PF"},
    "stagnation":          {"threshold": 30,   "label": "No meaningful profit in last 30+ trades"},
}


def _check_divergence(backtest: dict, live: dict) -> list[dict]:
    issues = []

    bt_profit = float(backtest.get("net_profit", 0) or 0)
    lv_profit = float(live.get("net_profit", 0) or 0)
    if bt_profit > 0 and lv_profit < bt_profit * RETIREMENT_RULES["profit_divergence"]["threshold"]:
        issues.append({
            "rule": "profit_divergence",
            "label": RETIREMENT_RULES["profit_divergence"]["label"],
            "backtest_value": bt_profit,
            "live_value": lv_profit,
            "ratio": round(lv_profit / bt_profit, 3) if bt_profit else 0,
        })

    bt_dd = float(backtest.get("max_drawdown", 0) or 0)
    lv_dd = float(live.get("max_drawdown", 0) or 0)
    if bt_dd > 0 and lv_dd > bt_dd * RETIREMENT_RULES["drawdown_expansion"]["threshold"]:
        issues.append({
            "rule": "drawdown_expansion",
            "label": RETIREMENT_RULES["drawdown_expansion"]["label"],
            "backtest_value": bt_dd,
            "live_value": lv_dd,
            "ratio": round(lv_dd / bt_dd, 3),
        })

    bt_wr = float(backtest.get("win_rate", 0) or 0)
    lv_wr = float(live.get("win_rate", 0) or 0)
    if bt_wr > 0 and lv_wr < bt_wr * RETIREMENT_RULES["win_rate_drop"]["threshold"]:
        issues.append({
            "rule": "win_rate_drop",
            "label": RETIREMENT_RULES["win_rate_drop"]["label"],
            "backtest_value": bt_wr,
            "live_value": lv_wr,
            "ratio": round(lv_wr / bt_wr, 3),
        })

    bt_pf = float(backtest.get("profit_factor", 0) or 0)
    lv_pf = float(live.get("profit_factor", 0) or 0)
    if bt_pf > 0 and lv_pf < bt_pf * RETIREMENT_RULES["profit_factor_drop"]["threshold"]:
        issues.append({
            "rule": "profit_factor_drop",
            "label": RETIREMENT_RULES["profit_factor_drop"]["label"],
            "backtest_value": bt_pf,
            "live_value": lv_pf,
            "ratio": round(lv_pf / bt_pf, 3),
        })

    lv_trades = int(live.get("total_trades", 0) or 0)
    if lv_trades >= RETIREMENT_RULES["stagnation"]["threshold"] and lv_profit <= 0:
        issues.append({
            "rule": "stagnation",
            "label": RETIREMENT_RULES["stagnation"]["label"],
            "backtest_value": bt_profit,
            "live_value": lv_profit,
            "trades_with_no_profit": lv_trades,
        })

    return issues


def run_strategy_retirement_agent(
    strategy: dict,
    backtest_metrics: dict | None = None,
    live_metrics: dict | None = None,
) -> dict:
    name = strategy.get("name", "unknown")
    generation = strategy.get("generation", 0)

    if not backtest_metrics and not live_metrics:
        backtest_metrics = {}
        live_metrics = {}

    bt = backtest_metrics or {}
    lv = live_metrics or bt

    issues = _check_divergence(bt, lv)
    n_issues = len(issues)

    age_generations = generation
    evidence = [
        f"Strategy: {name} | Generation: {generation}",
        f"Backtest profit: ${float(bt.get('net_profit', 0)):.0f} | Live: ${float(lv.get('net_profit', 0)):.0f}",
        f"Backtest drawdown: {float(bt.get('max_drawdown', 0)):.1f}% | Live: {float(lv.get('max_drawdown', 0)):.1f}%",
        f"Retirement rules triggered: {n_issues}/{len(RETIREMENT_RULES)}",
    ]
    for issue in issues:
        evidence.append(f"  FAIL: {issue['label']} (ratio: {issue.get('ratio', 'n/a')})")

    if n_issues >= 3:
        decision, risk_level, review_state = "reject", "high", "Rejected"
        confidence = round(0.75 + n_issues * 0.05, 3)
        reason = (
            f"Strategy '{name}' should be RETIRED. {n_issues} retirement rules triggered. "
            "Live performance has significantly diverged from backtest. Archive and evolve a replacement."
        )
        recommendation = "retire"
    elif n_issues == 2:
        decision, risk_level, review_state = "needs_evolution", "high", "Needs Evolution"
        confidence = 0.78
        reason = (
            f"{n_issues} divergence rules triggered for '{name}'. "
            "Strong warning: evolve this strategy before live capital allocation."
        )
        recommendation = "evolve_urgently"
    elif n_issues == 1:
        decision, risk_level, review_state = "needs_retest", "medium", "Needs Retest"
        confidence = 0.68
        reason = (
            f"Minor divergence detected for '{name}': {issues[0]['label']}. "
            "Retest with fresh data before continuing."
        )
        recommendation = "retest"
    else:
        decision, risk_level, review_state = "approve", "low", "Approved"
        confidence = 0.80
        reason = (
            f"Strategy '{name}' shows no retirement flags. "
            "Live performance aligns with backtest expectations."
        )
        recommendation = "continue"

    return {
        "agent": "Strategy Retirement Agent",
        "decision": decision,
        "confidence": confidence,
        "risk_level": risk_level,
        "reason": reason,
        "evidence": evidence,
        "data": {
            "strategy_name": name,
            "generation": generation,
            "retirement_issues": issues,
            "n_issues_triggered": n_issues,
            "recommendation": recommendation,
            "should_retire": n_issues >= 3,
        },
        "review_state": review_state,
    }
