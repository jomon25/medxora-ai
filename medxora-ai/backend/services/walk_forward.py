from datetime import datetime

from dateutil.relativedelta import relativedelta


def generate_walk_forward_windows(
    start_date: str,
    end_date: str,
    train_months: int = 24,
    test_months: int = 6,
):
    start = datetime.strptime(start_date, "%Y.%m.%d")
    end = datetime.strptime(end_date, "%Y.%m.%d")

    windows = []
    current = start

    while True:
        train_start = current
        train_end = train_start + relativedelta(months=train_months)
        test_start = train_end
        test_end = test_start + relativedelta(months=test_months)

        if test_end > end:
            break

        windows.append(
            {
                "train_start": train_start.strftime("%Y.%m.%d"),
                "train_end": train_end.strftime("%Y.%m.%d"),
                "test_start": test_start.strftime("%Y.%m.%d"),
                "test_end": test_end.strftime("%Y.%m.%d"),
            }
        )

        current = current + relativedelta(months=test_months)

    return windows


def walk_forward_score(results: list[dict]):
    if not results:
        return {
            "status": "failed",
            "score": 0,
            "reason": "No walk-forward results",
        }

    profitable_windows = 0
    total_profit = 0
    max_drawdowns = []
    profit_factors = []

    for result in results:
        profit = float(result.get("net_profit", 0))
        drawdown = float(result.get("max_drawdown", 0))
        profit_factor = float(result.get("profit_factor", 0))

        if profit > 0:
            profitable_windows += 1

        total_profit += profit
        max_drawdowns.append(drawdown)
        profit_factors.append(profit_factor)

    consistency = profitable_windows / len(results)
    avg_drawdown = sum(max_drawdowns) / len(max_drawdowns)
    avg_pf = sum(profit_factors) / len(profit_factors)

    score = (
        total_profit * 0.30
        + consistency * 1000
        + avg_pf * 200
        - avg_drawdown * 20
    )

    return {
        "status": "success",
        "score": round(score, 2),
        "total_profit": round(total_profit, 2),
        "consistency": round(consistency * 100, 2),
        "average_drawdown": round(avg_drawdown, 2),
        "average_profit_factor": round(avg_pf, 2),
        "windows": len(results),
    }
