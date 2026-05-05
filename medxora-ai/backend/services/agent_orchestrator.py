"""
Agent Orchestrator — central hub for MedXora AI's advanced agent architecture.

Architecture:
  - AgentRegistry  : all agents registered with metadata and weights
  - Pipeline       : sequential execution with per-agent timing
  - Veto System    : hard-stop agents (Risk Manager, Monte Carlo) can force reject
  - Ensemble Vote  : confidence-weighted consensus after all agents run
  - Decision Trail : full audit log returned with every orchestration
"""

import time
from dataclasses import dataclass, field
from typing import Callable

from agents.adaptive_risk_agent      import run_adaptive_risk_agent
from agents.correlation_guard_agent  import run_correlation_guard_agent
from agents.ensemble_voting_agent    import run_ensemble_voting_agent
from agents.market_regime_agent      import run_market_regime_agent
from agents.monte_carlo_agent        import run_monte_carlo_agent
from agents.overfitting_detector     import run_overfitting_detector
from agents.session_performance_agent import run_session_performance_agent
from services.agent_firm import (
    bull_researcher_review,
    bear_researcher_review,
    portfolio_manager_review,
    risk_manager_review,
    technical_indicator_review,
)


# ── Wrappers to normalise AgentDecision Pydantic objects → plain dicts ────────

def _wrap(fn: Callable) -> Callable:
    def handler(strategy: dict, metrics: dict | None = None, **_ctx) -> dict:
        result = fn(strategy, metrics)
        return result.model_dump() if hasattr(result, "model_dump") else result
    return handler


def _wrap_portfolio(fn: Callable) -> Callable:
    def handler(strategy: dict, metrics: dict | None = None, upstream: list | None = None, **_ctx) -> dict:
        result = fn(strategy, metrics, upstream or [])
        return result.model_dump() if hasattr(result, "model_dump") else result
    return handler


# ── Agent metadata record ──────────────────────────────────────────────────────

@dataclass
class AgentRecord:
    name:         str
    role:         str
    category:     str    # risk | technical | research | quantitative | meta
    weight:       float  # voting power (0.0 – 1.0)
    description:  str
    capabilities: list[str]
    handler:      Callable
    needs_metrics:   bool = False
    needs_portfolio: bool = False
    needs_upstream:  bool = False
    field_order:     int  = 99


# ── Registry ──────────────────────────────────────────────────────────────────

class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, AgentRecord] = {}

    def register(self, record: AgentRecord) -> None:
        self._agents[record.role] = record

    def get(self, role: str) -> AgentRecord | None:
        return self._agents.get(role)

    def all_sorted(self) -> list[AgentRecord]:
        return sorted(self._agents.values(), key=lambda r: r.field_order)

    def as_list(self, runs_map: dict[str, int] | None = None) -> list[dict]:
        rows = []
        for i, rec in enumerate(self.all_sorted(), start=1):
            rows.append({
                "id":           i,
                "name":         rec.name,
                "role":         rec.role,
                "category":     rec.category,
                "weight":       rec.weight,
                "status":       "active",
                "description":  rec.description,
                "capabilities": rec.capabilities,
                "runs":         (runs_map or {}).get(rec.role, 0),
            })
        # Append Ensemble Voting Agent (meta, always last)
        rows.append({
            "id":           len(rows) + 1,
            "name":         "Ensemble Voting Agent",
            "role":         "ensemble_voting_agent",
            "category":     "meta",
            "weight":       1.0,
            "status":       "active",
            "description":  (
                "Aggregates all agent decisions with confidence-weighted voting. "
                "Enforces veto rules from Risk Manager and Monte Carlo agents."
            ),
            "capabilities": ["weighted_voting", "veto_enforcement", "consensus_building", "decision_audit"],
            "runs":         (runs_map or {}).get("ensemble_voting_agent", 0),
        })
        return rows


# ── Orchestrator ───────────────────────────────────────────────────────────────

