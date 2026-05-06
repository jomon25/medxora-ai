import math


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _bull_score(strategy: dict, metrics: dict) -> float:
    """Score from the bull (pro-strategy) perspective."""
    p = strategy.get("parameters", {})
    sl  = float(p.get("stop_loss", 300) or 300)
    tp  = float(p.get("take_profit", 600) or 600)
    fe  = float(p.get("fast_ema", 10) or 10)
    se  = float(p.get("slow_ema", 50) or 50)
    rsi_buy  = float(p.get("rsi_buy", 55) or 55)
    risk_pct = float(p.get("risk_percent", 1.0) or 1.0)

    rr_ratio   = tp / sl if sl > 0 else 1.0          # reward-to-risk
    ema_gap    = (se - fe) / se if se > 0 else 0.0    # relative EMA separation
    rsi_signal = max(0.0, (rsi_buy - 50.0) / 20.0)   # how far above 50

    pf      = float(metrics.get("profit_factor", 1.2) or 1.2)
    sharpe  = float(metrics.get("sharpe_ratio", 0.8) or 0.8)
    wr      = float(metrics.get("win_rate", 55) or 55) / 100.0

    score = (
        min(rr_ratio / 3.0, 1.0)          * 25   # R:R up to 3 = full points
        + min(ema_gap * 3.0, 1.0)          * 20   # clear EMA gap
        + rsi_signal                        * 15   # RSI above neutral
        + min(pf / 2.5, 1.0)               * 20   # profit factor
        + min(sharpe / 2.0, 1.0)           * 10   # Sharpe ratio
        + min(wr / 0.70, 1.0)              * 10   # win rate
    )
    # Penalise high risk percent
    score -= max(0.0, risk_pct - 1.0) * 5
    return round(max(0.0, min(score, 100.0)), 2)


def _bear_score(strategy: dict, metrics: dict) -> float:
    """Score from the bear (critical) perspective."""
    p = strategy.get("parameters", {})
    sl       = float(p.get("stop_loss", 300) or 300)
    tp       = float(p.get("take_profit", 600) or 600)
    fe       = float(p.get("fast_ema", 10) or 10)
    se       = float(p.get("slow_ema", 50) or 50)
    rsi_buy  = float(p.get("rsi_buy", 55) or 55)
    risk_pct = float(p.get("risk_percent", 1.0) or 1.0)

    dd        = float(metrics.get("max_drawdown", 12) or 12)
    wr        = float(metrics.get("win_rate", 55) or 55) / 100.0
    pf        = float(metrics.get("profit_factor", 1.2) or 1.2)

    # Bear scores high when risk is high
    dd_risk      = min(dd / 30.0, 1.0)                        * 30
    rsi_overbuy  = max(0.0, (rsi_buy - 60.0) / 10.0)          * 20
    tight_ema    = max(0.0, 1.0 - (se - fe) / 30.0)           * 20
    low_wr       = max(0.0, 1.0 - wr / 0.60)                  * 15
    low_pf       = max(0.0, 1.0 - pf / 1.8)                   * 10
    high_risk    = min(risk_pct / 2.0, 1.0)                    * 5

    score = dd_risk + rsi_overbuy + tight_ema + low_wr + low_pf + high_risk
    return round(max(0.0, min(score, 100.0)), 2)


# ---------------------------------------------------------------------------
# Argument generators
# ---------------------------------------------------------------------------

def _bull_arguments(strategy: dict, metrics: dict, round_n: int) -> list[str]:
    p = strategy.get("parameters", {})
    sl = float(p.get("stop_loss", 300) or 300)
    tp = float(p.get("take_profit", 600) or 600)
    fe = float(p.get("fast_ema", 10) or 10)
    se = float(p.get("slow_ema", 50) or 50)
    pf = float(metrics.get("profit_factor", 1.2) or 1.2)
    wr = float(metrics.get("win_rate", 55) or 55)
    sharpe = float(metrics.get("sharpe_ratio", 0.8) or 0.8)

    base = [
        f"R:R ratio of {tp/sl:.2f} exceeds the 1.5 minimum threshold, delivering positive expectancy per trade.",
        f"EMA separation of {se - fe:.0f} periods confirms a clean trend-following signal with low whipsaw risk.",
        f"Profit factor of {pf:.2f} demonstrates that gross wins materially outpace gross losses.",
        f"Win rate of {wr:.1f}% is above the 50% breakeven mark, supporting consistent capital growth.",
        f"Sharpe ratio of {sharpe:.2f} indicates acceptable risk-adjusted returns versus a passive benchmark.",
    ]
    escalation = [
        "The EMA crossover system has a multi-decade track record on major pairs like EURUSD.",
        "Trend-following strategies historically recover from drawdowns faster than mean-reversion systems.",
        f"With TP={tp:.0f} pts and SL={sl:.0f} pts, a single winning trade more than offsets two losses.",
    ]
    return base[:2 + round_n] + escalation[:round_n - 1]


def _bear_arguments(strategy: dict, metrics: dict, round_n: int) -> list[str]:
    p = strategy.get("parameters", {})
    sl       = float(p.get("stop_loss", 300) or 300)
    fe       = float(p.get("fast_ema", 10) or 10)
    se       = float(p.get("slow_ema", 50) or 50)
    rsi_buy  = float(p.get("rsi_buy", 55) or 55)
    risk_pct = float(p.get("risk_percent", 1.0) or 1.0)
    dd       = float(metrics.get("max_drawdown", 12) or 12)
    pf       = float(metrics.get("profit_factor", 1.2) or 1.2)

    base = [
        f"Max drawdown of {dd:.1f}% represents a significant capital at-risk event for a live account.",
        f"RSI buy threshold of {rsi_buy:.1f} risks entering already-overbought conditions near exhaustion points.",
        f"EMA gap of only {se - fe:.0f} periods is susceptible to false crossovers during ranging markets.",
        f"Profit factor of {pf:.2f} leaves very little margin before the strategy turns unprofitable.",
        f"Risk percent of {risk_pct:.1f}% can compound drawdowns rapidly during losing streaks.",
    ]
    escalation = [
        f"Stop loss of {sl:.0f} points is tight relative to average daily range — expect frequent stop-outs.",
        "Curve-fitting risk: EMA+RSI parameters optimised on historical data often fail out-of-sample.",
        "Trending environments that suit this strategy represent less than 35% of total market time.",
    ]
    return base[:2 + round_n] + escalation[:round_n - 1]


