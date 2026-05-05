import random
import uuid
from services.timeframes import normalize_timeframe

STRATEGY_TYPES = [
    "ema_rsi",
    "breakout",
    "bollinger_mean_reversion",
    "macd_crossover",
    "supertrend",
    "adx_trend_filter",
    "donchian_breakout",
    "multi_tf_ema_rsi",
    "news_avoidance",
    # New strategy types (v2)
    "ichimoku",
    "stochastic_rsi",
    "vwap_deviation",
    "pivot_points",
    "grid_trading",
]

STRATEGY_PREFIXES = {
    "ema_rsi":                 "EMA_RSI",
    "breakout":                "BRKOUT",
    "bollinger_mean_reversion":"BB_REV",
    "macd_crossover":          "MACD_X",
    "supertrend":              "SUPERT",
    "adx_trend_filter":        "ADX_TF",
    "donchian_breakout":       "DONCH",
    "multi_tf_ema_rsi":        "MTF_EMA",
    "news_avoidance":          "NEWS_AV",
    # New
    "ichimoku":                "ICHI",
    "stochastic_rsi":          "SRSI",
    "vwap_deviation":          "VWAP",
    "pivot_points":            "PIVOT",
    "grid_trading":            "GRID",
}


def _ema_rsi_params():
    fast = random.randint(10, 30)
    slow = random.randint(fast + 15, fast + 70)
    return {
        "fast_ema":    fast,
        "slow_ema":    slow,
        "rsi_period":  14,
        "rsi_buy":     random.randint(52, 60),
        "rsi_sell":    random.randint(40, 48),
        "stop_loss":   random.randint(200, 500),
        "take_profit": random.randint(400, 1000),
        "risk_percent": 1.0,
    }


def _breakout_params():
    return {
        "breakout_period":  random.randint(10, 30),
        "atr_period":       14,
        "atr_multiplier":   round(random.uniform(1.5, 3.0), 1),
        "volume_filter":    random.choice([True, False]),
        "stop_loss":        random.randint(200, 600),
        "take_profit":      random.randint(400, 1200),
        "risk_percent":     1.0,
    }


def _bollinger_params():
    return {
        "bb_period":       random.randint(14, 25),
        "bb_deviation":    round(random.uniform(1.5, 2.5), 1),
        "rsi_period":      14,
        "rsi_oversold":    random.randint(25, 35),
        "rsi_overbought":  random.randint(65, 75),
        "stop_loss":       random.randint(150, 400),
        "take_profit":     random.randint(300, 800),
        "risk_percent":    1.0,
    }


def _macd_params():
    fast = random.randint(8, 14)
    slow = random.randint(fast + 10, fast + 20)
    signal = random.randint(7, 11)
    return {
        "macd_fast":    fast,
        "macd_slow":    slow,
        "macd_signal":  signal,
        "rsi_period":   14,
        "rsi_filter":   random.randint(45, 55),
        "stop_loss":    random.randint(200, 500),
        "take_profit":  random.randint(400, 1000),
        "risk_percent": 1.0,
    }


def _supertrend_params():
    return {
        "atr_period":     random.randint(7, 14),
        "atr_multiplier": round(random.uniform(2.0, 4.0), 1),
        "ema_filter":     random.randint(100, 200),
        "stop_loss":      random.randint(200, 600),
        "take_profit":    random.randint(400, 1200),
        "risk_percent":   1.0,
    }


def _adx_params():
    fast = random.randint(8, 20)
    slow = random.randint(fast + 10, fast + 50)
    return {
        "adx_period":   random.randint(10, 20),
        "adx_threshold": random.randint(20, 30),
        "fast_ema":     fast,
        "slow_ema":     slow,
        "stop_loss":    random.randint(200, 500),
        "take_profit":  random.randint(400, 1000),
        "risk_percent": 1.0,
    }


def _donchian_params():
    return {
        "donchian_period":  random.randint(15, 30),
        "atr_period":       14,
        "breakout_confirm": random.randint(1, 3),
        "stop_loss":        random.randint(250, 600),
        "take_profit":      random.randint(500, 1200),
        "risk_percent":     1.0,
    }


