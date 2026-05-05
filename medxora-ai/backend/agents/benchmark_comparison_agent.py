"""
Benchmark Comparison Agent — compares strategy performance vs Buy-and-Hold
and a moving-average baseline.

Benchmarks:
  1. Buy-and-Hold EURUSD  (~3.5% annual average return, ~12% drawdown)
  2. 50-SMA Crossover EA  (~6% annual, ~8% drawdown, ~52% win rate)
  3. Risk-Free Rate (US T-bill proxy ~5.2% annual)
"""

import math


BENCHMARKS = {
    "buy_and_hold": {
        "label":         "Buy & Hold EURUSD",
        "annual_return":  3.5,
        "max_drawdown":  12.0,
        "win_rate":       0.0,
        "profit_factor":  1.0,
        "sharpe":         0.28,
        "description":   "Simple long position held over the test period",
    },
    "ma_crossover": {
        "label":         "50-SMA Crossover Baseline",
        "annual_return":  6.2,
        "max_drawdown":   8.5,
        "win_rate":      52.0,
        "profit_factor":  1.18,
        "sharpe":         0.55,
        "description":   "50/200 SMA crossover — simplest mechanical system",
    },
    "risk_free": {
        "label":         "US T-Bill (Risk-Free Rate)",
        "annual_return":  5.2,
        "max_drawdown":   0.0,
        "win_rate":     100.0,
        "profit_factor":  9.9,
        "sharpe":         9.9,
        "description":   "US 3-month Treasury Bill rate proxy",
    },
}


def _annual_return(net_profit: float, start_equity: float = 10000.0, years: float = 4.0) -> float:
    if start_equity <= 0 or years <= 0:
        return 0.0
    total_return = net_profit / start_equity
    annualized = ((1 + total_return) ** (1.0 / years) - 1) * 100
    return round(annualized, 2)


def _sharpe_vs_benchmark(strategy_sharpe: float, benchmark_sharpe: float) -> float:
    return round(strategy_sharpe - benchmark_sharpe, 3)


def run_benchmark_comparison_agent(strategy: dict, metrics: dict | None = None) -> dict:
    name = strategy.get("name", "unknown")
    m = metrics or {}

    net_profit = float(m.get("net_profit", 0) or 0)
    max_dd = float(m.get("max_drawdown", 15) or 15)
    win_rate = float(m.get("win_rate", 50) or 50)
    pf = float(m.get("profit_factor", 1.0) or 1.0)
    sharpe = float(m.get("sharpe_ratio", 0.5) or 0.5)

    strat_annual = _annual_return(net_profit)

    comparisons = {}
    beats_count = 0

    for key, bm in BENCHMARKS.items():
        beats_return = strat_annual > bm["annual_return"]
        beats_dd = max_dd < bm["max_drawdown"] if bm["max_drawdown"] > 0 else True
        beats_sharpe = sharpe > bm["sharpe"]
        beats_pf = pf > bm["profit_factor"]
        score = sum([beats_return, beats_dd, beats_sharpe, beats_pf])
        if key != "risk_free":
            beats_count += (1 if score >= 3 else 0)

        comparisons[key] = {
            "label":          bm["label"],
            "strategy_annual": strat_annual,
            "benchmark_annual": bm["annual_return"],
            "beats_return":   beats_return,
            "beats_drawdown": beats_dd,
            "beats_sharpe":   beats_sharpe,
            "beats_pf":       beats_pf,
            "score":          f"{score}/4",
            "sharpe_alpha":   _sharpe_vs_benchmark(sharpe, bm["sharpe"]),
        }

    beats_bnh = comparisons["buy_and_hold"]["score"] >= "3/4"
    beats_ma  = comparisons["ma_crossover"]["score"] >= "3/4"

    evidence = [
        f"Strategy annualised return: {strat_annual:+.1f}% | Sharpe: {sharpe:.2f} | DD: {max_dd:.1f}%",
        f"vs Buy & Hold: annual {strat_annual:+.1f}% vs {BENCHMARKS['buy_and_hold']['annual_return']:+.1f}% — {'BEATS' if comparisons['buy_and_hold']['beats_return'] else 'TRAILS'}",
        f"vs MA Crossover: annual {strat_annual:+.1f}% vs {BENCHMARKS['ma_crossover']['annual_return']:+.1f}% — {'BEATS' if comparisons['ma_crossover']['beats_return'] else 'TRAILS'}",
        f"vs Risk-Free: {strat_annual:+.1f}% vs {BENCHMARKS['risk_free']['annual_return']:+.1f}% — {'BEATS' if comparisons['risk_free']['beats_return'] else 'TRAILS'}",
        f"Strategies beating benchmarks: {beats_count}/2 key benchmarks",
    ]

    if beats_bnh and beats_ma:
        decision, risk_level, review_state = "approve", "low", "Approved"
        confidence = round(0.70 + beats_count * 0.10, 3)
        reason = (
            f"Strategy outperforms both Buy-and-Hold ({strat_annual:+.1f}% vs "
            f"{BENCHMARKS['buy_and_hold']['annual_return']:+.1f}%) and MA Crossover baseline. "
            "Significant alpha generated."
        )
    elif beats_bnh and not beats_ma:
        decision, risk_level, review_state = "needs_retest", "medium", "Needs Retest"
        confidence = 0.65
        reason = (
            f"Strategy beats Buy-and-Hold but trails the MA Crossover baseline "
            f"({strat_annual:+.1f}% vs {BENCHMARKS['ma_crossover']['annual_return']:+.1f}%). "
            "Optimize for better risk-adjusted returns."
        )
    elif not beats_bnh and not beats_ma:
        decision, risk_level, review_state = "needs_evolution", "high", "Needs Evolution"
        confidence = 0.80
        reason = (
            f"Strategy underperforms both benchmarks (annual: {strat_annual:+.1f}%). "
            "Even a simple Buy-and-Hold or MA system would outperform. Evolve significantly."
        )
    else:
        decision, risk_level, review_state = "needs_retest", "medium", "Needs Retest"
        confidence = 0.62
        reason = (
            f"Mixed benchmark results. Annual {strat_annual:+.1f}% shows partial outperformance. "
            "More data needed to confirm edge."
        )

    return {
        "agent": "Benchmark Comparison Agent",
        "decision": decision,
        "confidence": confidence,
        "risk_level": risk_level,
        "reason": reason,
        "evidence": evidence,
        "data": {
            "strategy_annual_return_pct": strat_annual,
            "strategy_sharpe": sharpe,
            "strategy_drawdown": max_dd,
            "comparisons": comparisons,
            "beats_buy_and_hold": beats_bnh,
            "beats_ma_baseline": beats_ma,
            "benchmarks_beaten": beats_count,
        },
        "review_state": review_state,
    }
