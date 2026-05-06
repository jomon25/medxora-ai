from agents.market_regime_agent import run_market_regime_agent


def run_regime_adaptive_parameter_agent(strategy: dict, metrics: dict | None = None) -> dict:
    regime_result = run_market_regime_agent(strategy, metrics)
    regime = (regime_result.get("data") or {}).get("regime", "mixed")
    params = dict(strategy.get("parameters", {}))

    fast = int(params.get("fast_ema", 12) or 12)
    slow = int(params.get("slow_ema", 48) or 48)
    rsi_buy = float(params.get("rsi_buy", 55) or 55)
    rsi_sell = float(params.get("rsi_sell", 45) or 45)

    suggested = dict(params)
    rationale = []

    if regime == "trending":
        suggested["fast_ema"] = max(5, fast - 1)
        suggested["slow_ema"] = max(suggested["fast_ema"] + 15, slow + 6)
        suggested["rsi_buy"] = min(68, rsi_buy + 2)
        suggested["rsi_sell"] = max(32, rsi_sell - 1)
        rationale.append("Trending regime favors a wider EMA gap and more decisive momentum thresholds.")
    elif regime == "ranging":
        suggested["fast_ema"] = min(max(5, fast + 1), slow - 8)
        suggested["slow_ema"] = max(suggested["fast_ema"] + 10, slow - 5)
        suggested["rsi_buy"] = max(52, rsi_buy - 2)
        suggested["rsi_sell"] = min(48, rsi_sell + 2)
        rationale.append("Ranging regime favors tighter EMA spacing and less aggressive RSI levels.")
    elif regime == "volatile":
        suggested["slow_ema"] = slow + 8
        suggested["stop_loss"] = int(min(800, int(params.get("stop_loss", 300) or 300) * 1.15))
        suggested["take_profit"] = int(max(200, int(params.get("take_profit", 600) or 600) * 1.1))
        rationale.append("Volatile conditions call for slower confirmation and wider execution buffers.")
    else:
        suggested["risk_percent"] = min(2.0, max(0.5, float(params.get("risk_percent", 1.0) or 1.0)))
        rationale.append("Mixed regime keeps the setup conservative until a clearer market state emerges.")

    changed_keys = [key for key, value in suggested.items() if params.get(key) != value]
    decision = "approve" if regime_result.get("decision") == "approve" else "needs_evolution"
    confidence = 0.74 if changed_keys else 0.62

    return {
        "agent": "Regime-Adaptive Parameter Agent",
        "decision": decision,
        "confidence": confidence,
        "risk_level": "low" if decision == "approve" else "medium",
        "reason": " ".join(rationale) if rationale else "No regime-specific parameter changes were necessary.",
        "evidence": [
            f"Detected regime: {regime}",
            f"Parameters changed: {', '.join(changed_keys) if changed_keys else 'none'}",
            regime_result.get("reason", "Used regime classifier as upstream context."),
        ],
        "data": {
            "regime": regime,
            "current_parameters": params,
            "suggested_parameters": suggested,
            "changed_keys": changed_keys,
        },
        "review_state": "Approved" if decision == "approve" else "Needs Evolution",
    }
