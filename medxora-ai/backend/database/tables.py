"""
database/tables.py
ORM table definitions for MedXora AI.

Tables
------
strategies          — every generated EA, including evolved children
backtest_results    — one row per backtest run (real or mock)
"""

import json

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from database.db import Base


class Strategy(Base):
    __tablename__ = "strategies"

    id           = Column(Integer, primary_key=True, index=True)
    name         = Column(String, unique=True, index=True)
    symbol       = Column(String, default="EURUSD")
    timeframe    = Column(String, default="M15")
    type         = Column(String, default="trend_following")   # strategy_type alias
    fast_ema     = Column(Integer)
    slow_ema     = Column(Integer)
    rsi_period   = Column(Integer)
    rsi_buy      = Column(Float)
    rsi_sell     = Column(Float)
    stop_loss    = Column(Integer)
    take_profit  = Column(Integer)
    risk_percent = Column(Float)
    mql5_file       = Column(String, nullable=True)
    parameters_json = Column(Text, nullable=True)   # full strategy params serialized as JSON
    parent_id    = Column(Integer, ForeignKey("strategies.id"), nullable=True)
    generation   = Column(Integer, default=0)
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    backtest_results = relationship("BacktestResult", back_populates="strategy")

    def as_dict(self) -> dict:
        # Start with extended params from JSON blob (covers MACD, Ichimoku, Bollinger, etc.)
        params: dict = {}
        if self.parameters_json:
            try:
                params = json.loads(self.parameters_json)
            except Exception:
                pass
        # Individual columns always win — they were the saved canonical values
        params.update({
            "fast_ema":     self.fast_ema,
            "slow_ema":     self.slow_ema,
            "rsi_period":   self.rsi_period,
            "rsi_buy":      self.rsi_buy,
            "rsi_sell":     self.rsi_sell,
            "stop_loss":    self.stop_loss,
            "take_profit":  self.take_profit,
            "risk_percent": self.risk_percent,
        })
        return {
            "id":            self.id,
            "name":          self.name,
            "symbol":        self.symbol,
            "timeframe":     self.timeframe,
            "strategy_type": self.type,
            "generation":    self.generation,
            "created_at":    self.created_at.isoformat() if self.created_at else None,
            "parameters":    params,
        }


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id               = Column(Integer, primary_key=True, index=True)
    strategy_id      = Column(Integer, ForeignKey("strategies.id"))
    net_profit       = Column(Float, nullable=True)
    gross_profit     = Column(Float, nullable=True)
    gross_loss       = Column(Float, nullable=True)
    max_drawdown     = Column(Float, nullable=True)
    win_rate         = Column(Float, nullable=True)
    total_trades     = Column(Integer, nullable=True)
    profit_factor    = Column(Float, nullable=True)
    expected_payoff  = Column(Float, nullable=True)
    sharpe_ratio     = Column(Float, nullable=True)
    recovery_factor  = Column(Float, nullable=True)
    monthly_profit   = Column(Float, nullable=True)
    yearly_profit    = Column(Float, nullable=True)
    report_file      = Column(String, nullable=True)
    status           = Column(String, default="pending")
    created_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    strategy = relationship("Strategy", back_populates="backtest_results")

    def as_dict(self) -> dict:
        return {
            "id":              self.id,
            "strategy_id":     self.strategy_id,
            "net_profit":      self.net_profit,
            "gross_profit":    self.gross_profit,
            "gross_loss":      self.gross_loss,
            "max_drawdown":    self.max_drawdown,
            "win_rate":        self.win_rate,
            "total_trades":    self.total_trades,
            "profit_factor":   self.profit_factor,
            "expected_payoff": self.expected_payoff,
            "sharpe_ratio":    self.sharpe_ratio,
            "recovery_factor": self.recovery_factor,
            "monthly_profit":  self.monthly_profit,
            "yearly_profit":   self.yearly_profit,
            "report_file":     self.report_file,
            "status":          self.status,
            "created_at":      self.created_at.isoformat() if self.created_at else None,
        }