# ---------------------------------------------------------------------------
# Judge logic
# ---------------------------------------------------------------------------

def _judge_round(bull_pts: float, bear_pts: float, round_n: int) -> dict:
    """Deterministic judge ruling for one debate round."""
    margin   = abs(bull_pts - bear_pts)
    winner   = "Bull" if bull_pts > bear_pts else "Bear" if bear_pts > bull_pts else "Draw"
    strength = "decisive" if margin > 15 else "narrow" if margin < 5 else "clear"
    verdict  = (
        f"Round {round_n} Judge Ruling: {winner} wins by a {strength} margin "
        f"(Bull {bull_pts:.1f} vs Bear {bear_pts:.1f}). "
        f"{'Trend alignment and R:R edge are compelling.' if winner == 'Bull' else 'Risk and overbought signals outweigh the positives.' if winner == 'Bear' else 'Arguments are balanced — round called a draw.'}"
    )
    return {"round": round_n, "bull_score": bull_pts, "bear_score": bear_pts,
            "winner": winner, "verdict": verdict}


# ---------------------------------------------------------------------------
# Main agent
# ---------------------------------------------------------------------------

def run_debate_agent(strategy: dict, metrics: dict | None = None, rounds: int = 3) -> dict:
    if metrics is None:
        metrics = {}

    rounds = max(1, min(rounds, 5))

    bull_wins, bear_wins, draws = 0, 0, 0
    round_transcripts = []
    cumulative_bull, cumulative_bear = 0.0, 0.0

    for r in range(1, rounds + 1):
        # Each round the scoring formula shifts slightly to simulate evolving arguments
        b_raw = _bull_score(strategy, metrics) + (r - 1) * 1.5
        br_raw = _bear_score(strategy, metrics) + (r - 1) * 0.8

        bull_args = _bull_arguments(strategy, metrics, r)
        bear_args = _bear_arguments(strategy, metrics, r)

        ruling = _judge_round(round(b_raw, 2), round(br_raw, 2), r)

        if ruling["winner"] == "Bull":
            bull_wins += 1
        elif ruling["winner"] == "Bear":
            bear_wins += 1
        else:
            draws += 1

        cumulative_bull  += b_raw
        cumulative_bear  += br_raw

        round_transcripts.append({
            "round":      r,
            "bull_args":  bull_args,
            "bear_args":  bear_args,
            "ruling":     ruling,
        })

    # Best-of-N verdict
    if bull_wins > bear_wins:
        final_winner = "Bull"
    elif bear_wins > bull_wins:
        final_winner = "Bear"
    else:
        final_winner = "Draw"

    avg_bull = cumulative_bull / rounds
    avg_bear = cumulative_bear / rounds
    margin   = abs(avg_bull - avg_bear) / 100.0          # normalised 0–1

    if final_winner == "Bull":
        decision     = "approve"
        risk_level   = "low" if margin > 0.15 else "medium"
        review_state = "Approved"
        confidence   = round(min(0.60 + margin * 1.5, 0.95), 3)
        reason = (
            f"Bull Researcher won {bull_wins}/{rounds} rounds. "
            f"Trend alignment, R:R ratio, and profit factor arguments prevailed over bear objections."
        )
    elif final_winner == "Bear":
        decision     = "reject"
        risk_level   = "high" if margin > 0.15 else "medium"
        review_state = "Rejected"
        confidence   = round(min(0.60 + margin * 1.5, 0.95), 3)
        reason = (
            f"Bear Researcher won {bear_wins}/{rounds} rounds. "
            f"Drawdown risk, RSI overbought conditions, and EMA gap concerns outweighed bullish arguments."
        )
    else:
        decision     = "needs_retest"
        risk_level   = "medium"
        review_state = "Needs Retest"
        confidence   = 0.55
        reason = (
            f"Debate ended in a {draws} draw(s) — bull and bear arguments are evenly matched. "
            "Further backtesting data is required to tip the balance."
        )

    evidence = [
        f"Debate ran {rounds} rounds (Bull wins: {bull_wins}, Bear wins: {bear_wins}, Draws: {draws})",
        f"Average Bull score across rounds: {avg_bull:.1f}/100",
        f"Average Bear score across rounds: {avg_bear:.1f}/100",
        f"Margin of victory: {margin*100:.1f}%",
        f"Final verdict: {final_winner} wins the adversarial debate",
    ]

    return {
        "agent":      "Debate Agent",
        "decision":   decision,
        "confidence": confidence,
        "risk_level": risk_level,
        "reason":     reason,
        "evidence":   evidence,
        "data": {
            "rounds":              rounds,
            "bull_wins":           bull_wins,
            "bear_wins":           bear_wins,
            "draws":               draws,
            "final_winner":        final_winner,
            "avg_bull_score":      round(avg_bull, 2),
            "avg_bear_score":      round(avg_bear, 2),
            "margin_of_victory":   round(margin, 4),
            "rounds_detail":       round_transcripts,
        },
        "review_state": review_state,
    }
