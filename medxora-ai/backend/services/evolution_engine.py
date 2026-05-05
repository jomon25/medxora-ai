import random
import copy
import uuid


def _mutate_ema_rsi(p: dict) -> dict:
    p["fast_ema"]  = max(5, p["fast_ema"] + random.randint(-3, 3))
    p["slow_ema"]  = max(p["fast_ema"] + 10, p["slow_ema"] + random.randint(-5, 5))
    p["rsi_buy"]   = max(50, min(70, p.get("rsi_buy", 55)  + random.randint(-2, 2)))
    p["rsi_sell"]  = max(30, min(50, p.get("rsi_sell", 45) + random.randint(-2, 2)))
    p["stop_loss"] = max(100, p["stop_loss"] + random.randint(-50, 50))
    p["take_profit"] = max(p["stop_loss"] + 100, p["take_profit"] + random.randint(-100, 100))
    return p


def _mutate_breakout(p: dict) -> dict:
    p["breakout_period"]  = max(5,   p.get("breakout_period", 20)  + random.randint(-3, 3))
    p["atr_multiplier"]   = max(1.0, round(p.get("atr_multiplier", 2.0) + random.uniform(-0.3, 0.3), 1))
    p["stop_loss"]        = max(100, p["stop_loss"] + random.randint(-50, 50))
    p["take_profit"]      = max(p["stop_loss"] + 100, p["take_profit"] + random.randint(-100, 100))
    return p


def _mutate_bollinger(p: dict) -> dict:
    p["bb_period"]    = max(5,   p.get("bb_period", 20) + random.randint(-2, 2))
    p["bb_deviation"] = max(1.0, round(p.get("bb_deviation", 2.0) + random.uniform(-0.2, 0.2), 1))
    p["rsi_oversold"] = max(20, min(40,  p.get("rsi_oversold", 30)  + random.randint(-3, 3)))
    p["rsi_overbought"] = max(60, min(80, p.get("rsi_overbought", 70) + random.randint(-3, 3)))
    p["stop_loss"]    = max(100, p["stop_loss"] + random.randint(-50, 50))
    p["take_profit"]  = max(p["stop_loss"] + 100, p["take_profit"] + random.randint(-80, 80))
    return p


def _mutate_macd(p: dict) -> dict:
    fast = max(5, p.get("macd_fast", 12) + random.randint(-2, 2))
    slow = max(fast + 5, p.get("macd_slow", 26) + random.randint(-3, 3))
    p["macd_fast"]   = fast
    p["macd_slow"]   = slow
    p["macd_signal"] = max(5, min(15, p.get("macd_signal", 9) + random.randint(-1, 1)))
    p["stop_loss"]   = max(100, p["stop_loss"] + random.randint(-50, 50))
    p["take_profit"] = max(p["stop_loss"] + 100, p["take_profit"] + random.randint(-100, 100))
    return p


def _mutate_supertrend(p: dict) -> dict:
    p["atr_period"]     = max(5,   p.get("atr_period", 10) + random.randint(-1, 1))
    p["atr_multiplier"] = max(1.5, round(p.get("atr_multiplier", 3.0) + random.uniform(-0.3, 0.3), 1))
    p["ema_filter"]     = max(50,  p.get("ema_filter", 200) + random.randint(-20, 20))
    p["stop_loss"]      = max(100, p["stop_loss"] + random.randint(-50, 50))
    p["take_profit"]    = max(p["stop_loss"] + 100, p["take_profit"] + random.randint(-100, 100))
    return p


def _mutate_adx(p: dict) -> dict:
    fast = max(5, p.get("fast_ema", 12) + random.randint(-2, 2))
    slow = max(fast + 10, p.get("slow_ema", 50) + random.randint(-5, 5))
    p["fast_ema"]      = fast
    p["slow_ema"]      = slow
    p["adx_period"]    = max(7, p.get("adx_period", 14) + random.randint(-2, 2))
    p["adx_threshold"] = max(15, min(35, p.get("adx_threshold", 25) + random.randint(-3, 3)))
    p["stop_loss"]     = max(100, p["stop_loss"] + random.randint(-50, 50))
    p["take_profit"]   = max(p["stop_loss"] + 100, p["take_profit"] + random.randint(-100, 100))
    return p