class AgentMemory(Base):
    __tablename__ = "agent_memory"

    id           = Column(Integer, primary_key=True, index=True)
    strategy_name = Column(String, index=True, nullable=True)
    agent_name   = Column(String, index=True)
    category     = Column(String, index=True)
    memory_text  = Column(Text)
    confidence   = Column(Float, nullable=True)
    payload_json = Column(Text, nullable=True)
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "strategy_name": self.strategy_name,
            "agent_name": self.agent_name,
            "category": self.category,
            "memory_text": self.memory_text,
            "confidence": self.confidence,
            "payload": json.loads(self.payload_json) if self.payload_json else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class StrategyReflection(Base):
    __tablename__ = "strategy_reflections"

    id              = Column(Integer, primary_key=True, index=True)
    strategy_name   = Column(String, index=True)
    reflection_type = Column(String, index=True)
    summary         = Column(Text)
    details_json    = Column(Text, nullable=True)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "strategy_name": self.strategy_name,
            "reflection_type": self.reflection_type,
            "summary": self.summary,
            "details": json.loads(self.details_json) if self.details_json else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class EvolutionLesson(Base):
    __tablename__ = "evolution_lessons"

    id            = Column(Integer, primary_key=True, index=True)
    strategy_name = Column(String, index=True)
    parameter     = Column(String, index=True)
    delta         = Column(Float, nullable=True)
    parent_score  = Column(Float, nullable=True)
    child_score   = Column(Float, nullable=True)
    lesson        = Column(Text)
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "strategy_name": self.strategy_name,
            "parameter": self.parameter,
            "delta": self.delta,
            "parent_score": self.parent_score,
            "child_score": self.child_score,
            "lesson": self.lesson,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class FailedStrategyReason(Base):
    __tablename__ = "failed_strategy_reasons"

    id            = Column(Integer, primary_key=True, index=True)
    strategy_name = Column(String, index=True)
    stage         = Column(String, index=True)
    reason        = Column(Text)
    details_json  = Column(Text, nullable=True)
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "strategy_name": self.strategy_name,
            "stage": self.stage,
            "reason": self.reason,
            "details": json.loads(self.details_json) if self.details_json else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class PipelineCheckpoint(Base):
    __tablename__ = "pipeline_checkpoints"

    id            = Column(Integer, primary_key=True, index=True)
    strategy_name = Column(String, index=True)
    stage         = Column(String, index=True)
    status        = Column(String, index=True)
    message       = Column(Text)
    payload_json  = Column(Text, nullable=True)
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at    = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "strategy_name": self.strategy_name,
            "stage": self.stage,
            "status": self.status,
            "message": self.message,
            "payload": json.loads(self.payload_json) if self.payload_json else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class BatchRun(Base):
    __tablename__ = "batch_runs"

    id = Column(Integer, primary_key=True, index=True)
    count = Column(Integer, default=0)
    tested = Column(Integer, default=0)
    profitable = Column(Integer, default=0)
    losing = Column(Integer, default=0)
    rejected = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    win_rate = Column(Float, nullable=True)
    avg_profit_factor = Column(Float, nullable=True)
    avg_drawdown = Column(Float, nullable=True)
    best_strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=True)
    mode = Column(String, default="mock")
    summary_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "count": self.count,
            "tested": self.tested,
            "profitable": self.profitable,
            "losing": self.losing,
            "rejected": self.rejected,
            "failed": self.failed,
            "win_rate": self.win_rate,
            "avg_profit_factor": self.avg_profit_factor,
            "avg_drawdown": self.avg_drawdown,
            "best_strategy_id": self.best_strategy_id,
            "mode": self.mode,
            "summary": json.loads(self.summary_json) if self.summary_json else [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class OptimizationRun(Base):
    __tablename__ = "optimization_runs"

    id = Column(Integer, primary_key=True, index=True)
    target_win_rate = Column(Float, nullable=True)
    initial_win_rate = Column(Float, nullable=True)
    final_win_rate = Column(Float, nullable=True)
    generations = Column(Integer, default=0)
    best_strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=True)
    mode = Column(String, default="mock")
    batch_size = Column(Integer, default=0)
    improvement = Column(String, nullable=True)
    history_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "target_win_rate": self.target_win_rate,
            "initial_win_rate": self.initial_win_rate,
            "final_win_rate": self.final_win_rate,
            "generations": self.generations,
            "best_strategy_id": self.best_strategy_id,
            "mode": self.mode,
            "batch_size": self.batch_size,
            "improvement": self.improvement,
            "generation_history": json.loads(self.history_json) if self.history_json else [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class StrategyFilter(Base):
    __tablename__ = "strategy_filters"

    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), index=True)
    approved = Column(String, default="false")
    score = Column(Float, nullable=True)
    risk_level = Column(String, nullable=True)
    reasons_json = Column(Text, nullable=True)
    stage = Column(String, default="pre")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "strategy_id": self.strategy_id,
            "approved": str(self.approved).lower() == "true",
            "score": self.score,
            "risk_level": self.risk_level,
            "reasons": json.loads(self.reasons_json) if self.reasons_json else [],
            "stage": self.stage,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class EvolutionHistory(Base):
    __tablename__ = "evolution_history"

    id = Column(Integer, primary_key=True, index=True)
    parent_strategy_id = Column(Integer, ForeignKey("strategies.id"), index=True)
    child_strategy_id = Column(Integer, ForeignKey("strategies.id"), index=True)
    mutation_details_json = Column(Text, nullable=True)
    parent_score = Column(Float, nullable=True)
    child_score = Column(Float, nullable=True)
    improved = Column(String, default="false")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "parent_strategy_id": self.parent_strategy_id,
            "child_strategy_id": self.child_strategy_id,
            "mutation_details": json.loads(self.mutation_details_json) if self.mutation_details_json else {},
            "parent_score": self.parent_score,
            "child_score": self.child_score,
            "improved": str(self.improved).lower() == "true",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Mission(Base):
    __tablename__ = "missions"
    id = Column(Integer, primary_key=True, index=True)
    user_goal = Column(Text)
    status = Column(String, default="pending")  # pending|running|waiting_approval|paused|completed|failed|stopped
    pair = Column(String, default="EURUSD")
    timeframe = Column(String, default="M15")
    plan_json = Column(Text, nullable=True)  # Gemini-generated step plan
    final_strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=True)
    gemini_reasoning = Column(Text, nullable=True)  # latest Gemini reasoning summary
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    steps = relationship("MissionStep", back_populates="mission")
    def as_dict(self):
        return {"id": self.id, "user_goal": self.user_goal, "status": self.status,
                "pair": self.pair, "timeframe": self.timeframe,
                "plan": json.loads(self.plan_json) if self.plan_json else [],
                "final_strategy_id": self.final_strategy_id,
                "gemini_reasoning": self.gemini_reasoning,
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "completed_at": self.completed_at.isoformat() if self.completed_at else None}

