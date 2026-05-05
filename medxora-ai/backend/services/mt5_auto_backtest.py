from services.mt5_config_generator import run_backtest


def run_mt5_backtest(strategy_name: str) -> dict:
    """
    Compatibility wrapper for older service naming.
    """
    return run_backtest(strategy_name)
