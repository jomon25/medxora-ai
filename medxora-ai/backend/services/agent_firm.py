from typing import Literal

from pydantic import BaseModel, Field

from agents.risk_manager import check_risk


class AgentDecision(BaseModel):
    agent: str
    decision: Literal["approve", "reject", "needs_evolution", "needs_retest"]
    confidence: float = Field(ge=0, le=1)
    risk_level: Literal["low", "medium", "high"]
    reason: str
    next_action: str
    evidence: list[str] = Field(default_factory=list)
    data: dict = Field(default_factory=dict)
    review_state: Literal["Approved", "Rejected", "Needs Evolution", "Needs Retest"]


def _reward_ratio(strategy: dict) -> float:
    params = strategy.get("parameters", {})
    stop_loss = float(params.get("stop_loss", 0) or 0)
    take_profit = float(params.get("take_profit", 0) or 0)
    if stop_loss <= 0:
        return 0
    return take_profit / stop_loss


def technical_indicator_review(strategy: dict) -> AgentDecision:
    params = strategy.get("parameters", {})
    ema_gap = float((params.get("slow_ema", 0) or 0) - (params.get("fast_ema", 0) or 0))
    rr = _reward_ratio(strategy)
    evidence = [
        f"EMA gap is {ema_gap:.0f}",
        f"Reward/risk ratio is {rr:.2f}",
        f"RSI bands are {params.get('rsi_sell', 45)} / {params.get('rsi_buy', 55)}",
    ]

    if ema_gap >= 15 and rr >= 1.5:
        return AgentDecision(
            agent="Technical Indicator Agent",
            decision="approve",
            confidence=0.79,
            risk_level="low",
            reason="The indicator stack is reasonably spaced and the reward-to-risk profile is healthy.",
            next_action="run_bull_bear_debate",
            evidence=evidence,
            data={"ema_gap": ema_gap, "reward_ratio": rr},
            review_state="Approved",
        )

    return AgentDecision(
        agent="Technical Indicator Agent",
        decision="needs_evolution",
        confidence=0.68,
        risk_level="medium",
        reason="The technical structure is tradable but the current parameter spacing is vulnerable to noise or weak reward/risk.",
        next_action="run_bull_bear_debate",
        evidence=evidence,
        data={"ema_gap": ema_gap, "reward_ratio": rr},
        review_state="Needs Evolution",
    )


def bull_researcher_review(strategy: dict, metrics: dict | None = None) -> AgentDecision:
    rr = _reward_ratio(strategy)
    params = strategy.get("parameters", {})
    evidence = [
        f"Fast EMA {params.get('fast_ema')} and slow EMA {params.get('slow_ema')} create a trend-following spread.",
        f"Reward/risk ratio is {rr:.2f}.",
    ]
    if metrics:
        evidence.extend(
            [
                f"Net profit is {metrics.get('net_profit', 0)}.",
                f"Profit factor is {metrics.get('profit_factor', 0)}.",
            ]
        )

    return AgentDecision(
        agent="Bull Researcher Agent",
        decision="approve" if not metrics or float(metrics.get("net_profit", 0)) >= 0 else "needs_retest",
        confidence=0.74 if metrics else 0.63,
        risk_level="medium" if not metrics else ("low" if float(metrics.get("profit_factor", 0)) >= 1.3 else "medium"),
        reason="This setup has upside potential because the trend logic is simple, explainable, and can compound when directional conditions hold.",
        next_action="collect_bear_case",
        evidence=evidence,
        data={"reward_ratio": rr},
        review_state="Approved" if not metrics or float(metrics.get("net_profit", 0)) >= 0 else "Needs Retest",
    )


def bear_researcher_review(strategy: dict, metrics: dict | None = None) -> AgentDecision:
    params = strategy.get("parameters", {})
    ema_gap = float((params.get("slow_ema", 0) or 0) - (params.get("fast_ema", 0) or 0))
    evidence = [
        f"EMA gap is {ema_gap:.0f}, which may overtrade when too narrow.",
        f"Stop loss is {params.get('stop_loss')} and take profit is {params.get('take_profit')}.",
    ]
    if metrics:
        evidence.extend(
            [
                f"Drawdown is {metrics.get('max_drawdown', 0)}%.",
                f"Win rate is {metrics.get('win_rate', 0)}%.",
            ]
        )

    risky = ema_gap < 10 or (metrics and float(metrics.get("max_drawdown", 0)) > 10)
    return AgentDecision(
        agent="Bear Researcher Agent",
        decision="needs_evolution" if risky else "needs_retest",
        confidence=0.77 if risky else 0.61,
        risk_level="high" if risky else "medium",
        reason="This strategy can fail in chop or poor execution conditions because the parameter spacing and downside controls are not fully defensive.",
        next_action="send_to_risk_manager",
        evidence=evidence,
        data={"ema_gap": ema_gap},
        review_state="Needs Evolution" if risky else "Needs Retest",
    )