class MissionStep(Base):
    __tablename__ = "mission_steps"
    id = Column(Integer, primary_key=True, index=True)
    mission_id = Column(Integer, ForeignKey("missions.id"), index=True)
    step_number = Column(Integer)
    step_name = Column(String)
    status = Column(String, default="pending")  # pending|running|completed|failed|waiting_approval|skipped
    tool_name = Column(String, nullable=True)
    input_json = Column(Text, nullable=True)
    output_json = Column(Text, nullable=True)
    requires_approval = Column(String, default="false")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    mission = relationship("Mission", back_populates="steps")
    def as_dict(self):
        return {"id": self.id, "mission_id": self.mission_id, "step_number": self.step_number,
                "step_name": self.step_name, "status": self.status, "tool_name": self.tool_name,
                "input": json.loads(self.input_json) if self.input_json else None,
                "output": json.loads(self.output_json) if self.output_json else None,
                "requires_approval": str(self.requires_approval).lower() == "true",
                "error_message": self.error_message,
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "completed_at": self.completed_at.isoformat() if self.completed_at else None}

class AgentReasoningLog(Base):
    __tablename__ = "agent_reasoning_logs"
    id = Column(Integer, primary_key=True, index=True)
    mission_id = Column(Integer, ForeignKey("missions.id"), index=True)
    agent_name = Column(String)
    reasoning_summary = Column(Text)
    decision = Column(String, nullable=True)
    next_action = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    def as_dict(self):
        return {"id": self.id, "mission_id": self.mission_id, "agent_name": self.agent_name,
                "reasoning_summary": self.reasoning_summary, "decision": self.decision,
                "next_action": self.next_action, "confidence": self.confidence,
                "created_at": self.created_at.isoformat() if self.created_at else None}

