import copy
import random

PARAM_LIMITS = {
    "fast_ema": (5, 50),
    "slow_ema": (20, 200),
    "rsi_buy": (50, 70),
    "rsi_sell": (30, 50),
    "stop_loss": (100, 1000),
    "take_profit": (200, 3000),
}


def clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))


def fitness_score(metrics: dict):
    net_profit = float(metrics.get("net_profit", 0))
    profit_factor = float(metrics.get("profit_factor", 0))
    win_rate = float(metrics.get("win_rate", 0))
    sharpe = float(metrics.get("sharpe_ratio", 0))
    drawdown = float(metrics.get("max_drawdown", 100))

    return (
        net_profit * 0.30
        + profit_factor * 200
        + win_rate * 3
        + sharpe * 100
        - drawdown * 5
    )


def smart_mutate(strategy: dict, mutation_memory: list[dict] | None = None):
    child = copy.deepcopy(strategy)
    params = child["parameters"]

    if mutation_memory:
        good_changes = [
            m for m in mutation_memory
            if m.get("child_score", 0) > m.get("parent_score", 0)
        ]
    else:
        good_changes = []

    for key in PARAM_LIMITS:
        if key not in params:
            continue

        low, high = PARAM_LIMITS[key]

        if good_changes:
            related = [m for m in good_changes if m.get("param") == key]

            if related:
                avg_delta = sum(m["delta"] for m in related) / len(related)
                delta = int(avg_delta + random.randint(-2, 2))
            else:
                delta = random.randint(-5, 5)
        else:
            if key in ["fast_ema", "rsi_buy", "rsi_sell"]:
                delta = random.randint(-3, 3)
            elif key == "slow_ema":
                delta = random.randint(-10, 10)
            else:
                delta = random.randint(-100, 100)

        params[key] = clamp(params[key] + delta, low, high)

    if params["fast_ema"] >= params["slow_ema"]:
        params["fast_ema"] = max(5, params["slow_ema"] - 5)

    if params["take_profit"] < params["stop_loss"] * 1.5:
        params["take_profit"] = int(params["stop_loss"] * 1.5)

    child["name"] = strategy["name"] + f"_EV_{random.randint(1000, 9999)}"

    return child


def evolve_population(parent_strategy, parent_metrics, generations=3, children_per_generation=5):
    parent_score = fitness_score(parent_metrics)

    best_strategy = parent_strategy
    best_metrics = parent_metrics
    best_score = parent_score

    mutation_memory = []

    for gen in range(generations):
        children = []

        for _ in range(children_per_generation):
            child = smart_mutate(best_strategy, mutation_memory)
            children.append(child)

        return {
            "generation": gen + 1,
            "parent": best_strategy,
            "children": children,
            "best_score": best_score,
            "mutation_memory": mutation_memory,
        }

    return {
        "best_strategy": best_strategy,
        "best_metrics": best_metrics,
        "best_score": best_score,
    }