def risk_manager_review(strategy: dict, metrics: dict | None = None) -> AgentDecision:
    review = check_risk(strategy)
    evidence = review["issues"] + review["warnings"]
    if metrics:
        evidence.extend(
            [
                f"Observed drawdown is {metrics.get('max_drawdown', 0)}%.",
                f"Observed profit factor is {metrics.get('profit_factor', 0)}.",
            ]
        )

    if review["passed"] and (not metrics or float(metrics.get("max_drawdown", 0) or 0) <= 10):
        return AgentDecision(
            agent="Risk Manager Agent",
            decision="approve",
            confidence=0.83,
            risk_level="low" if not review["warnings"] else "medium",
            reason="The strategy passes the current hard risk limits and does not present an immediate structural risk breach.",
            next_action="send_to_portfolio_manager",
            evidence=evidence or ["No major risk issues found."],
            data=review,
            review_state="Approved",
        )

    return AgentDecision(
        agent="Risk Manager Agent",
        decision="reject" if review["issues"] else "needs_evolution",
        confidence=0.87 if review["issues"] else 0.73,
        risk_level="high",
        reason="The current strategy violates or pressures MedXora risk controls and should not be treated as deployment-ready.",
        next_action="evolve_or_retest",
        evidence=evidence or ["Risk conditions are not acceptable."],
        data=review,
        review_state="Rejected" if review["issues"] else "Needs Evolution",
    )


def portfolio_manager_review(
    strategy: dict,
    metrics: dict | None,
    upstream_reviews: list[AgentDecision],
) -> AgentDecision:
    if metrics is None:
        return AgentDecision(
            agent="Portfolio Manager Agent",
            decision="needs_retest",
            confidence=0.66,
            risk_level="medium",
            reason="Pre-backtest review is useful, but portfolio approval requires observed performance before deployment or inclusion.",
            next_action="run_backtest",
            evidence=[review.reason for review in upstream_reviews],
            data={"mode": "pre_backtest"},
            review_state="Needs Retest",
        )

    drawdown = float(metrics.get("max_drawdown", 100) or 100)
    profit_factor = float(metrics.get("profit_factor", 0) or 0)
    net_profit = float(metrics.get("net_profit", 0) or 0)
    evidence = [
        f"Net profit is {net_profit}.",
        f"Profit factor is {profit_factor}.",
        f"Max drawdown is {drawdown}%.",
    ]

    if net_profit > 0 and profit_factor >= 1.3 and drawdown < 10:
        decision = "approve"
        review_state = "Approved"
        reason = "The strategy meets the current portfolio admission thresholds for profitability, drawdown, and execution quality."
        next_action = "save_and_monitor"
        confidence = 0.84
        risk_level = "low"
    elif drawdown >= 15 or profit_factor < 1.0 or net_profit < 0:
        decision = "reject"
        review_state = "Rejected"
        reason = "The strategy should not be deployed because the realized performance profile is too weak or too risky."
        next_action = "store_failure_reason"
        confidence = 0.88
        risk_level = "high"
    elif profit_factor < 1.3 or drawdown >= 10:
        decision = "needs_evolution"
        review_state = "Needs Evolution"
        reason = "The strategy shows potential but needs parameter improvement before portfolio inclusion."
        next_action = "evolve_strategy"
        confidence = 0.78
        risk_level = "medium"
    else:
        decision = "needs_retest"
        review_state = "Needs Retest"
        reason = "The result is inconclusive and should be retested before any deployment decision."
        next_action = "run_additional_backtests"
        confidence = 0.71
        risk_level = "medium"

    return AgentDecision(
        agent="Portfolio Manager Agent",
        decision=decision,
        confidence=confidence,
        risk_level=risk_level,
        reason=reason,
        next_action=next_action,
        evidence=evidence + [review.reason for review in upstream_reviews],
        data={"net_profit": net_profit, "profit_factor": profit_factor, "max_drawdown": drawdown},
        review_state=review_state,
    )


def generate_agent_review(strategy: dict, metrics: dict | None = None) -> dict:
    technical = technical_indicator_review(strategy)
    bull = bull_researcher_review(strategy, metrics)
    bear = bear_researcher_review(strategy, metrics)
    risk = risk_manager_review(strategy, metrics)
    approval = portfolio_manager_review(strategy, metrics, [technical, bull, bear, risk])

    return {
        "technical_indicator_agent": technical.model_dump(),
        "bull_researcher_agent": bull.model_dump(),
        "bear_researcher_agent": bear.model_dump(),
        "risk_manager_agent": risk.model_dump(),
        "portfolio_manager_agent": approval.model_dump(),
    }
