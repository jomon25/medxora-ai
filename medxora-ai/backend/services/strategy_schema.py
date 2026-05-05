strategy = {
    "name": "EMA_RSI_Strategy",
    "symbol": "EURUSD",
    "timeframe": "M15",
    "type": "trend_following",
    "parameters": {
        "fast_ema": 20,
        "slow_ema": 50,
        "rsi_period": 14,
        "rsi_buy": 55,
        "rsi_sell": 45,
        "stop_loss": 300,
        "take_profit": 600,
        "risk_percent": 1.0
    }
}