def _multi_tf_params():
    fast = random.randint(10, 25)
    slow = random.randint(fast + 15, fast + 60)
    return {
        "fast_ema":          fast,
        "slow_ema":          slow,
        "higher_tf_ema":     random.randint(50, 100),
        "higher_timeframe":  random.choice(["H4", "D1"]),
        "rsi_period":        14,
        "rsi_buy":           random.randint(52, 60),
        "rsi_sell":          random.randint(40, 48),
        "stop_loss":         random.randint(200, 500),
        "take_profit":       random.randint(400, 1000),
        "risk_percent":      1.0,
    }


def _news_avoidance_params():
    fast = random.randint(10, 25)
    slow = random.randint(fast + 15, fast + 60)
    return {
        "fast_ema":          fast,
        "slow_ema":          slow,
        "rsi_period":        14,
        "rsi_buy":           random.randint(52, 60),
        "rsi_sell":          random.randint(40, 48),
        "news_pause_minutes": random.choice([30, 60, 120]),
        "avoid_friday_close": True,
        "stop_loss":         random.randint(200, 500),
        "take_profit":       random.randint(400, 1000),
        "risk_percent":      1.0,
    }


def _ichimoku_params():
    return {
        "tenkan_period":   random.randint(7, 12),
        "kijun_period":    random.randint(22, 30),
        "senkou_b_period": random.randint(48, 56),
        "displacement":    26,
        "stop_loss":       random.randint(200, 600),
        "take_profit":     random.randint(400, 1200),
        "risk_percent":    1.0,
    }


def _stochastic_rsi_params():
    return {
        "stoch_period":     random.randint(12, 16),
        "stoch_smooth_k":   random.randint(2, 4),
        "stoch_smooth_d":   random.randint(2, 4),
        "rsi_period":       14,
        "oversold":         random.randint(20, 30),
        "overbought":       random.randint(70, 80),
        "stop_loss":        random.randint(150, 400),
        "take_profit":      random.randint(300, 800),
        "risk_percent":     1.0,
    }


def _vwap_deviation_params():
    return {
        "vwap_period":      random.randint(14, 25),
        "deviation_bands":  round(random.uniform(1.5, 2.5), 1),
        "rsi_period":       14,
        "rsi_confirm":      random.randint(45, 55),
        "stop_loss":        random.randint(150, 400),
        "take_profit":      random.randint(300, 800),
        "risk_percent":     1.0,
    }


def _pivot_points_params():
    return {
        "pivot_type":       random.choice(["standard", "fibonacci", "camarilla"]),
        "sr_levels":        random.choice([2, 3]),
        "ema_filter":       random.randint(50, 200),
        "rsi_period":       14,
        "rsi_confirm":      random.randint(45, 55),
        "stop_loss":        random.randint(200, 500),
        "take_profit":      random.randint(400, 1000),
        "risk_percent":     1.0,
    }


def _grid_trading_params():
    return {
        "grid_size_pips":   random.randint(15, 40),
        "grid_levels":      random.randint(3, 8),
        "base_lot":         round(random.uniform(0.01, 0.05), 2),
        "max_grid_dd_pct":  random.randint(10, 20),
        "take_profit":      random.randint(30, 80),
        "stop_loss":        random.randint(200, 500),
        "risk_percent":     0.5,
    }


PARAM_BUILDERS = {
    "ema_rsi":                 _ema_rsi_params,
    "breakout":                _breakout_params,
    "bollinger_mean_reversion":_bollinger_params,
    "macd_crossover":          _macd_params,
    "supertrend":              _supertrend_params,
    "adx_trend_filter":        _adx_params,
    "donchian_breakout":       _donchian_params,
    "multi_tf_ema_rsi":        _multi_tf_params,
    "news_avoidance":          _news_avoidance_params,
    # New
    "ichimoku":                _ichimoku_params,
    "stochastic_rsi":          _stochastic_rsi_params,
    "vwap_deviation":          _vwap_deviation_params,
    "pivot_points":            _pivot_points_params,
    "grid_trading":            _grid_trading_params,
}


def generate_strategy(timeframe: str = "M15", strategy_type: str = None):
    timeframe = normalize_timeframe(timeframe)
    if strategy_type not in PARAM_BUILDERS:
        strategy_type = random.choice(STRATEGY_TYPES)
    prefix = STRATEGY_PREFIXES[strategy_type]
    name   = f"{prefix}_{uuid.uuid4().hex[:8].upper()}"
    params = PARAM_BUILDERS[strategy_type]()
    return {
        "name":          name,
        "symbol":        "EURUSD",
        "timeframe":     timeframe,
        "strategy_type": strategy_type,
        "parameters":    params,
    }