class HumanApproval(Base):
    __tablename__ = "human_approvals"
    id = Column(Integer, primary_key=True, index=True)
    mission_id = Column(Integer, ForeignKey("missions.id"), index=True)
    step_id = Column(Integer, ForeignKey("mission_steps.id"), nullable=True)
    action_description = Column(Text)
    approved = Column(String, default="pending")  # pending|approved|rejected
    approved_by = Column(String, default="human")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    def as_dict(self):
        return {"id": self.id, "mission_id": self.mission_id, "step_id": self.step_id,
                "action_description": self.action_description,
                "approved": self.approved, "approved_by": self.approved_by,
                "notes": self.notes,
                "created_at": self.created_at.isoformat() if self.created_at else None}

class MCPEvent(Base):
    __tablename__ = "mcp_events"
    id = Column(Integer, primary_key=True, index=True)
    mission_id = Column(Integer, ForeignKey("missions.id"), nullable=True, index=True)
    event_type = Column(String)  # save_memory|search|log|observe
    payload_json = Column(Text, nullable=True)
    response_json = Column(Text, nullable=True)
    source = Column(String, default="local")  # local|mongodb|elastic
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    def as_dict(self):
        return {"id": self.id, "mission_id": self.mission_id, "event_type": self.event_type,
                "payload": json.loads(self.payload_json) if self.payload_json else None,
                "response": json.loads(self.response_json) if self.response_json else None,
                "source": self.source,
                "created_at": self.created_at.isoformat() if self.created_at else None}

class StrategyMemory(Base):
    __tablename__ = "strategy_memory"
    id = Column(Integer, primary_key=True, index=True)
    strategy_name = Column(String, index=True)
    pair = Column(String, nullable=True)
    timeframe = Column(String, nullable=True)
    sharpe = Column(Float, nullable=True)
    drawdown = Column(Float, nullable=True)
    win_rate = Column(Float, nullable=True)
    profit_factor = Column(Float, nullable=True)
    risk_status = Column(String, default="unknown")  # approved|rejected|unknown
    mql5_exported = Column(String, default="false")
    mission_id = Column(Integer, ForeignKey("missions.id"), nullable=True)
    tags_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    def as_dict(self):
        return {"id": self.id, "strategy_name": self.strategy_name, "pair": self.pair,
                "timeframe": self.timeframe, "sharpe": self.sharpe, "drawdown": self.drawdown,
                "win_rate": self.win_rate, "profit_factor": self.profit_factor,
                "risk_status": self.risk_status,
                "mql5_exported": str(self.mql5_exported).lower() == "true",
                "mission_id": self.mission_id,
                "tags": json.loads(self.tags_json) if self.tags_json else [],
                "created_at": self.created_at.isoformat() if self.created_at else None}

class ValidationReport(Base):
    __tablename__ = "validation_reports"
    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), index=True)
    validation_type = Column(String)  # monte_carlo|walk_forward|oos
    robustness_score = Column(Float, nullable=True)
    risk_score = Column(Float, nullable=True)
    passed = Column(String, default="false")
    summary = Column(Text, nullable=True)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    def as_dict(self):
        return {"id": self.id, "strategy_id": self.strategy_id,
                "validation_type": self.validation_type,
                "robustness_score": self.robustness_score, "risk_score": self.risk_score,
                "passed": str(self.passed).lower() == "true", "summary": self.summary,
                "details": json.loads(self.details_json) if self.details_json else {},
                "created_at": self.created_at.isoformat() if self.created_at else None}

