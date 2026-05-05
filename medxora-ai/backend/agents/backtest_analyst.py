from services.evolution_engine import score_result
from services.report_parser import parse_mock_result, parse_report


def analyze(strategy_name: str, report_path: str | None = None, use_mock: bool = False) -> dict:
    if use_mock or not report_path:
        raw = parse_mock_result(strategy_name)
    else:
        raw = parse_report(report_path)

    if not raw:
        return {"status": "no_data", "strategy": strategy_name}

    fitness = score_result(raw)
    grade = _grade(fitness)

    return {
        "status": "analyzed",
        "strategy": strategy_name,
        "metrics": raw,
        "fitness_score": fitness,
        "grade": grade,
        "verdict": _verdict(raw),
    }


def analyze_backtest(metrics: dict) -> dict:
    """
    Compatibility helper for callers that already have parsed metrics.
    """
    if not metrics:
        return {"status": "no_data"}

    fitness = score_result(metrics)
    grade = _grade(fitness)
    return {
        "status": "analyzed",
        "metrics": metrics,
        "fitness_score": fitness,
        "grade": grade,
        "verdict": _verdict(metrics),
    }


def _grade(score: float) -> str:
    if score >= 800:
        return "A"
    if score >= 600:
        return "B"
    if score >= 400:
        return "C"
    if score >= 200:
        return "D"
    return "F"


def _verdict(metrics: dict) -> str:
    pf = metrics.get("profit_factor", 0) or 0
    dd = metrics.get("max_drawdown", 100) or 100
    wr = metrics.get("win_rate", 0) or 0

    if pf >= 1.5 and dd <= 15 and wr >= 55:
        return "Strong - consider live testing"
    if pf >= 1.2 and dd <= 25:
        return "Moderate - needs further optimization"
    return "Weak - evolve or discard"
