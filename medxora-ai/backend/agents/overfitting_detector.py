import copy
import math

from services.report_parser import parse_mock_result
from services.evolution_engine import score_result

_PARAM_NUMERIC = [
    "fast_ema", "slow_ema", "rsi_period", "rsi_buy", "rsi_sell",
    "stop_loss", "take_profit", "bb_period", "bb_deviation",
    "macd_fast", "macd_slow", "macd_signal", "atr_period", "atr_multiplier",
    "ema_filter", "adx_period", "adx_threshold", "donchian_period",
    "breakout_period", "higher_tf_ema",
]

_DELTAS = [0.93, 0.97, 1.03, 1.07]  # ±3% and ±7%


def _perturb(strategy: dict, param: str, delta: float) -> dict:
    child = copy.deepcopy(strategy)
    p = child.get("parameters", {})
    if param in p and isinstance(p[param], (int, float)):
        raw = p[param] * delta
        child["parameters"][param] = max(1, int(round(raw))) if isinstance(p[param], int) else round(raw, 2)
        child["name"] = f"{strategy['name']}_P{param[:4]}{int(delta*100)}"
    return child


def run_overfitting_detector(strategy: dict, metrics: dict | None = None) -> dict:
    base_metrics = metrics or parse_mock_result(strategy["name"])
    base_score = score_result(base_metrics)

    if base_score <= 0:
        return {
            "agent": "Overfitting Detector Agent",
            "decision": "reject",
            "confidence": 0.88,
            "risk_level": "high",
            "reason": "Base strategy has zero or negative fitness score — cannot assess robustness.",
            "evidence": [f"Base fitness score: {base_score:.2f}"],
            "data": {"base_score": base_score, "sensitivity_cv": None, "fragile_params": []},
            "review_state": "Rejected",
        }

    p = strategy.get("parameters", {})
    present_params = [k for k in _PARAM_NUMERIC if k in p and isinstance(p[k], (int, float))]

    all_scores = []
    fragile = []

    for param in present_params:
        param_scores = []
        for delta in _DELTAS:
            child = _perturb(strategy, param, delta)
            child_score = score_result(parse_mock_result(child["name"]))
            param_scores.append(child_score)

        if param_scores:
            avg = sum(param_scores) / len(param_scores)
            drop_pct = (base_score - avg) / base_score if base_score > 0 else 0
            all_scores.extend(param_scores)
            if drop_pct > 0.30:
                fragile.append(f"{param} drops {drop_pct*100:.1f}% on ±7% param change")

    if not all_scores:
        sensitivity = 0.0
    else:
        mean = sum(all_scores) / len(all_scores)
        variance = sum((s - mean) ** 2 for s in all_scores) / len(all_scores)
        sensitivity = math.sqrt(variance) / max(abs(mean), 1)

    evidence = [
        f"Base fitness score: {base_score:.2f}",
        f"Parameter sensitivity (CV): {sensitivity:.3f}",
        f"Parameters tested: {len(present_params)}",
        f"Fragile parameters found: {len(fragile)}",
    ]
    evidence.extend(fragile[:3])

    if sensitivity > 0.40 or len(fragile) >= 3:
        decision, confidence, risk_level, review_state = "needs_evolution", min(0.70 + sensitivity * 0.3, 0.93), "high", "Needs Evolution"
        reason = f"High parameter sensitivity (CV={sensitivity:.2f}) — strategy likely curve-fitted. Fragile params: {len(fragile)}."
    elif sensitivity > 0.25 or len(fragile) >= 1:
        decision, confidence, risk_level, review_state = "needs_retest", 0.72, "medium", "Needs Retest"
        reason = f"Moderate sensitivity (CV={sensitivity:.2f}). Strategy may be partially over-optimised."
    else:
        decision, confidence, risk_level, review_state = "approve", min(0.78 + (0.25 - sensitivity), 0.92), "low", "Approved"
        reason = f"Strategy is robust across parameter perturbations (CV={sensitivity:.2f}). Overfitting risk is low."

    return {
        "agent": "Overfitting Detector Agent",
        "decision": decision,
        "confidence": round(confidence, 3),
        "risk_level": risk_level,
        "reason": reason,
        "evidence": evidence,
        "data": {
            "base_score": round(base_score, 2),
            "sensitivity_cv": round(sensitivity, 4),
            "fragile_params": fragile,
            "params_tested": len(present_params),
            "sample_scores": [round(s, 2) for s in all_scores[:20]],
        },
        "review_state": review_state,
    }