def _mutate_donchian(p: dict) -> dict:
    p["donchian_period"]  = max(5,  p.get("donchian_period", 20) + random.randint(-3, 3))
    p["breakout_confirm"] = max(1,  min(5, p.get("breakout_confirm", 2) + random.randint(-1, 1)))
    p["stop_loss"]        = max(100, p["stop_loss"] + random.randint(-50, 50))
    p["take_profit"]      = max(p["stop_loss"] + 100, p["take_profit"] + random.randint(-100, 100))
    return p


def _mutate_multi_tf(p: dict) -> dict:
    fast = max(5, p.get("fast_ema", 14) + random.randint(-3, 3))
    slow = max(fast + 10, p.get("slow_ema", 50) + random.randint(-5, 5))
    p["fast_ema"]       = fast
    p["slow_ema"]       = slow
    p["higher_tf_ema"]  = max(50, p.get("higher_tf_ema", 100) + random.randint(-10, 10))
    p["rsi_buy"]        = max(50, min(70, p.get("rsi_buy", 55)  + random.randint(-2, 2)))
    p["rsi_sell"]       = max(30, min(50, p.get("rsi_sell", 45) + random.randint(-2, 2)))
    p["stop_loss"]      = max(100, p["stop_loss"] + random.randint(-50, 50))
    p["take_profit"]    = max(p["stop_loss"] + 100, p["take_profit"] + random.randint(-100, 100))
    return p


def _mutate_news_avoidance(p: dict) -> dict:
    fast = max(5, p.get("fast_ema", 14) + random.randint(-3, 3))
    slow = max(fast + 10, p.get("slow_ema", 50) + random.randint(-5, 5))
    p["fast_ema"]           = fast
    p["slow_ema"]           = slow
    p["rsi_buy"]            = max(50, min(70, p.get("rsi_buy", 55)  + random.randint(-2, 2)))
    p["rsi_sell"]           = max(30, min(50, p.get("rsi_sell", 45) + random.randint(-2, 2)))
    p["news_pause_minutes"] = random.choice([30, 60, 120])
    p["stop_loss"]          = max(100, p["stop_loss"] + random.randint(-50, 50))
    p["take_profit"]        = max(p["stop_loss"] + 100, p["take_profit"] + random.randint(-100, 100))
    return p


def _mutate_ichimoku(p: dict) -> dict:
    p["tenkan_period"]   = max(5,  p.get("tenkan_period", 9)   + random.randint(-2, 2))
    p["kijun_period"]    = max(p["tenkan_period"] + 5, p.get("kijun_period", 26)  + random.randint(-3, 3))
    p["senkou_b_period"] = max(p["kijun_period"] * 2 - 5, p.get("senkou_b_period", 52) + random.randint(-4, 4))
    p["stop_loss"]       = max(100, p["stop_loss"] + random.randint(-50, 50))
    p["take_profit"]     = max(p["stop_loss"] + 100, p["take_profit"] + random.randint(-100, 100))
    return p


def _mutate_stochastic_rsi(p: dict) -> dict:
    p["stoch_period"]    = max(5,  p.get("stoch_period", 14)  + random.randint(-2, 2))
    p["stoch_smooth_k"]  = max(1,  p.get("stoch_smooth_k", 3) + random.randint(-1, 1))
    p["stoch_smooth_d"]  = max(1,  p.get("stoch_smooth_d", 3) + random.randint(-1, 1))
    p["oversold"]        = max(15, min(35, p.get("oversold", 25)   + random.randint(-3, 3)))
    p["overbought"]      = max(65, min(85, p.get("overbought", 75) + random.randint(-3, 3)))
    p["stop_loss"]       = max(100, p["stop_loss"] + random.randint(-40, 40))
    p["take_profit"]     = max(p["stop_loss"] + 100, p["take_profit"] + random.randint(-80, 80))
    return p