class AgentOrchestrator:
    def __init__(self) -> None:
        self.registry = AgentRegistry()
        self._build_registry()

    def _build_registry(self) -> None:
        agents = [
            AgentRecord(
                name="Market Regime Agent",
                role="market_regime_agent",
                category="technical",
                weight=0.65,
                description="Classifies market as trending/ranging/volatile and checks strategy type fit.",
                capabilities=["regime_detection", "strategy_type_fit", "ema_gap_analysis"],
                handler=lambda s, m=None, **_: run_market_regime_agent(s, m),
                field_order=1,
            ),
            AgentRecord(
                name="Technical Indicator Agent",
                role="technical_indicator_agent",
                category="technical",
                weight=0.70,
                description="Reviews EMA spacing, RSI bands, and reward-to-risk structure.",
                capabilities=["ema_analysis", "rsi_validation", "reward_risk_review"],
                handler=_wrap(technical_indicator_review),
                field_order=2,
            ),
            AgentRecord(
                name="Bull Researcher Agent",
                role="bull_researcher_agent",
                category="research",
                weight=0.55,
                description="Builds bullish case and upside scenario analysis.",
                capabilities=["upside_analysis", "profit_scenario", "trend_confirmation"],
                handler=_wrap(bull_researcher_review),
                needs_metrics=True,
                field_order=3,
            ),
            AgentRecord(
                name="Bear Researcher Agent",
                role="bear_researcher_agent",
                category="research",
                weight=0.75,
                description="Challenges setup, identifies downside risks and failure modes.",
                capabilities=["downside_analysis", "failure_modes", "drawdown_risk"],
                handler=_wrap(bear_researcher_review),
                needs_metrics=True,
                field_order=4,
            ),
            AgentRecord(
                name="Risk Manager Agent",
                role="risk_manager_agent",
                category="risk",
                weight=0.90,
                description="Validates strategy against hard risk constraints — carries veto power.",
                capabilities=["hard_risk_gating", "parameter_validation", "sl_tp_check"],
                handler=_wrap(risk_manager_review),
                needs_metrics=True,
                field_order=5,
            ),
            AgentRecord(
                name="Overfitting Detector Agent",
                role="overfitting_detector_agent",
                category="quantitative",
                weight=0.80,
                description="Detects curve-fitting via parameter sensitivity analysis (CV scoring).",
                capabilities=["sensitivity_analysis", "parameter_perturbation", "robustness_check"],
                handler=lambda s, m=None, **_: run_overfitting_detector(s, m),
                field_order=6,
            ),
            AgentRecord(
                name="Monte Carlo Agent",
                role="monte_carlo_agent",
                category="quantitative",
                weight=0.85,
                description="Runs 1 000-scenario simulation for ruin probability and tail-risk — carries veto power.",
                capabilities=["monte_carlo_simulation", "ruin_probability", "equity_distribution", "tail_risk"],
                handler=lambda s, m=None, **_: run_monte_carlo_agent(s, m),
                needs_metrics=True,
                field_order=7,
            ),
            AgentRecord(
                name="Session Performance Agent",
                role="session_performance_agent",
                category="technical",
                weight=0.50,
                description="Scores strategy fit for London, NY, Asian, and Overlap sessions.",
                capabilities=["session_scoring", "timeframe_analysis", "news_filter_check"],
                handler=lambda s, m=None, **_: run_session_performance_agent(s, m),
                field_order=8,
            ),
            AgentRecord(
                name="Adaptive Risk Agent",
                role="adaptive_risk_agent",
                category="risk",
                weight=0.60,
                description="Applies half-Kelly Criterion to recommend optimal position sizing.",
                capabilities=["kelly_criterion", "position_sizing", "drawdown_adjusted_risk"],
                handler=lambda s, m=None, **_: run_adaptive_risk_agent(s, m),
                needs_metrics=True,
                field_order=9,
            ),
            AgentRecord(
                name="Correlation Guard Agent",
                role="correlation_guard_agent",
                category="meta",
                weight=0.70,
                description="Detects parameter similarity with existing portfolio strategies to enforce diversification.",
                capabilities=["cosine_similarity", "duplicate_detection", "diversification_check"],
                handler=lambda s, m=None, portfolio=None, **_: run_correlation_guard_agent(s, portfolio),
                needs_portfolio=True,
                field_order=10,
            ),
            AgentRecord(
                name="Portfolio Manager Agent",
                role="portfolio_manager_agent",
                category="meta",
                weight=0.85,
                description="Final approval gate using observed performance metrics and upstream agent reviews.",
                capabilities=["portfolio_admission", "threshold_gating", "strategy_routing"],
                handler=_wrap_portfolio(portfolio_manager_review),
                needs_metrics=True,
                needs_upstream=True,
                field_order=11,
            ),
        ]
        for rec in agents:
            self.registry.register(rec)

    # ── Public API ─────────────────────────────────────────────────────────────

    def get_agent_list(self, runs_map: dict[str, int] | None = None) -> list[dict]:
        return self.registry.as_list(runs_map)

    def run(
        self,
        strategy: dict,
        metrics:  dict | None = None,
        portfolio_strategies: list[dict] | None = None,
    ) -> dict:
        """
        Execute the full agent pipeline and return a structured orchestration result.

        Returns
        -------
        dict with keys:
          strategy_name, final_decision, final_confidence, final_risk_level,
          final_reason, review_state, agent_decisions, pipeline_log,
          decision_summary, total_agents_run, elapsed_seconds
        """
        t_start   = time.perf_counter()
        decisions = {}
        log       = []
        upstream_list: list[dict] = []

        # ── Run all agents except Portfolio Manager + Ensemble ─────────────────
        for rec in self.registry.all_sorted():
            if rec.role == "portfolio_manager_agent":
                continue  # handled after the loop

            t0 = time.perf_counter()
            try:
                result = rec.handler(
                    strategy,
                    m=metrics,
                    portfolio=portfolio_strategies,
                    upstream=upstream_list,
                )
            except Exception as exc:
                result = {
                    "agent":    rec.name,
                    "decision": "needs_retest",
                    "confidence": 0.50,
                    "risk_level": "medium",
                    "reason":   f"Agent error: {exc}",
                    "evidence": [str(exc)],
                    "data":     {},
                    "review_state": "Needs Retest",
                }

            elapsed = round(time.perf_counter() - t0, 4)
            decisions[rec.role] = result
            upstream_list.append(result)
            log.append({
                "agent":      rec.name,
                "role":       rec.role,
                "decision":   result.get("decision"),
                "confidence": result.get("confidence"),
                "elapsed_s":  elapsed,
            })

        # ── Portfolio Manager (needs upstream decisions) ───────────────────────
        pm_rec = self.registry.get("portfolio_manager_agent")
        if pm_rec:
            t0 = time.perf_counter()
            try:
                pm_result = pm_rec.handler(
                    strategy,
                    m=metrics,
                    upstream=upstream_list,
                )
            except Exception as exc:
                pm_result = {
                    "agent":      "Portfolio Manager Agent",
                    "decision":   "needs_retest",
                    "confidence": 0.50,
                    "risk_level": "medium",
                    "reason":     f"Portfolio Manager error: {exc}",
                    "evidence":   [],
                    "data":       {},
                    "review_state": "Needs Retest",
                }
            elapsed = round(time.perf_counter() - t0, 4)
            decisions["portfolio_manager_agent"] = pm_result
            upstream_list.append(pm_result)
            log.append({
                "agent":      "Portfolio Manager Agent",
                "role":       "portfolio_manager_agent",
                "decision":   pm_result.get("decision"),
                "confidence": pm_result.get("confidence"),
                "elapsed_s":  elapsed,
            })

        # ── Ensemble Voting ────────────────────────────────────────────────────
        t0 = time.perf_counter()
        ensemble = run_ensemble_voting_agent(list(decisions.values()))
        elapsed  = round(time.perf_counter() - t0, 4)
        decisions["ensemble_voting_agent"] = ensemble
        log.append({
            "agent":      "Ensemble Voting Agent",
            "role":       "ensemble_voting_agent",
            "decision":   ensemble.get("decision"),
            "confidence": ensemble.get("confidence"),
            "elapsed_s":  elapsed,
        })

        # ── Summary ────────────────────────────────────────────────────────────
        tally: dict[str, int] = {}
        for d in decisions.values():
            dec = d.get("decision", "unknown")
            tally[dec] = tally.get(dec, 0) + 1

        return {
            "strategy_name":    strategy.get("name"),
            "final_decision":   ensemble.get("decision"),
            "final_confidence": ensemble.get("confidence"),
            "final_risk_level": ensemble.get("risk_level"),
            "final_reason":     ensemble.get("reason"),
            "review_state":     ensemble.get("review_state"),
            "veto_triggered":   ensemble.get("data", {}).get("veto_triggered", False),
            "agent_decisions":  decisions,
            "pipeline_log":     log,
            "decision_summary": tally,
            "total_agents_run": len(decisions),
            "elapsed_seconds":  round(time.perf_counter() - t_start, 3),
        }


# ── Singleton ─────────────────────────────────────────────────────────────────

_orchestrator: AgentOrchestrator | None = None


def get_orchestrator() -> AgentOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator
