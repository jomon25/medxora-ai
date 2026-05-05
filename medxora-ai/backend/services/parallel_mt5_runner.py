from concurrent.futures import ProcessPoolExecutor, as_completed

from services.mt5_config_generator import run_backtest

MAX_WORKERS = 3


def run_parallel_backtests(strategy_names: list[str]):
    results = []

    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {
            executor.submit(run_backtest, name): name
            for name in strategy_names
        }

        for future in as_completed(future_map):
            strategy_name = future_map[future]

            try:
                result = future.result()
                results.append(
                    {
                        "strategy_name": strategy_name,
                        "status": "completed",
                        "result": result,
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "strategy_name": strategy_name,
                        "status": "failed",
                        "error": str(exc),
                    }
                )

    return results
