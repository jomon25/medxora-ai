import random


def _simulate_curve(win_rate: float, avg_win: float, avg_loss: float, n: int, start: float, rng: random.Random) -> list[float]:
    equity = start
    curve = [equity]
    for _ in range(n):
        equity += avg_win if rng.random() < win_rate else -avg_loss
        equity = max(equity, 0.0)
        curve.append(equity)
        if equity <= 0:
            break
    return curve


def _max_drawdown(curve: list[float]) -> float:
    peak, max_dd = curve[0], 0.0
    for v in curve:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return max_dd


def run_monte_carlo_agent(strategy: dict, metrics: dict | None = None, n_simulations: int = 1000) -> dict:
    p = strategy.get("parameters", {})
    sl = float(p.get("stop_loss", 300) or 300)
    tp = float(p.get("take_profit", 600) or 600)
    risk_pct = float(p.get("risk_percent", 1.0) or 1.0)

    if metrics:
        win_rate    = float(metrics.get("win_rate", 55) or 55) / 100
        max_dd_hist = float(metrics.get("max_drawdown", 12) or 12)
        pf          = float(metrics.get("profit_factor", 1.2) or 1.2)
        n_trades    = int(metrics.get("total_trades", 100) or 100)
    else:
        win_rate    = min(0.40 + (tp / (tp + sl)) * 0.30, 0.72)
        max_dd_hist = 12.0
        pf          = (tp / sl) * (win_rate / (1 - win_rate)) if win_rate < 1 else 2.0
        n_trades    = 100

    start_equity = 10_000.0
    avg_win  = start_equity * (risk_pct / 100.0) * (tp / 200.0)
    avg_loss = start_equity * (risk_pct / 100.0) * (sl / 200.0)

    rng = random.Random(hash(strategy["name"]) & 0xFFFFFF)
    ruin_threshold = start_equity * 0.50

    final_equities, drawdowns, ruin_count = [], [], 0

    for _ in range(n_simulations):
        curve = _simulate_curve(win_rate, avg_win, avg_loss, n_trades, start_equity, rng)
        final_equities.append(curve[-1])
        drawdowns.append(_max_drawdown(curve))
        if curve[-1] < ruin_threshold:
            ruin_count += 1

    ruin_prob = ruin_count / n_simulations
    avg_final = sum(final_equities) / n_simulations
    avg_dd    = sum(drawdowns) / n_simulations

    sorted_eq = sorted(final_equities)
    sorted_dd = sorted(drawdowns)
    p10 = sorted_eq[int(0.10 * n_simulations)]
    p25 = sorted_eq[int(0.25 * n_simulations)]
    p75 = sorted_eq[int(0.75 * n_simulations)]
    p90 = sorted_eq[int(0.90 * n_simulations)]
    worst_dd_p95 = sorted_dd[int(0.95 * n_simulations)]

    expected_return_pct = (avg_final - start_equity) / start_equity * 100.0

    evidence = [
        f"Simulations run: {n_simulations}",
        f"Ruin probability (<50% equity): {ruin_prob*100:.1f}%",
        f"Expected return: {expected_return_pct:.1f}%",
        f"Average max drawdown: {avg_dd*100:.1f}%",
        f"95th-pct worst-case drawdown: {worst_dd_p95*100:.1f}%",
        f"Equity range — P10: ${p10:.0f} | P25: ${p25:.0f} | P75: ${p75:.0f} | P90: ${p90:.0f}",
    ]

    if ruin_prob < 0.05 and worst_dd_p95 < 0.25 and expected_return_pct > 5:
        decision, risk_level, review_state = "approve", "low", "Approved"
        confidence = round(0.85 - ruin_prob * 2, 3)
        reason = f"Monte Carlo shows robust profile. Ruin probability {ruin_prob*100:.1f}%, expected return {expected_return_pct:.1f}%."
    elif ruin_prob > 0.20 or worst_dd_p95 > 0.40:
        decision, risk_level, review_state = "reject", "high", "Rejected"
        confidence = round(min(0.80 + ruin_prob * 0.5, 0.96), 3)
        reason = f"High tail risk detected. Ruin probability {ruin_prob*100:.1f}%, worst-case drawdown {worst_dd_p95*100:.1f}%."
    elif ruin_prob > 0.10 or worst_dd_p95 > 0.25:
        decision, risk_level, review_state = "needs_evolution", "medium", "Needs Evolution"
        confidence = 0.73
        reason = f"Moderate tail risk (ruin {ruin_prob*100:.1f}%). Parameter evolution may reduce downside."
    else:
        decision, risk_level, review_state = "needs_retest", "medium", "Needs Retest"
        confidence = 0.68
        reason = "Borderline Monte Carlo metrics — additional testing recommended before deployment."

    return {
        "agent": "Monte Carlo Agent",
        "decision": decision,
        "confidence": confidence,
        "risk_level": risk_level,
        "reason": reason,
        "evidence": evidence,
        "data": {
            "n_simulations": n_simulations,
            "ruin_probability": round(ruin_prob, 4),
            "expected_return_pct": round(expected_return_pct, 2),
            "avg_max_drawdown_pct": round(avg_dd * 100, 2),
            "worst_drawdown_p95_pct": round(worst_dd_p95 * 100, 2),
            "equity_percentiles": {"p10": round(p10, 2), "p25": round(p25, 2), "p75": round(p75, 2), "p90": round(p90, 2)},
            "win_rate_used": round(win_rate, 4),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
        },
        "review_state": review_state,
    }
