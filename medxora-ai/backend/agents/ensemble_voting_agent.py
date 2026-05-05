"""
Ensemble Voting Agent — confidence-weighted consensus across all agents.

Veto rule: if Risk Manager Agent OR Monte Carlo Agent returns "reject",
the ensemble final decision is forced to "reject" regardless of other votes.
"""

_AGENT_WEIGHTS: dict[str, float] = {
    "Market Regime Agent":         0.65,
    "Technical Indicator Agent":   0.70,
    "Bull Researcher Agent":       0.55,
    "Bear Researcher Agent":       0.75,
    "Risk Manager Agent":          0.90,
    "Overfitting Detector Agent":  0.80,
    "Monte Carlo Agent":           0.85,
    "Session Performance Agent":   0.50,
    "Adaptive Risk Agent":         0.60,
    "Correlation Guard Agent":     0.70,
    "Portfolio Manager Agent":     0.85,
}

_VETO_AGENTS = {"Risk Manager Agent", "Monte Carlo Agent"}

_SCORE_MAP: dict[str, float] = {
    "approve":          1.0,
    "needs_retest":     0.4,
    "needs_evolution":  0.0,
    "reject":          -1.0,
}


def run_ensemble_voting_agent(agent_decisions: list[dict]) -> dict:
    if not agent_decisions:
        return {
            "agent": "Ensemble Voting Agent",
            "decision": "needs_retest",
            "confidence": 0.50,
            "risk_level": "medium",
            "reason": "No agent decisions to aggregate.",
            "evidence": [],
            "data": {},
            "review_state": "Needs Retest",
        }

    weighted_score   = 0.0
    total_weight     = 0.0
    weighted_conf    = 0.0
    tally: dict[str, int] = {"approve": 0, "reject": 0, "needs_evolution": 0, "needs_retest": 0}
    votes = []
    veto_triggered = False

    for d in agent_decisions:
        name       = d.get("agent", "Unknown Agent")
        decision   = d.get("decision", "needs_retest")
        confidence = float(d.get("confidence", 0.5))
        risk_level = d.get("risk_level", "medium")
        weight     = _AGENT_WEIGHTS.get(name, 0.60)
        eff_weight = weight * confidence

        score = _SCORE_MAP.get(decision, 0.0)
        weighted_score += score * eff_weight
        total_weight   += eff_weight
        weighted_conf  += confidence * weight

        tally[decision] = tally.get(decision, 0) + 1

        if name in _VETO_AGENTS and decision == "reject":
            veto_triggered = True

        votes.append({
            "agent":          name,
            "decision":       decision,
            "confidence":     confidence,
            "weight":         weight,
            "effective_weight": round(eff_weight, 4),
            "risk_level":     risk_level,
        })

    norm_score  = weighted_score / total_weight if total_weight > 0 else 0.0
    avg_conf    = weighted_conf / sum(_AGENT_WEIGHTS.get(v["agent"], 0.6) for v in votes) if votes else 0.5

    if veto_triggered:
        final_decision = "reject"
        review_state   = "Rejected"
        risk_level     = "high"
    elif norm_score >= 0.50:
        final_decision, review_state, risk_level = "approve",         "Approved",        "low"
    elif norm_score >= 0.10:
        final_decision, review_state, risk_level = "needs_retest",    "Needs Retest",    "medium"
    elif norm_score >= -0.30:
        final_decision, review_state, risk_level = "needs_evolution", "Needs Evolution", "medium"
    else:
        final_decision, review_state, risk_level = "reject",          "Rejected",        "high"

    total = len(votes)
    evidence = [
        f"Total agents voted: {total}",
        (
            f"Approve: {tally.get('approve',0)} | "
            f"Reject: {tally.get('reject',0)} | "
            f"Evolution: {tally.get('needs_evolution',0)} | "
            f"Retest: {tally.get('needs_retest',0)}"
        ),
        f"Weighted consensus score: {norm_score:.3f}  (range −1.0 → +1.0)",
        f"Average weighted confidence: {avg_conf:.3f}",
        f"Veto triggered: {veto_triggered}",
    ]
    if veto_triggered:
        vetoes = [v["agent"] for v in votes if v["agent"] in _VETO_AGENTS and v["decision"] == "reject"]
        evidence.append(f"Veto by: {', '.join(vetoes)}")

    ensemble_confidence = round(min(abs(norm_score) * 0.40 + avg_conf * 0.60, 0.97), 3)

    return {
        "agent": "Ensemble Voting Agent",
        "decision": final_decision,
        "confidence": ensemble_confidence,
        "risk_level": risk_level,
        "reason": (
            f"Ensemble consensus ({total} agents): {final_decision.replace('_', ' ').title()}. "
            f"Weighted score: {norm_score:.2f}."
            + (" VETO applied." if veto_triggered else "")
        ),
        "evidence": evidence,
        "data": {
            "weighted_consensus_score": round(norm_score, 4),
            "decision_tally": tally,
            "total_agents": total,
            "veto_triggered": veto_triggered,
            "votes": sorted(votes, key=lambda v: v["effective_weight"], reverse=True),
        },
        "review_state": review_state,
    }