class ExportedMql5(Base):
    __tablename__ = "exported_mql5_files"
    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), index=True)
    mission_id = Column(Integer, ForeignKey("missions.id"), nullable=True)
    file_path = Column(String)
    approved_by_human = Column(String, default="false")
    gemini_report = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    def as_dict(self):
        return {"id": self.id, "strategy_id": self.strategy_id, "mission_id": self.mission_id,
                "file_path": self.file_path,
                "approved_by_human": str(self.approved_by_human).lower() == "true",
                "gemini_report": self.gemini_report,
                "created_at": self.created_at.isoformat() if self.created_at else None}


class AgentCalibration(Base):
    """Tracks prediction accuracy of each agent over time for dynamic weight adjustment."""
    __tablename__ = "agent_calibration"

    id            = Column(Integer, primary_key=True, index=True)
    agent_name    = Column(String, index=True)
    strategy_name = Column(String, index=True, nullable=True)
    predicted_decision = Column(String)           # approve|reject|needs_retest|needs_evolution
    actual_outcome     = Column(String, nullable=True)  # profitable|unprofitable|neutral (filled after 30d)
    predicted_confidence = Column(Float, nullable=True)
    was_correct   = Column(String, nullable=True)  # true|false|pending
    calibration_score = Column(Float, nullable=True)  # rolling accuracy 0.0-1.0
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at   = Column(DateTime, nullable=True)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "agent_name": self.agent_name,
            "strategy_name": self.strategy_name,
            "predicted_decision": self.predicted_decision,
            "actual_outcome": self.actual_outcome,
            "predicted_confidence": self.predicted_confidence,
            "was_correct": self.was_correct,
            "calibration_score": self.calibration_score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class DebateRecord(Base):
    """Stores Bull vs Bear debate transcripts for strategy decisions."""
    __tablename__ = "debate_records"

    id             = Column(Integer, primary_key=True, index=True)
    strategy_name  = Column(String, index=True)
    bull_score     = Column(Float, nullable=True)
    bear_score     = Column(Float, nullable=True)
    rounds_json    = Column(Text, nullable=True)   # JSON list of round transcripts
    final_verdict  = Column(String, nullable=True)  # bull_wins|bear_wins|draw
    judge_summary  = Column(Text, nullable=True)
    created_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "strategy_name": self.strategy_name,
            "bull_score": self.bull_score,
            "bear_score": self.bear_score,
            "rounds": json.loads(self.rounds_json) if self.rounds_json else [],
            "final_verdict": self.final_verdict,
            "judge_summary": self.judge_summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class WalkForwardResult(Base):
    """Stores walk-forward optimization results for overfitting detection."""
    __tablename__ = "walk_forward_results"

    id              = Column(Integer, primary_key=True, index=True)
    strategy_id     = Column(Integer, ForeignKey("strategies.id"), index=True)
    windows_json    = Column(Text, nullable=True)   # IS/OOS window results
    consistency_score = Column(Float, nullable=True)  # 0-100: how consistent across windows
    is_avg_profit   = Column(Float, nullable=True)
    oos_avg_profit  = Column(Float, nullable=True)
    degradation_pct = Column(Float, nullable=True)  # IS→OOS profit degradation
    passed          = Column(String, default="false")
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "strategy_id": self.strategy_id,
            "windows": json.loads(self.windows_json) if self.windows_json else [],
            "consistency_score": self.consistency_score,
            "is_avg_profit": self.is_avg_profit,
            "oos_avg_profit": self.oos_avg_profit,
            "degradation_pct": self.degradation_pct,
            "passed": str(self.passed).lower() == "true",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