def _mutate_vwap(p: dict) -> dict:
    p["vwap_period"]      = max(5,  p.get("vwap_period", 20) + random.randint(-2, 2))
    p["deviation_bands"]  = max(1.0, round(p.get("deviation_bands", 2.0) + random.uniform(-0.2, 0.2), 1))
    p["rsi_confirm"]      = max(40, min(60, p.get("rsi_confirm", 50) + random.randint(-3, 3)))
    p["stop_loss"]        = max(100, p["stop_loss"] + random.randint(-40, 40))
    p["take_profit"]      = max(p["stop_loss"] + 100, p["take_profit"] + random.randint(-80, 80))
    return p


def _mutate_pivot(p: dict) -> dict:
    p["ema_filter"]   = max(20, p.get("ema_filter", 100) + random.randint(-20, 20))
    p["sr_levels"]    = random.choice([2, 3])
    p["rsi_confirm"]  = max(40, min(60, p.get("rsi_confirm", 50) + random.randint(-3, 3)))
    p["stop_loss"]    = max(100, p["stop_loss"] + random.randint(-50, 50))
    p["take_profit"]  = max(p["stop_loss"] + 100, p["take_profit"] + random.randint(-100, 100))
    return p


def _mutate_grid(p: dict) -> dict:
    p["grid_size_pips"] = max(5,  p.get("grid_size_pips", 20) + random.randint(-5, 5))
    p["grid_levels"]    = max(2,  min(10, p.get("grid_levels", 5) + random.randint(-1, 1)))
    p["max_grid_dd_pct"]= max(5,  min(25, p.get("max_grid_dd_pct", 15) + random.randint(-2, 2)))
    p["take_profit"]    = max(20, p.get("take_profit", 50) + random.randint(-10, 10))
    p["stop_loss"]      = max(100, p["stop_loss"] + random.randint(-50, 50))
    return p


_MUTATORS = {
    "ema_rsi":                 _mutate_ema_rsi,
    "breakout":                _mutate_breakout,
    "bollinger_mean_reversion":_mutate_bollinger,
    "macd_crossover":          _mutate_macd,
    "supertrend":              _mutate_supertrend,
    "adx_trend_filter":        _mutate_adx,
    "donchian_breakout":       _mutate_donchian,
    "multi_tf_ema_rsi":        _mutate_multi_tf,
    "news_avoidance":          _mutate_news_avoidance,
    # New
    "ichimoku":                _mutate_ichimoku,
    "stochastic_rsi":          _mutate_stochastic_rsi,
    "vwap_deviation":          _mutate_vwap,
    "pivot_points":            _mutate_pivot,
    "grid_trading":            _mutate_grid,
}

_PREFIX_MAP = {
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


def mutate_strategy(strategy: dict) -> dict:
    child  = copy.deepcopy(strategy)
    stype  = child.get("strategy_type", "ema_rsi")
    mutate = _MUTATORS.get(stype, _mutate_ema_rsi)
    child["parameters"] = mutate(child["parameters"])
    prefix = _PREFIX_MAP.get(stype, "EMA_RSI")
    child["name"]        = f"{prefix}_{uuid.uuid4().hex[:8].upper()}"
    child["parent_name"] = strategy["name"]
    return child


def score_result(result: dict) -> float:
    if not result:
        return 0.0
    net = result.get("net_profit", 0) or 0
    pf  = result.get("profit_factor", 1) or 1
    dd  = result.get("max_drawdown", 100) or 100
    wr  = result.get("win_rate", 0) or 0
    sr  = result.get("sharpe_ratio", 0) or 0
    if dd == 0:
        dd = 0.01
    score = (net * 0.3) + (pf * 200) + ((wr / 100) * 300) + (sr * 100) - (dd * 5)
    return round(score, 4)


def select_best(strategies_with_scores: list) -> dict:
    return max(strategies_with_scores, key=lambda x: x[1])[0]


def evolve_population(base_strategy: dict, size: int = 5) -> list:
    return [mutate_strategy(base_strategy) for _ in range(size)]
