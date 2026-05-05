import numpy as np
import pandas as pd


def calculate_returns(equity_curve: list[float]):
    series = pd.Series(equity_curve)
    return series.pct_change().dropna()


def correlation_matrix(strategy_equity_curves: dict):
    returns = {}

    for name, curve in strategy_equity_curves.items():
        returns[name] = calculate_returns(curve)

    df = pd.DataFrame(returns).dropna()
    return df.corr()


def portfolio_score(strategy):
    profit = float(strategy.get("net_profit", 0))
    drawdown = float(strategy.get("max_drawdown", 100))
    sharpe = float(strategy.get("sharpe_ratio", 0))
    win_rate = float(strategy.get("win_rate", 0))

    return (
        profit * 0.40
        + sharpe * 300
        + win_rate * 5
        - drawdown * 20
    )


def optimize_portfolio(strategies: list[dict], max_count=5, max_correlation=0.65):
    sorted_strategies = sorted(
        strategies,
        key=portfolio_score,
        reverse=True,
    )

    selected = []

    for strategy in sorted_strategies:
        if len(selected) >= max_count:
            break

        if not selected:
            selected.append(strategy)
            continue

        allowed = True

        for existing in selected:
            corr = strategy.get("correlations", {}).get(existing["name"], 0)

            if abs(corr) > max_correlation:
                allowed = False
                break

        if allowed:
            selected.append(strategy)

    total_profit = sum(float(s.get("net_profit", 0)) for s in selected)
    avg_drawdown = np.mean([float(s.get("max_drawdown", 0)) for s in selected]) if selected else 0
    avg_sharpe = np.mean([float(s.get("sharpe_ratio", 0)) for s in selected]) if selected else 0

    return {
        "selected_strategies": selected,
        "portfolio_metrics": {
            "total_profit": total_profit,
            "average_drawdown": round(float(avg_drawdown), 2),
            "average_sharpe": round(float(avg_sharpe), 2),
            "strategy_count": len(selected),
        },
    }
