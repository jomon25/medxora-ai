import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import DatasetEnginePage from "./DatasetEnginePage";

import {
  connectPipelineSocket,
  downloadMql5Url,
  evolveStrategy,
  getAllAgents,
  getHealth,
  getIntegrationSettings,
  getLatestBatch,
  getLogs,
  getPortfolioBestMix,
  getRiskDashboard,
  getStats,
  getStrategy,
  getWinRateStats,
  listBacktests,
  listStrategies,
  optimizeStrategyWinRate,
  runBacktest,
  runBatchTest,
  runFinalPipeline,
  saveIntegrationSettings,
} from "./api";
import {
  startMission, listMissions, getMission, advanceMission, approveStep,
  pauseMission, resumeMission, stopMission, getMcpStatus, createMission, getMissionEvents, exportMQL5,
} from "./api";

const GOLD = "#c99a45";
const GOLD_BRIGHT = "#f4d58d";
const SURFACE = "#11100e";
const TEXT = "#f8f1df";
const TIMEFRAMES = ["M1", "M15", "H1", "H4", "D1", "W1"];
const NAV = [
  ["Command Center", "CC"],
  ["Strategy Lab", "SL"],
  ["Mission Control", "MC"],
  ["Dataset Engine", "DE"],
  ["Evolution Lab", "EV"],
  ["Agent Control Room", "AR"],
  ["Portfolio Optimizer", "PO"],
  ["Risk Center", "RC"],
  ["Logs", "LG"],
  ["Settings", "ST"],
];
const LOCAL_MODEL_DEFAULTS = ["llama3", "qwen2.5"];

function getReactiveTheme(state = "idle") {
  if (state === "profit") {
    return {
      accent: "#22c55e",
      soft: "rgba(34,197,94,.12)",
      border: "rgba(34,197,94,.24)",
      text: "#dcfce7",
      status: "PROFIT MODE",
    };
  }
  if (state === "loss") {
    return {
      accent: "#ef4444",
      soft: "rgba(239,68,68,.12)",
      border: "rgba(239,68,68,.24)",
      text: "#fee2e2",
      status: "RISK MODE",
    };
  }
  return {
    accent: GOLD,
    soft: "rgba(201,154,69,.12)",
    border: "rgba(201,154,69,.24)",
    text: TEXT,
    status: "IDLE MODE",
  };
}

function cn(...classes) {
  return classes.filter(Boolean).join(" ");
}

function hashNumber(value) {
  return [...String(value || "medxora")].reduce((acc, char) => (acc * 31 + char.charCodeAt(0)) % 9973, 17);
}

function formatCurrency(value) {
  if (value == null || Number.isNaN(Number(value))) {
    return "--";
  }
  const num = Number(value);
  const abs = Math.abs(num).toLocaleString(undefined, { maximumFractionDigits: 2 });
  return `${num < 0 ? "-" : ""}$${abs}`;
}

function formatCompact(value) {
  if (value == null || Number.isNaN(Number(value))) {
    return "--";
  }
  return new Intl.NumberFormat("en", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(Number(value));
}

function formatPercent(value) {
  if (value == null || Number.isNaN(Number(value))) {
    return "--";
  }
  return `${Number(value).toFixed(1)}%`;
}

function formatDateTime(value) {
  if (!value) return "--";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "--";
  return parsed.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatMonthYear(value) {
  if (!value) return "--";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "--";
  return parsed.toLocaleString([], {
    month: "short",
    year: "numeric",
  });
}

function formatBacktestRange(startValue, endValue) {
  const start = formatMonthYear(startValue);
  const end = formatMonthYear(endValue);
  if (start === "--" && end === "--") return "--";
  if (start === end) return start;
  if (start === "--") return end;
  if (end === "--") return start;
  return `${start} - ${end}`;
}

function toFiniteNumber(value) {
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

function clampValue(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function computeStrategyEvaluationScore(strategy) {
  const profit = toFiniteNumber(strategy?.netProfit);
  const winRate = toFiniteNumber(strategy?.winRate);
  const drawdown = toFiniteNumber(strategy?.maxDrawdown);
  const profitFactor = toFiniteNumber(strategy?.profitFactor);
  const sharpeRatio = toFiniteNumber(strategy?.sharpeRatio);

  let score = 48;

  score += profit == null ? -10 : clampValue(profit / 1800, -16, 24);
  score += winRate == null ? -5 : clampValue((winRate - 50) * 0.72, -16, 16);
  score += drawdown == null ? -5 : clampValue((18 - drawdown) * 1.18, -20, 16);
  score += profitFactor == null ? -5 : clampValue((profitFactor - 1) * 18, -14, 18);
  score += sharpeRatio == null ? 0 : clampValue(sharpeRatio * 6, -8, 12);

  return Math.round(clampValue(score, 1, 99));
}

function getStrategyEvaluationTier(score) {
  if (score >= 85) {
    return {
      label: "Elite",
      badgeClass: "border-emerald-400/25 bg-emerald-400/12 text-emerald-300",
      meterClass: "bg-emerald-400",
    };
  }
  if (score >= 72) {
    return {
      label: "Strong",
      badgeClass: "border-sky-400/25 bg-sky-400/12 text-sky-300",
      meterClass: "bg-sky-400",
    };
  }
  if (score >= 58) {
    return {
      label: "Watchlist",
      badgeClass: "border-[#f5b342]/25 bg-[#f5b342]/12 text-[#f5d18b]",
      meterClass: "bg-[#f5b342]",
    };
  }
  return {
    label: "Fragile",
    badgeClass: "border-red-400/25 bg-red-400/12 text-red-300",
    meterClass: "bg-red-400",
  };
}

function averageMetric(rows, key) {
  const values = rows
    .map((row) => toFiniteNumber(row?.[key]))
    .filter((value) => value != null);
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function compareStrategyRows(left, right, sortBy) {
  if (sortBy === "profit") return (right.netProfit ?? Number.NEGATIVE_INFINITY) - (left.netProfit ?? Number.NEGATIVE_INFINITY);
  if (sortBy === "winRate") return (right.winRate ?? Number.NEGATIVE_INFINITY) - (left.winRate ?? Number.NEGATIVE_INFINITY);
  if (sortBy === "drawdown") return (left.maxDrawdown ?? Number.POSITIVE_INFINITY) - (right.maxDrawdown ?? Number.POSITIVE_INFINITY);
  if (sortBy === "profitFactor") return (right.profitFactor ?? Number.NEGATIVE_INFINITY) - (left.profitFactor ?? Number.NEGATIVE_INFINITY);
  if (sortBy === "recent") return new Date(right.createdAt || 0).getTime() - new Date(left.createdAt || 0).getTime();
  return (right.evaluationScore ?? Number.NEGATIVE_INFINITY) - (left.evaluationScore ?? Number.NEGATIVE_INFINITY);
}

function getEvolutionBestGeneration(result) {
  const generations = result?.generations || [];
  if (!generations.length) return null;
  return generations.reduce((best, current) => (
    (current?.best_score ?? Number.NEGATIVE_INFINITY) > (best?.best_score ?? Number.NEGATIVE_INFINITY)
      ? current
      : best
  ), generations[0]);
}

function buildEvolutionSnapshot(sourceStrategy, result) {
  if (!result?.evolved && !result?.generations?.length) return null;
  const bestGeneration = getEvolutionBestGeneration(result);
  const metrics = result?.evolved_metrics || bestGeneration?.metrics || {};
  const candidateName = result?.improved
    ? result?.evolved?.name
    : bestGeneration?.best_name || result?.evolved?.name || sourceStrategy?.name;
  return {
    ...normalizeStrategySummary({
      id: sourceStrategy?.id ?? result.evolved.name,
      created_at: new Date().toISOString(),
      name: candidateName,
      symbol: result.evolved.symbol || sourceStrategy?.symbol,
      timeframe: result.evolved.timeframe || sourceStrategy?.timeframe,
      strategy_type: result.evolved.strategy_type || sourceStrategy?.type,
      generation: (sourceStrategy?.generation || 0) + (result.improved ? 1 : 0),
      net_profit: metrics.net_profit ?? sourceStrategy?.netProfit,
      win_rate: metrics.win_rate ?? sourceStrategy?.winRate,
      max_drawdown: metrics.max_drawdown ?? sourceStrategy?.maxDrawdown,
      profit_factor: metrics.profit_factor ?? sourceStrategy?.profitFactor,
      sharpe_ratio: metrics.sharpe_ratio ?? sourceStrategy?.sharpeRatio,
      total_trades: metrics.total_trades ?? sourceStrategy?.totalTrades,
      parameters: result.evolved.parameters || sourceStrategy?.params || {},
    }),
    params: result.evolved.parameters || sourceStrategy?.params || {},
    bestScore: result.best_score ?? null,
  };
}

function mergeEvolutionStrategy(primaryStrategy, fallbackStrategy) {
  if (!primaryStrategy) return fallbackStrategy;
  if (!fallbackStrategy) return primaryStrategy;

  return {
    ...fallbackStrategy,
    ...primaryStrategy,
    params: Object.keys(primaryStrategy.params || {}).length ? primaryStrategy.params : fallbackStrategy.params,
    profit: primaryStrategy.netProfit != null ? primaryStrategy.profit : fallbackStrategy.profit,
    monthlyProfit: primaryStrategy.netProfit != null ? primaryStrategy.monthlyProfit : fallbackStrategy.monthlyProfit,
    yearlyProfit: primaryStrategy.netProfit != null ? primaryStrategy.yearlyProfit : fallbackStrategy.yearlyProfit,
    win: primaryStrategy.winRate != null ? primaryStrategy.win : fallbackStrategy.win,
    dd: primaryStrategy.maxDrawdown != null ? primaryStrategy.dd : fallbackStrategy.dd,
    pf: primaryStrategy.profitFactor != null ? primaryStrategy.pf : fallbackStrategy.pf,
    sharpe: primaryStrategy.sharpeRatio != null ? primaryStrategy.sharpe : fallbackStrategy.sharpe,
    trades: primaryStrategy.totalTrades != null ? primaryStrategy.trades : fallbackStrategy.trades,
    netProfit: primaryStrategy.netProfit ?? fallbackStrategy.netProfit,
    winRate: primaryStrategy.winRate ?? fallbackStrategy.winRate,
    maxDrawdown: primaryStrategy.maxDrawdown ?? fallbackStrategy.maxDrawdown,
    profitFactor: primaryStrategy.profitFactor ?? fallbackStrategy.profitFactor,
    sharpeRatio: primaryStrategy.sharpeRatio ?? fallbackStrategy.sharpeRatio,
    totalTrades: primaryStrategy.totalTrades ?? fallbackStrategy.totalTrades,
    bestScore: primaryStrategy.bestScore ?? fallbackStrategy.bestScore,
  };
}

function formatEvolutionDelta(beforeValue, afterValue, kind = "number", lowerIsBetter = false) {
  const before = toFiniteNumber(beforeValue);
  const after = toFiniteNumber(afterValue);
  if (before == null || after == null) {
    return { label: "--", improved: null };
  }

  const delta = after - before;
  const improved = lowerIsBetter ? delta < 0 : delta > 0;
  const sign = delta > 0 ? "+" : "";

  if (kind === "currency") {
    return {
      label: `${sign}${formatCurrency(delta)}`,
      improved: delta === 0 ? null : improved,
    };
  }

  if (kind === "percent") {
    return {
      label: `${sign}${delta.toFixed(2)}%`,
      improved: delta === 0 ? null : improved,
    };
  }

  return {
    label: `${sign}${delta.toFixed(2)}`,
    improved: delta === 0 ? null : improved,
  };
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function statusTone(value) {
  if (!value) return "text-[#fff7e6]/55";
  const normalized = String(value).toLowerCase();
  if (["approve", "approved", "success", "active", "online", "configured", "healthy", "ready", "completed"].includes(normalized)) {
    return "text-emerald-400";
  }
  if (["reject", "failed", "error", "offline", "missing"].includes(normalized)) {
    return "text-red-400";
  }
  return "text-[#f5b342]";
}

function sparklinePath(values, width = 180, height = 36) {
  if (!values?.length) return "";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(max - min, 1);
  return values
    .map((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * width;
      const y = height - (((value - min) / range) * height);
      return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

function orbitCurvePath(startX, startY, endX, endY, bend = 0.2) {
  const controlX = (startX + endX) / 2;
  const controlY = (startY + endY) / 2;
  const dx = endX - startX;
  const dy = endY - startY;
  const normalX = -dy;
  const normalY = dx;
  const length = Math.hypot(normalX, normalY) || 1;
  const curveX = controlX + ((normalX / length) * 90 * bend);
  const curveY = controlY + ((normalY / length) * 90 * bend);
  return `M ${startX} ${startY} Q ${curveX} ${curveY} ${endX} ${endY}`;
}

function buildSyntheticSeries(strategy) {
  const seed = hashNumber(strategy?.name);
  const annualBase = Number(strategy?.net_profit ?? strategy?.backtest_results?.[0]?.net_profit ?? 0);
  const monthly = Array.from({ length: 12 }, (_, index) => {
    const swing = ((seed + index * 17) % 1900) - 850;
    const drift = annualBase / 14;
    return Math.round(drift + swing);
  });
  const yearly = Array.from({ length: 4 }, (_, index) => Math.round((annualBase || 4000) * (0.58 + index * 0.2)));
  const daily = Array.from({ length: 84 }, (_, index) => {
    const motion = ((seed + index * 13) % 420) - 180;
    return Math.round(monthly[index % monthly.length] / 12 + motion);
  });
  return { monthly, yearly, daily };
}

const MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const WEEKDAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function buildCalendarYears(strategy) {
  const monthly = strategy?.monthlySeries || [];
  const yearly = strategy?.yearlySeries || [];
  const daily = strategy?.dailySeries || [];
  const seed = hashNumber(strategy?.name || "calendar");
  const parsedEnd = strategy?.endDate ? new Date(strategy.endDate) : null;
  const anchorYear = parsedEnd && !Number.isNaN(parsedEnd.getTime()) ? parsedEnd.getFullYear() : new Date().getFullYear();
  const yearCount = Math.max(yearly.length, 4);
  const startYear = anchorYear - yearCount + 1;

  return Array.from({ length: yearCount }, (_, yearIndex) => {
    const year = startYear + yearIndex;
    const monthEntries = MONTH_LABELS.map((label, monthIndex) => {
      const baseMonth = monthly[monthIndex % Math.max(monthly.length, 1)] || 0;
      const yearTarget = yearly[yearIndex] ?? yearly[yearly.length - 1] ?? 0;
      const adjustment = ((seed + yearIndex * 41 + monthIndex * 17) % 420) - 210;
      const monthProfit = Math.round(baseMonth + (yearTarget / 16) + adjustment);
      const daysInMonth = new Date(year, monthIndex + 1, 0).getDate();
      const startOffset = new Date(year, monthIndex, 1).getDay();
      const cells = [];

      for (let offset = 0; offset < startOffset; offset += 1) {
        cells.push(null);
      }

      const dayValues = Array.from({ length: daysInMonth }, (_, dayIndex) => {
        const raw = daily[(yearIndex * 29 + monthIndex * 7 + dayIndex) % Math.max(daily.length, 1)] || 0;
        return Math.round((monthProfit / daysInMonth) + raw / 3.5);
      });
      const currentSum = dayValues.reduce((sum, value) => sum + value, 0);
      if (dayValues.length) {
        dayValues[dayValues.length - 1] += monthProfit - currentSum;
      }

      dayValues.forEach((value, dayIndex) => {
        cells.push({
          day: dayIndex + 1,
          value,
        });
      });

      while (cells.length < 42) {
        cells.push(null);
      }

      return {
        label,
        monthIndex,
        profit: monthProfit,
        cells,
      };
    });

    return {
      year,
      total: monthEntries.reduce((sum, month) => sum + month.profit, 0),
      months: monthEntries,
    };
  });
}

function serviceLabel(service) {
  const status = String(service?.status || "unknown").toLowerCase();
  if (["online", "ready", "configured", "enabled", "healthy", "active"].includes(status)) {
    return "Online";
  }
  if (status === "missing") return "Missing";
  if (status === "offline") return "Offline";
  if (status === "failed") return "Failed";
  return status ? status[0].toUpperCase() + status.slice(1) : "Unknown";
}

function normalizeAgent(agent, index) {
  // category drives colour-coding; role is the agent's actual identifier
  const category = agent.category || _roleToCategory(agent.role) || "core";
  return {
    id: agent.id ?? index + 1,
    name: agent.name || `Agent ${index + 1}`,
    short: (agent.name || `A${index + 1}`)
      .split(" ")
      .map((word) => word[0])
      .join("")
      .slice(0, 2)
      .toUpperCase(),
    file: `${agent.role || "agent"}.py`,
    role: agent.role || category,        // the agent's API identifier (e.g. "risk_manager_agent")
    category,                            // visual group (technical / risk / meta / …)
    score: Math.max(55, Math.round((agent.weight || 0.7) * 100)),
    runs: agent.runs || 0,
    rejected: agent.strategies_rejected || 0,
    status: agent.status || "active",    // "active" | "idle" — real lifecycle status
    description: agent.description || "Watching the pipeline.",
    decision: agent.status || "active",
    capabilities: agent.capabilities || [],
    endpoint: agent.endpoint || "",
    weight: agent.weight || 0.7,
  };
}

const _ROLE_CATEGORY_MAP = {
  risk_manager_agent: "risk", risk_manager: "risk",
  monte_carlo_agent: "quantitative", overfitting_detector_agent: "quantitative",
  slippage_spread_agent: "quantitative", benchmark_comparison_agent: "quantitative",
  market_regime_agent: "technical", technical_indicator_agent: "technical",
  session_performance_agent: "technical", regime_change_detector_agent: "technical",
  bull_researcher_agent: "research", bear_researcher_agent: "research",
  ensemble_voting_agent: "meta", portfolio_manager_agent: "meta",
  correlation_guard_agent: "meta", strategy_retirement_agent: "meta",
  portfolio_rebalancer_agent: "meta", alert_notification_agent: "meta",
  adaptive_risk_agent: "risk", drawdown_recovery_agent: "risk",
  multi_symbol_correlation_agent: "risk",
  sentiment_agent: "intelligence", macro_calendar_agent: "intelligence",
  seasonality_agent: "intelligence",
};

function _roleToCategory(role) {
  return _ROLE_CATEGORY_MAP[role] || null;
}

const AGENT_CATEGORY_STYLES = {
  technical: { color: "#78a8ff", glow: "rgba(120,168,255,.28)" },
  research: { color: "#d891ff", glow: "rgba(216,145,255,.24)" },
  risk: { color: "#ff8b98", glow: "rgba(255,139,152,.24)" },
  quantitative: { color: "#58d7c8", glow: "rgba(88,215,200,.24)" },
  intelligence: { color: "#9aa6ff", glow: "rgba(154,166,255,.24)" },
  meta: { color: "#f2bc68", glow: "rgba(242,188,104,.24)" },
  core: { color: "#f6ddb0", glow: "rgba(246,221,176,.24)" },
};

const DEFAULT_GRAPH_AGENTS = [
  { id: 1, name: "Strategy Creator", category: "technical" },
  { id: 2, name: "Technical Indicator", category: "technical" },
  { id: 3, name: "Bull Researcher", category: "research" },
  { id: 4, name: "Bear Researcher", category: "research" },
  { id: 5, name: "Risk Manager", category: "risk" },
  { id: 6, name: "Monte Carlo", category: "quantitative" },
  { id: 7, name: "Ensemble Voting", category: "meta" },
  { id: 8, name: "Portfolio Rebalancer", category: "meta" },
  { id: 9, name: "Alert Notification", category: "meta" },
  { id: 10, name: "Benchmark Comparison", category: "quantitative" },
  { id: 11, name: "Sentiment Analysis", category: "intelligence" },
  { id: 12, name: "Macro Calendar", category: "intelligence" },
  { id: 13, name: "Market Regime", category: "technical" },
  { id: 14, name: "Drawdown Recovery", category: "risk" },
];

const COMMAND_ORBIT_GROUPS = [
  {
    key: "research",
    title: "RESEARCH & INTELLIGENCE",
    color: "#b36cff",
    accent: "rgba(179,108,255,.24)",
    subtitle: "Research",
    align: "left",
    position: { x: 24, y: 58 },
    labelX: 12,
    items: ["Bear Researcher", "Bull Researcher", "EDB Data Miner"],
  },
  {
    key: "analysis",
    title: "MARKET ANALYSIS",
    color: "#4b88ff",
    accent: "rgba(75,136,255,.24)",
    subtitle: "Technical",
    align: "left",
    position: { x: 96, y: 186 },
    labelX: 70,
    items: ["MTF Analyzer", "Regime Adaptive", "Session Perf", "Indicator Watcher", "Regime Shift Det."],
  },
  {
    key: "optimization",
    title: "OPTIMIZATION & LEARNING",
    color: "#f0b547",
    accent: "rgba(240,181,71,.24)",
    subtitle: "Optimization",
    align: "left",
    position: { x: 34, y: 446 },
    labelX: 18,
    items: ["Corr Guard", "Ensemble Voting", "Portfolio Builder", "Walk-Forward"],
  },
  {
    key: "risk",
    title: "RISK MANAGEMENT",
    color: "#ff5f6d",
    accent: "rgba(255,95,109,.24)",
    subtitle: "Risk",
    align: "right",
    position: { x: 830, y: 54 },
    labelX: 804,
    items: ["DD Recovery", "Risk Manager", "Adapt Risk"],
  },
  {
    key: "execution",
    title: "EXECUTION & OPERATIONS",
    color: "#2fe0ad",
    accent: "rgba(47,224,173,.24)",
    subtitle: "Intelligence",
    align: "right",
    position: { x: 764, y: 214 },
    labelX: 736,
    items: ["Macro Cal", "Seasonal Intel", "Monte Carlo", "Sentiment AI", "News NLP", "Trade Ops"],
  },
  {
    key: "infrastructure",
    title: "INFRASTRUCTURE",
    color: "#57d2ff",
    accent: "rgba(87,210,255,.24)",
    subtitle: "System",
    align: "right",
    position: { x: 834, y: 468 },
    labelX: 808,
    items: ["Overfitting Detect", "Bench Comparator", "Space Optimizer", "Data Core"],
  },
];

const COMMAND_ACTIVITY_FEED = [
  { text: "Monte Carlo simulation completed", time: "2m ago", color: "#2fe0ad" },
  { text: "Risk Manager adjusted exposure", time: "3m ago", color: "#ff5f6d" },
  { text: "News NLP processed 24 headlines", time: "4m ago", color: "#57d2ff" },
  { text: "Regime Shift detected on M15", time: "5m ago", color: "#4b88ff" },
  { text: "Portfolio Optimizer rebalanced", time: "7m ago", color: "#f0b547" },
  { text: "Backtest batch #48 completed", time: "9m ago", color: "#2fe0ad" },
  { text: "Bear Researcher updated insights", time: "11m ago", color: "#b36cff" },
  { text: "DD Recovery routine optimized", time: "13m ago", color: "#ff5f6d" },
];

const COMMAND_OVERVIEW_SEGMENTS = [
  { label: "Research", value: 3, color: "#b36cff" },
  { label: "Analysis", value: 5, color: "#4b88ff" },
  { label: "Risk", value: 3, color: "#ff5f6d" },
  { label: "Execution", value: 6, color: "#2fe0ad" },
  { label: "Optimization", value: 4, color: "#f0b547" },
  { label: "Infrastructure", value: 4, color: "#57d2ff" },
];

function getAgentCategoryStyle(category) {
  return AGENT_CATEGORY_STYLES[category] || AGENT_CATEGORY_STYLES.core;
}

function compactAgentLabel(name) {
  const cleaned = String(name || "Agent")
    .replace(/\bAgent\b/g, "")
    .replace(/\bAnalysis\b/g, "")
    .replace(/\bParameter\b/g, "Params")
    .replace(/\bPerformance\b/g, "Perf")
    .replace(/\bComparison\b/g, "Compare")
    .replace(/\bDetector\b/g, "Detect")
    .replace(/\bRecovery\b/g, "Recover")
    .replace(/\bCalendar\b/g, "Cal")
    .replace(/\bCorrelation\b/g, "Corr")
    .replace(/\bSentiment NLP\b/g, "News NLP")
    .replace(/\bMulti-Timeframe\b/g, "MTF")
    .replace(/\bMulti-Symbol\b/g, "Multi")
    .replace(/\bTechnical Indicator\b/g, "Indicator")
    .replace(/\bPortfolio Manager\b/g, "Portfolio")
    .replace(/\bRegime Change\b/g, "Regime Shift")
    .replace(/\bDrawdown\b/g, "DD")
    .replace(/\bAdaptive Risk\b/g, "Adapt Risk")
    .replace(/\bBenchmark\b/g, "Bench")
    .replace(/\bSeasonality\b/g, "Seasonal")
    .replace(/\bAlert Notification\b/g, "Alerts")
    .replace(/\s+/g, " ")
    .trim();

  if (cleaned.length <= 16) return cleaned;

  const compact = cleaned
    .split(" ")
    .filter(Boolean)
    .map((word, index) => {
      if (index === 0) return word;
      return word.length > 5 ? `${word.slice(0, 4)}.` : word;
    })
    .join(" ");

  return compact.length <= 16 ? compact : compact.slice(0, 16).trim();
}

// eslint-disable-next-line no-unused-vars
function buildAgentNetwork(agents, phase = 0, energetic = false, immersive = false) {
  const source = agents.length
    ? agents
    : DEFAULT_GRAPH_AGENTS.map((agent, index) => normalizeAgent(agent, index));

  const core = { x: 460, y: 310 };
  const bounds = immersive
    ? { left: 44, right: 876, top: 90, bottom: 532 }
    : { left: 74, right: 846, top: 82, bottom: 500 };
  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
  const categoryAnchors = {
    technical: { x: bounds.left + 92, y: bounds.top + 124 },
    research: { x: bounds.right - 112, y: bounds.top + 98 },
    risk: { x: bounds.right - 72, y: bounds.bottom - 156 },
    intelligence: { x: bounds.right - 158, y: bounds.bottom - 66 },
    quantitative: { x: core.x + 12, y: bounds.bottom - 26 },
    meta: { x: bounds.left + 94, y: bounds.bottom - 122 },
    core,
  };
  const protectedRadius = immersive ? 126 : 116;
  const motionScale = energetic ? 1 : immersive ? 0.32 : 0.22;

  const nodes = source.map((agent, index) => {
    const style = getAgentCategoryStyle(agent.category);
    const seed = hashNumber(`${agent.name}-${agent.category}-${index}`);
    const anchor = categoryAnchors[agent.category] || categoryAnchors.core;
    const inwardAngle = Math.atan2(core.y - anchor.y, core.x - anchor.x);
    const spread = immersive ? 1.58 : 1.18;
    const spin = phase * motionScale * (0.02 + ((seed % 9) * 0.002));
    const fan = ((((seed % 1000) / 1000) - 0.5) * spread) + spin;
    const angle = inwardAngle + fan;
    const orbitBase = immersive ? (agent.category === "meta" ? 56 : 72) : agent.category === "meta" ? 26 : 34;
    const orbitRange = immersive ? (agent.category === "meta" ? 164 : 212) : agent.category === "meta" ? 92 : 128;
    const orbitWave = Math.sin(phase * (energetic ? 0.16 : 0.05) + index * 0.85 + (seed % 19)) * (immersive ? (energetic ? 12 : 8) : energetic ? 8 : 3);
    const orbit = orbitBase + ((seed * 13) % orbitRange) + orbitWave;
    const baseDriftX = immersive ? (((seed >> 2) % 26) - 13) : (((seed >> 2) % 18) - 9);
    const baseDriftY = immersive ? (((seed >> 4) % 20) - 10) : (((seed >> 4) % 14) - 7);
    const driftX = baseDriftX + Math.cos(phase * 0.045 + index + (seed % 11)) * (immersive ? 7 : 3) * motionScale;
    const driftY = baseDriftY + Math.sin(phase * 0.05 + index * 0.7 + (seed % 13)) * (immersive ? 6 : 2.5) * motionScale;
    const tangentAngle = angle + (Math.PI / 2);
    const streamWave = Math.sin(phase * (energetic ? 0.11 : 0.038) + index * 0.6 + seed * 0.009) * (immersive ? 8 : 3.5);
    let x = clamp(anchor.x + Math.cos(angle) * orbit + driftX + Math.cos(tangentAngle) * streamWave, bounds.left, bounds.right);
    let y = clamp(anchor.y + Math.sin(angle) * orbit + driftY + Math.sin(tangentAngle) * streamWave, bounds.top, bounds.bottom);
    const dx = x - core.x;
    const dy = y - core.y;
    const radialDistance = Math.hypot(dx, dy) || 1;
    if (radialDistance < protectedRadius) {
      const push = protectedRadius - radialDistance;
      x += (dx / radialDistance) * push;
      y += (dy / radialDistance) * push;
    }
    x = clamp(x, bounds.left, bounds.right);
    y = clamp(y, bounds.top, bounds.bottom);
    const size = 4 + Math.min(8, Math.round((agent.runs || 0) / 120) + Math.round((agent.score - 50) / 25));

    return {
      ...agent,
      x,
      y,
      size,
      seed,
      pulse: (Math.sin(phase * 0.085 + seed * 0.01) + 1) / 2,
      orbitPulse: (Math.cos(phase * 0.06 + seed * 0.008) + 1) / 2,
      satelliteAngle: phase * (energetic ? 0.11 : 0.055) + seed * 0.018,
      color: style.color,
      glow: style.glow,
      label: compactAgentLabel(agent.name),
    };
  });

  const minGapPadding = immersive ? 18 : 8;
  for (let iteration = 0; iteration < (immersive ? 8 : 5); iteration += 1) {
    for (let leftIndex = 0; leftIndex < nodes.length; leftIndex += 1) {
      for (let rightIndex = leftIndex + 1; rightIndex < nodes.length; rightIndex += 1) {
        const left = nodes[leftIndex];
        const right = nodes[rightIndex];
        const dx = right.x - left.x;
        const dy = right.y - left.y;
        const distance = Math.hypot(dx, dy) || 1;
        const minimumDistance = left.size + right.size + minGapPadding;
        if (distance >= minimumDistance) continue;
        const overlap = (minimumDistance - distance) / 2;
        const pushX = (dx / distance) * overlap;
        const pushY = (dy / distance) * overlap;
        left.x -= pushX;
        left.y -= pushY;
        right.x += pushX;
        right.y += pushY;
      }
    }
    nodes.forEach((node) => {
      const dx = node.x - core.x;
      const dy = node.y - core.y;
      const distance = Math.hypot(dx, dy) || 1;
      const minCoreDistance = protectedRadius + node.size + 4;
      if (distance < minCoreDistance) {
        const push = minCoreDistance - distance;
        node.x += (dx / distance) * push;
        node.y += (dy / distance) * push;
      }
      node.x = clamp(node.x, bounds.left, bounds.right);
      node.y = clamp(node.y, bounds.top, bounds.bottom);
    });
  }

  const metaNodes = nodes.filter((node) => node.category === "meta");
  const hubNode = metaNodes[0] || nodes[0];

  const distance = (left, right) => Math.hypot(left.x - right.x, left.y - right.y);
  const edges = [];
  const edgeKey = new Set();

  function link(a, b, strength = "soft") {
    if (!a || !b || a.id === b.id) return;
    const key = [a.id, b.id].sort((left, right) => left - right).join(":");
    if (edgeKey.has(key)) return;
    edgeKey.add(key);
    edges.push({ from: a.id, to: b.id, strength, seed: hashNumber(`edge-${key}`) });
  }

  nodes.forEach((node, index) => {
    if (hubNode && node.id !== hubNode.id) {
      link(node, hubNode, node.category === "meta" ? "strong" : "soft");
    }

    nodes
      .filter((candidate) => candidate.category === node.category && candidate.id !== node.id)
      .sort((left, right) => distance(node, left) - distance(node, right))
      .slice(0, 2)
      .forEach((candidate) => link(node, candidate, "medium"));

    const crossCategory = nodes.find(
      (candidate, candidateIndex) =>
        candidate.category !== node.category &&
        candidate.id !== node.id &&
        ((candidateIndex + index + hashNumber(node.name)) % 7 === 0),
    );

    link(node, crossCategory, "soft");
  });

  return { nodes, edges, hubNode, core };
}

function normalizeStrategySummary(strategy) {
  const synthetic = buildSyntheticSeries(strategy);
  return {
    id: strategy.id,
    createdAt: strategy.created_at || null,
    name: strategy.name,
    symbol: strategy.symbol || "EURUSD",
    timeframe: strategy.timeframe || "M15",
    type: strategy.strategy_type || "strategy",
    generation: strategy.generation || 0,
    status: strategy.net_profit != null ? "Completed" : "Pending",
    profit: formatCurrency(strategy.net_profit),
    monthlyProfit: formatCurrency((strategy.net_profit ?? 0) / 12),
    yearlyProfit: formatCurrency(strategy.net_profit),
    win: formatPercent(strategy.win_rate),
    dd: formatPercent(strategy.max_drawdown),
    pf: strategy.profit_factor != null ? Number(strategy.profit_factor).toFixed(2) : "--",
    sharpe: strategy.sharpe_ratio != null ? Number(strategy.sharpe_ratio).toFixed(2) : "--",
    trades: strategy.total_trades ?? 0,
    params: strategy.parameters || {},
    netProfit: strategy.net_profit,
    winRate: strategy.win_rate,
    maxDrawdown: strategy.max_drawdown,
    profitFactor: strategy.profit_factor,
    sharpeRatio: strategy.sharpe_ratio,
    totalTrades: strategy.total_trades ?? 0,
    monthlySeries: synthetic.monthly,
    yearlySeries: synthetic.yearly,
    dailySeries: synthetic.daily,
  };
}

function normalizeStrategyDetail(detail) {
  const latest = detail?.backtest_results?.[0] || null;
  const synthetic = buildSyntheticSeries(detail);
  return {
    ...normalizeStrategySummary({
      ...detail,
      net_profit: latest?.net_profit,
      win_rate: latest?.win_rate,
      max_drawdown: latest?.max_drawdown,
      profit_factor: latest?.profit_factor,
      parameters: detail.parameters,
    }),
    params: detail.parameters || {},
    mql5Code: detail.mql5_code || "",
    backtests: detail.backtest_results || [],
    initialBalance: latest?.initial_balance,
    startDate: latest?.start_date,
    endDate: latest?.end_date,
    dataSource: latest?.data_source || "EURUSD real tick-derived OHLCV",
    monthlySeries: synthetic.monthly,
    yearlySeries: synthetic.yearly,
    dailySeries: synthetic.daily,
  };
}

function normalizeMissionStrategySnapshot(strategy) {
  if (!strategy) return null;
  const latest = strategy.latest_backtest || {};
  const resolved = {
    ...strategy,
    net_profit: strategy.net_profit ?? latest.net_profit,
    win_rate: strategy.win_rate ?? latest.win_rate,
    max_drawdown: strategy.max_drawdown ?? latest.max_drawdown,
    profit_factor: strategy.profit_factor ?? latest.profit_factor,
    parameters: strategy.parameters || {},
  };
  return {
    ...normalizeStrategySummary(resolved),
    parameters: resolved.parameters || {},
    latestBacktest: latest,
    dataSource: strategy.data_source || latest.data_source || "EURUSD real tick-derived OHLCV",
    grossProfit: strategy.gross_profit ?? latest.gross_profit,
    grossLoss: strategy.gross_loss ?? latest.gross_loss,
    expectedPayoff: strategy.expected_payoff ?? latest.expected_payoff,
    sharpeRatio: strategy.sharpe_ratio ?? latest.sharpe_ratio,
    recoveryFactor: strategy.recovery_factor ?? latest.recovery_factor,
    totalTrades: strategy.total_trades ?? latest.total_trades,
    initialBalance: strategy.initial_balance ?? latest.initial_balance,
    startDate: strategy.start_date ?? latest.start_date,
    endDate: strategy.end_date ?? latest.end_date,
    mql5File: strategy.mql5_file || null,
  };
}

function MedXoraLogo({ size = 40, state = "idle" }) {
  const theme = getReactiveTheme(state);
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="mx-grad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor={theme.accent} />
          <stop offset="100%" stopColor={GOLD_BRIGHT} />
        </linearGradient>
      </defs>
      <rect x="6" y="6" width="88" height="88" rx="22" fill={SURFACE} stroke="url(#mx-grad)" strokeWidth="4" />
      <path d="M24 66 L40 36 L50 54 L60 28 L76 66" stroke="url(#mx-grad)" strokeWidth="4" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="60" cy="28" r="4" fill={theme.accent} />
      <text x="50" y="84" textAnchor="middle" fontSize="10" fill={theme.accent} fontWeight="bold">MX</text>
    </svg>
  );
}

function ShellCard({ children, className = "", state = "idle", onClick }) {
  const theme = getReactiveTheme(state);
  return (
    <div
      onClick={onClick}
      className={cn(
        "rounded-[30px] border bg-[#11100e]/90 shadow-[0_24px_90px_rgba(0,0,0,.42)] backdrop-blur-2xl",
        className,
        onClick ? "cursor-pointer" : "",
      )}
      style={{ borderColor: theme.border, boxShadow: `0 24px 90px rgba(0,0,0,.42), 0 0 28px ${theme.soft}` }}
    >
      {children}
    </div>
  );
}

function StatCard({ label, value, sub, state = "idle", accent = "" }) {
  const theme = getReactiveTheme(state);
  return (
    <ShellCard className="p-5" state={state}>
      <div className="text-[10px] font-semibold uppercase tracking-[.18em] text-[#fff7e6]/42">{label}</div>
      <div className={cn("mt-3 text-2xl font-black", accent || "")} style={!accent ? { color: theme.accent } : undefined}>{value}</div>
      <div className="mt-1 text-xs text-[#fff7e6]/45">{sub}</div>
    </ShellCard>
  );
}

function Toast({ message }) {
  if (!message) return null;
  return (
    <div className="fixed bottom-6 right-6 z-[120] rounded-2xl border border-[#f5b342]/25 bg-[#080501]/92 px-4 py-3 text-sm font-bold text-[#fff7e6] shadow-2xl backdrop-blur-xl">
      {message}
    </div>
  );
}

function SidebarIcon({ code, active = false }) {
  return (
    <div
      className={cn(
        "grid h-9 w-9 place-items-center rounded-xl border text-[11px] font-black tracking-[.18em]",
        active ? "bg-[#f5b342] text-black" : "bg-[#120f0b] text-[#fff7e6]/78",
      )}
      style={{ borderColor: active ? "rgba(245,179,66,.5)" : "rgba(245,179,66,.14)" }}
    >
      {code}
    </div>
  );
}

function PanelHeader({ title, action, tone = "gold" }) {
  const toneColor = tone === "teal" ? "text-[#57d2ff]" : "text-[#f5b342]";
  return (
    <div className="mb-4 flex items-center justify-between gap-3">
      <div className={cn("text-xs font-black uppercase tracking-[.2em]", toneColor)}>{title}</div>
      {action ? <div className="text-[10px] font-black uppercase tracking-[.18em] text-[#fff7e6]/45">{action}</div> : null}
    </div>
  );
}

function Sparkline({ values, color }) {
  return (
    <svg viewBox="0 0 180 36" className="h-9 w-full">
      <path d={sparklinePath(values, 180, 36)} fill="none" stroke={color} strokeWidth="2.2" strokeLinecap="round" />
      <path d={`${sparklinePath(values, 180, 26)} L 180 36 L 0 36 Z`} fill={color} fillOpacity="0.1" />
    </svg>
  );
}

function DonutChart({ segments, total }) {
  const radius = 58;
  const circumference = 2 * Math.PI * radius;
  const segmentOffsets = segments.map((segment) => {
    const offset = segments
      .slice(0, segments.indexOf(segment))
      .reduce((sum, entry) => sum + ((entry.value / total) * circumference) + 4, 0);
    return {
      ...segment,
      offset,
    };
  });

  return (
    <svg viewBox="0 0 180 180" className="h-40 w-40">
      <circle cx="90" cy="90" r={radius} fill="none" stroke="rgba(255,255,255,.06)" strokeWidth="18" />
      {segmentOffsets.map((segment) => {
        const segmentLength = (segment.value / total) * circumference;
        const strokeDasharray = `${segmentLength} ${circumference - segmentLength}`;
        return (
          <circle
            key={segment.label}
            cx="90"
            cy="90"
            r={radius}
            fill="none"
            stroke={segment.color}
            strokeWidth="18"
            strokeDasharray={strokeDasharray}
            strokeDashoffset={-segment.offset}
            transform="rotate(-90 90 90)"
            strokeLinecap="round"
          />
        );
      })}
      <circle cx="90" cy="90" r="44" fill="#0a0907" stroke="rgba(245,179,66,.12)" />
      <text x="90" y="86" textAnchor="middle" fill="#fff7e6" fontSize="32" fontWeight="800">{total}</text>
      <text x="90" y="108" textAnchor="middle" fill="rgba(255,247,230,.55)" fontSize="11" fontWeight="700">TOTAL</text>
    </svg>
  );
}

function HoverSidebar({ page, setPage, health }) {
  return (
    <div className="group fixed inset-y-0 left-0 z-50 w-[12px] transition-[width] duration-300 hover:w-[286px]">
      <div className="pointer-events-none absolute left-2 top-1/2 z-[60] -translate-y-1/2 transition-all duration-300 group-hover:translate-x-[-12px] group-hover:opacity-0">
        <div className="flex h-20 w-6 items-center justify-center rounded-r-full border border-[#f5b342]/18 bg-[linear-gradient(180deg,rgba(20,16,10,.92),rgba(10,8,6,.96))] shadow-[0_0_24px_rgba(245,179,66,.14)]">
          <span className="text-[10px] font-black tracking-[.2em] text-[#f5b342]/80">{">>"}</span>
        </div>
      </div>
      <aside className="absolute inset-y-0 left-0 flex w-[286px] translate-x-[-274px] flex-col overflow-hidden border-r border-[#f5b342]/10 bg-[linear-gradient(180deg,rgba(9,8,6,.96),rgba(6,5,4,.98))] px-4 py-5 text-[#fff7e6] opacity-0 shadow-[30px_0_90px_rgba(0,0,0,.42)] backdrop-blur-xl transition-all duration-300 group-hover:translate-x-0 group-hover:opacity-100">
        <div className="mb-6 flex items-center gap-4">
          <div className="grid h-12 w-12 shrink-0 place-items-center rounded-[16px] border border-[#f5b342]/28 bg-[linear-gradient(180deg,#f2bb48,#d7941f)] shadow-[0_0_32px_rgba(245,179,66,.22)]">
            <MedXoraLogo size={30} />
          </div>
          <div className="min-w-[160px] opacity-0 transition-opacity duration-200 group-hover:opacity-100">
            <div className="text-[17px] font-black tracking-tight">MedXora AI</div>
            <div className="mt-1 text-[11px] font-medium tracking-[.12em] text-[#fff7e6]/52">Elite Agentic Trading System</div>
          </div>
        </div>

        <nav className="space-y-2.5">
          {NAV.map(([name, code]) => {
            const active = page === name;
            return (
              <button
                key={name}
                onClick={() => setPage(name)}
                className={cn(
                  "group flex w-full items-center gap-3 rounded-[18px] border px-3 py-3.5 text-left transition-all duration-200",
                  active
                    ? "bg-[linear-gradient(90deg,rgba(245,179,66,.26),rgba(245,179,66,.08))] shadow-[0_0_26px_rgba(245,179,66,.16)]"
                    : "bg-transparent hover:border-[#f5b342]/22 hover:bg-[#f5b342]/6",
                )}
                style={{ borderColor: active ? "rgba(245,179,66,.42)" : "rgba(245,179,66,.08)" }}
              >
                <SidebarIcon code={code} active={active} />
                <span className={cn("min-w-[124px] flex-1 text-[15px] font-semibold opacity-0 transition-opacity duration-200 group-hover:opacity-100", active ? "text-[#f8e3b2]" : "text-[#fff7e6]/78")}>{name}</span>
                <span className={cn("text-xs font-black tracking-[.18em] opacity-0 transition-opacity duration-200 group-hover:opacity-100", active ? "text-[#f5b342]" : "text-[#fff7e6]/42")}>{code}</span>
              </button>
            );
          })}
        </nav>

        <div className="mt-auto overflow-hidden rounded-[24px] border border-[#f5b342]/14 bg-[linear-gradient(180deg,rgba(10,12,16,.82),rgba(7,8,10,.94))] p-3 shadow-[0_24px_60px_rgba(0,0,0,.32)]">
          <div className="flex items-center justify-center group-hover:justify-start">
            <div className="h-3 w-3 rounded-full bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,.55)]" />
            <div className="ml-3 min-w-[160px] opacity-0 transition-opacity duration-200 group-hover:opacity-100">
              <PanelHeader title="System Status" />
              {[
                ["FastAPI", serviceLabel(health?.services?.backend)],
                ["Database", serviceLabel(health?.services?.database)],
                ["MT5", serviceLabel(health?.services?.mt5_terminal)],
                ["Gemini", serviceLabel(health?.services?.gemini)],
              ].map(([name, status]) => (
                <div key={name} className="flex items-center justify-between py-2 text-sm">
                  <span className="text-[#fff7e6]/66">{name}</span>
                  <span className={cn("font-black uppercase", status === "Online" ? "text-emerald-400" : status === "Missing" ? "text-[#f5b342]" : "text-red-400")}>{status}</span>
                </div>
              ))}
              <div className="mt-3 border-t border-[#f5b342]/10 pt-2 text-xs text-[#fff7e6]/45">
                All systems nominal
              </div>
            </div>
          </div>
        </div>
      </aside>
    </div>
  );
}

// eslint-disable-next-line no-unused-vars
function AgentNetworkGraph({ agents, selectedAgent, onSelectAgent, systemState, stats, isGenerating, graphPhase, immersive = false }) {
  const theme = getReactiveTheme(systemState);
  const core = { x: 488, y: 300 };
  const pulseRing = (Math.sin(graphPhase * 0.075) + 1) / 2;
  const secondaryPulse = (Math.cos(graphPhase * 0.058) + 1) / 2;
  const displayAgentCount = COMMAND_ORBIT_GROUPS.reduce((total, group) => total + group.items.length, 0);
  const strategyCount = stats?.totalStrategies || 107;
  const normalizeAgentKey = (value) => String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  const resolveAgent = (item, group) => {
    const itemKey = normalizeAgentKey(item);
    const match = agents.find((agent) => {
      const nameKey = normalizeAgentKey(agent?.name);
      const roleKey = normalizeAgentKey(agent?.role);
      return nameKey.includes(itemKey) || itemKey.includes(nameKey) || roleKey.includes(itemKey) || itemKey.includes(roleKey);
    });

    return {
      id: match?.id || `${group.key}-${item}`,
      name: item,
      category: group.key,
      role: match?.role || group.subtitle.toLowerCase(),
      file: match?.endpoint || `${group.title} Node`,
      description: match?.description || `${item} supports the ${group.title.toLowerCase()} workflow in the MedXora command center.`,
      score: Math.round((match?.weight || 0.84) * 100),
      runs: match?.runs ?? 0,
      rejected: match?.rejected ?? 0,
      decision: match?.status === "active" ? "Live monitoring" : "Standby",
      status: match?.status || "active",
      capabilities: match?.capabilities || [],
    };
  };

  return (
    <svg viewBox="0 0 920 620" className={cn("h-full w-full", immersive ? "" : "max-w-[1180px]")}>
      <defs>
        <radialGradient id="mx-field" cx="50%" cy="50%" r="58%">
          <stop offset="0%" stopColor={isGenerating ? "rgba(34,197,94,.28)" : "rgba(0,212,255,.24)"} />
          <stop offset="55%" stopColor={isGenerating ? "rgba(20,184,166,.22)" : "rgba(34,211,238,.16)"} />
          <stop offset="100%" stopColor="transparent" />
        </radialGradient>
      </defs>
      <g>
        <rect x="0" y="0" width="920" height="620" rx="36" fill="rgba(4,8,12,.66)" />
        <circle cx={core.x} cy={core.y} r={320} fill="url(#mx-field)" />
        <circle cx={core.x} cy={core.y} r="278" fill="none" stroke="rgba(120,168,255,.08)" strokeDasharray="2 10" />
        <circle cx={core.x} cy={core.y} r="242" fill="none" stroke="rgba(87,210,255,.1)" strokeDasharray="1 12" />
        <circle cx={core.x} cy={core.y} r="206" fill="none" stroke="rgba(179,108,255,.08)" />
        <circle
          cx={core.x}
          cy={core.y}
          r={126 + pulseRing * 20}
          fill="none"
          stroke={isGenerating ? "rgba(52,211,153,.28)" : "rgba(120,168,255,.14)"}
          strokeWidth="1.2"
        />
        <circle
          cx={core.x}
          cy={core.y}
          r={164 + secondaryPulse * 26}
          fill="none"
          stroke={isGenerating ? "rgba(56,189,248,.2)" : "rgba(216,145,255,.12)"}
          strokeWidth="0.9"
        />
        {[0, 1, 2].map((ring) => (
          <circle
            key={ring}
            cx={core.x}
            cy={core.y}
            r={94 + ring * 18}
            fill="none"
            stroke={ring === 0 ? "rgba(46,224,173,.75)" : ring === 1 ? "rgba(87,210,255,.34)" : "rgba(179,108,255,.24)"}
            strokeWidth={ring === 0 ? "2.6" : "1.2"}
          />
        ))}
        <circle cx={core.x} cy={core.y} r="84" fill="rgba(8,12,16,.94)" stroke="rgba(245,179,66,.28)" />
        <text x={core.x} y={core.y - 48} textAnchor="middle" fill={theme.accent} fontSize="34" fontWeight="900">M</text>
        <text x={core.x} y={core.y + 8} textAnchor="middle" fill={theme.accent} fontSize="30" fontWeight="900">MedXora AI</text>
        <text x={core.x} y={core.y + 34} textAnchor="middle" fill="#57f7d4" fontSize="14" fontWeight="700">AI Command Core</text>
        <text x={core.x - 12} y={core.y + 64} textAnchor="end" fill="#2fe0ad" fontSize="11">●</text>
        <text x={core.x} y={core.y + 64} fill="rgba(255,247,230,.72)" fontSize="12">{displayAgentCount} agents active</text>
        <text x={core.x - 12} y={core.y + 86} textAnchor="end" fill="#57d2ff" fontSize="11">◈</text>
        <text x={core.x} y={core.y + 86} fill="rgba(255,247,230,.72)" fontSize="12">{strategyCount} strategies tracked</text>

        {COMMAND_ORBIT_GROUPS.map((group, groupIndex) => {
          const itemGap = 44;
          return (
            <g key={group.key}>
              <text x={group.labelX} y={group.position.y - 24} fill={group.color} fontSize="11" fontWeight="800">
                {group.title}
              </text>
              {group.items.map((item, itemIndex) => {
                const nodeX = group.position.x;
                const nodeY = group.position.y + itemIndex * itemGap;
                const targetAngle = (-140 + (groupIndex * 52) + itemIndex * 8) * (Math.PI / 180);
                const targetRadius = 128 + (itemIndex % 2) * 18;
                const targetX = core.x + Math.cos(targetAngle) * targetRadius;
                const targetY = core.y + Math.sin(targetAngle) * targetRadius;
                const bend = group.align === "left" ? -0.34 : 0.34;
                const active = selectedAgent?.name === item;
                const labelOffset = group.align === "left" ? 26 : 20;
                const titleX = group.align === "left" ? nodeX + labelOffset : nodeX + labelOffset;
                return (
                  <g key={item} onClick={() => onSelectAgent?.(resolveAgent(item, group))} className="cursor-pointer">
                    <path
                      d={orbitCurvePath(nodeX, nodeY, targetX, targetY, bend)}
                      fill="none"
                      stroke={group.color}
                      strokeOpacity={active ? 0.92 : 0.65}
                      strokeWidth={active ? 2 : 1.2}
                    />
                    <circle cx={nodeX} cy={nodeY} r="19" fill={group.accent} />
                    <circle cx={nodeX} cy={nodeY} r="13.5" fill="rgba(10,12,18,.94)" stroke={group.color} strokeWidth="1.5" />
                    <circle cx={nodeX} cy={nodeY} r="7.2" fill={group.color} fillOpacity="0.85" />
                    <circle cx={nodeX} cy={nodeY} r="3.2" fill="#fffef8" fillOpacity="0.92" />
                    <circle cx={targetX} cy={targetY} r="2.2" fill={group.color} fillOpacity="0.92" />
                    <text x={titleX} y={nodeY - 4} fill="#fff7e6" fontSize="11" fontWeight="700">{item}</text>
                    <text x={titleX} y={nodeY + 11} fill="rgba(255,247,230,.48)" fontSize="8.6">{group.subtitle}</text>
                  </g>
                );
              })}
            </g>
          );
        })}
      </g>
    </svg>
  );
}

function EnhancedAgentNetworkGraph({ agents, selectedAgent, onSelectAgent, systemState, stats, isGenerating, graphPhase, immersive = false }) {
  const theme = getReactiveTheme(systemState);
  const core = { x: 492, y: 306 };
  const pulseRing = (Math.sin(graphPhase * 0.075) + 1) / 2;
  const secondaryPulse = (Math.cos(graphPhase * 0.058) + 1) / 2;
  const displayAgentCount = COMMAND_ORBIT_GROUPS.reduce((total, group) => total + group.items.length, 0);
  const strategyCount = stats?.totalStrategies || 107;
  const normalizeAgentKey = (value) => String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  const motionStrength = isGenerating ? 1 : 0;
  const animatedOffset = (seed, amplitudeX, amplitudeY, speed = 0.065) => ({
    x: Math.sin(graphPhase * speed + seed) * amplitudeX * motionStrength,
    y: Math.cos(graphPhase * (speed * 0.82) + seed * 1.4) * amplitudeY * motionStrength,
  });
  const resolveAgent = (item, group) => {
    const itemKey = normalizeAgentKey(item);
    const match = agents.find((agent) => {
      const nameKey = normalizeAgentKey(agent?.name);
      const roleKey = normalizeAgentKey(agent?.role);
      return nameKey.includes(itemKey) || itemKey.includes(nameKey) || roleKey.includes(itemKey) || itemKey.includes(roleKey);
    });

    return {
      id: match?.id || `${group.key}-${item}`,
      name: item,
      category: group.key,
      role: match?.role || group.subtitle.toLowerCase(),
      file: match?.endpoint || `${group.title} Node`,
      description: match?.description || `${item} supports the ${group.title.toLowerCase()} workflow in the MedXora command center.`,
      score: Math.round((match?.weight || 0.84) * 100),
      runs: match?.runs ?? 0,
      rejected: match?.rejected ?? 0,
      decision: match?.status === "active" ? "Live monitoring" : "Standby",
      status: match?.status || "active",
      capabilities: match?.capabilities || [],
    };
  };

  return (
    <svg viewBox="0 0 920 620" className={cn("h-full w-full", immersive ? "scale-[1.06]" : "max-w-[1180px]")}>
      <defs>
        <radialGradient id="mx-field-large" cx="50%" cy="50%" r="60%">
          <stop offset="0%" stopColor={isGenerating ? "rgba(34,197,94,.30)" : "rgba(0,212,255,.26)"} />
          <stop offset="55%" stopColor={isGenerating ? "rgba(20,184,166,.22)" : "rgba(34,211,238,.18)"} />
          <stop offset="100%" stopColor="transparent" />
        </radialGradient>
      </defs>
      <g>
        <rect x="0" y="0" width="920" height="620" rx="36" fill="rgba(4,8,12,.66)" />
        <circle cx={core.x} cy={core.y} r={344} fill="url(#mx-field-large)" />
        <circle cx={core.x} cy={core.y} r="304" fill="none" stroke="rgba(120,168,255,.08)" strokeDasharray="2 10" />
        <circle cx={core.x} cy={core.y} r="266" fill="none" stroke="rgba(87,210,255,.1)" strokeDasharray="1 12" />
        <circle cx={core.x} cy={core.y} r="226" fill="none" stroke="rgba(179,108,255,.08)" />
        <circle
          cx={core.x}
          cy={core.y}
          r={142 + pulseRing * 22}
          fill="none"
          stroke={isGenerating ? "rgba(52,211,153,.28)" : "rgba(120,168,255,.14)"}
          strokeWidth="1.2"
        />
        <circle
          cx={core.x}
          cy={core.y}
          r={186 + secondaryPulse * 28}
          fill="none"
          stroke={isGenerating ? "rgba(56,189,248,.2)" : "rgba(216,145,255,.12)"}
          strokeWidth="0.9"
        />
        {[0, 1, 2].map((ring) => (
          <circle
            key={ring}
            cx={core.x}
            cy={core.y}
            r={108 + ring * 20}
            fill="none"
            stroke={ring === 0 ? "rgba(46,224,173,.75)" : ring === 1 ? "rgba(87,210,255,.34)" : "rgba(179,108,255,.24)"}
            strokeWidth={ring === 0 ? "2.6" : "1.2"}
          />
        ))}
        <circle cx={core.x} cy={core.y} r="94" fill="rgba(8,12,16,.94)" stroke="rgba(245,179,66,.28)" />
        <text x={core.x} y={core.y - 54} textAnchor="middle" fill={theme.accent} fontSize="38" fontWeight="900">M</text>
        <text x={core.x} y={core.y + 10} textAnchor="middle" fill={theme.accent} fontSize="34" fontWeight="900">MedXora AI</text>
        <text x={core.x} y={core.y + 38} textAnchor="middle" fill="#57f7d4" fontSize="15" fontWeight="700">AI Command Core</text>
        <text x={core.x - 12} y={core.y + 70} textAnchor="end" fill="#2fe0ad" fontSize="11">●</text>
        <text x={core.x} y={core.y + 70} fill="rgba(255,247,230,.72)" fontSize="12">{displayAgentCount} agents active</text>
        <text x={core.x - 12} y={core.y + 92} textAnchor="end" fill="#57d2ff" fontSize="11">◈</text>
        <text x={core.x} y={core.y + 92} fill="rgba(255,247,230,.72)" fontSize="12">{strategyCount} strategies tracked</text>

        {COMMAND_ORBIT_GROUPS.map((group, groupIndex) => {
          const itemGap =
            group.key === "research" ? 54 :
            group.key === "analysis" ? 49 :
            group.key === "optimization" ? 46 :
            group.key === "risk" ? 52 :
            group.key === "execution" ? 41 :
            38;
          return (
            <g key={group.key}>
              <text x={group.labelX} y={group.position.y - 24} fill={group.color} fontSize="12" fontWeight="800">
                {group.title}
              </text>
              {group.items.map((item, itemIndex) => {
                const seed = groupIndex * 7 + itemIndex * 1.9;
                const nodeDrift = animatedOffset(seed, group.align === "left" ? 6 : 5, 9, 0.09);
                const anchorDrift = animatedOffset(seed + 0.6, 8, 10, 0.075);
                const lateralSpread =
                  group.align === "left"
                    ? group.key === "analysis"
                      ? (itemIndex % 2 === 0 ? -4 : 18)
                      : group.key === "optimization"
                        ? (itemIndex % 2 === 0 ? 6 : 24)
                        : (itemIndex % 2 === 0 ? 0 : 18)
                    : group.key === "execution"
                      ? (itemIndex % 2 === 0 ? 0 : 18)
                      : group.key === "infrastructure"
                        ? (itemIndex % 2 === 0 ? -6 : 14)
                        : (itemIndex % 2 === 0 ? 0 : 14);
                const nodeX = group.position.x + lateralSpread + nodeDrift.x;
                const nodeY = group.position.y + itemIndex * itemGap + nodeDrift.y;
                const targetAngle = (-140 + (groupIndex * 52) + itemIndex * 8) * (Math.PI / 180);
                const targetRadius = 146 + (itemIndex % 2) * 18;
                const targetX = core.x + Math.cos(targetAngle) * targetRadius + anchorDrift.x;
                const targetY = core.y + Math.sin(targetAngle) * targetRadius + anchorDrift.y;
                const bend = group.align === "left" ? -0.34 : 0.34;
                const active = selectedAgent?.name === item;
                const labelOffset = group.align === "left" ? 24 : 16;
                const titleX = nodeX + labelOffset;
                const compactLabel = compactAgentLabel(item);
                return (
                  <g key={item} onClick={() => onSelectAgent?.(resolveAgent(item, group))} className="cursor-pointer">
                    <path
                      d={orbitCurvePath(nodeX, nodeY, targetX, targetY, bend)}
                      fill="none"
                      stroke={group.color}
                      strokeOpacity={active ? 0.92 : isGenerating ? 0.82 : 0.65}
                      strokeWidth={active ? 2 : isGenerating ? 1.45 : 1.2}
                    />
                    <circle cx={nodeX} cy={nodeY} r={isGenerating ? "22" : "21"} fill={group.accent} />
                    <circle cx={nodeX} cy={nodeY} r="14.5" fill="rgba(10,12,18,.94)" stroke={group.color} strokeWidth="1.6" />
                    <circle cx={nodeX} cy={nodeY} r="7.8" fill={group.color} fillOpacity="0.85" />
                    <circle cx={nodeX} cy={nodeY} r="3.4" fill="#fffef8" fillOpacity="0.92" />
                    <circle cx={targetX} cy={targetY} r={isGenerating ? "2.8" : "2.2"} fill={group.color} fillOpacity="0.92" />
                    <text x={titleX} y={nodeY + 4} fill={group.color} fontSize="10.8" fontWeight="700">{compactLabel}</text>
                  </g>
                );
              })}
            </g>
          );
        })}
      </g>
    </svg>
  );
}

function AgentDrawer({ agent, onClose, systemState, floating = true, className = "" }) {
  if (!agent) return null;
  const theme = getReactiveTheme(systemState);
  return (
    <div
      className={cn(
        "rounded-[30px] border border-[#f5b342]/25 bg-[#080501]/95 p-5 text-[#fff7e6] shadow-[0_30px_100px_rgba(0,0,0,.55)] backdrop-blur-2xl",
        floating ? "absolute right-6 top-24 z-[85] w-[420px]" : "w-full",
        className,
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <div className="text-[10px] font-black uppercase tracking-[.22em] text-[#f5b342]">Agent Inspector</div>
          <h3 className="mt-2 text-2xl font-black">{agent.name}</h3>
          <p className="mt-1 text-xs text-[#fff7e6]/45">{agent.file} · {agent.role}</p>
        </div>
        <button onClick={onClose} className="rounded-xl border border-[#f5b342]/20 bg-[#f5b342]/10 px-3 py-2 text-xs font-black text-[#f5b342]">Close</button>
      </div>
            <div className="mt-5 rounded-2xl border border-[#f5b342]/15 bg-[#f5b342]/8 p-4 text-sm text-[#fff7e6]/70">{agent.description}</div>
      <div className="mt-4 grid grid-cols-3 gap-3 text-center text-xs">
        <div className="rounded-2xl bg-[#f5b342]/8 p-3"><b className="block text-lg text-[#f5b342]">{agent.score}%</b>Score</div>
        <div className="rounded-2xl bg-[#f5b342]/8 p-3"><b className="block text-lg text-[#f5b342]">{agent.runs}</b>Runs</div>
        <div className="rounded-2xl bg-red-500/10 p-3"><b className="block text-lg text-red-400">{agent.rejected}</b>Reject</div>
      </div>
      <div className="mt-5 space-y-3 text-sm">
        <div className="rounded-2xl border border-[#f5b342]/10 bg-black/30 px-4 py-3 text-[#fff7e6]/65">Decision state: {agent.decision}</div>
        <div className="rounded-2xl border border-[#f5b342]/10 bg-black/30 px-4 py-3 text-[#fff7e6]/65">Pipeline role: {agent.role}</div>
        <div className="rounded-2xl border border-[#f5b342]/10 bg-black/30 px-4 py-3 text-[#fff7e6]/65" style={{ color: theme.text }}>Status: {agent.status}</div>
        {agent.capabilities?.length ? (
          <div className="rounded-2xl border border-[#f5b342]/10 bg-black/30 px-4 py-3 text-[#fff7e6]/65">
            Capabilities: {agent.capabilities.slice(0, 4).join(", ")}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function StatusPillCard({ title, value, tone = "teal" }) {
  const palette = tone === "gold"
    ? { dot: "#f5b342", glow: "rgba(245,179,66,.32)" }
    : { dot: "#2fe0ad", glow: "rgba(47,224,173,.28)" };

  return (
    <div className="min-w-[184px] rounded-[20px] border border-[#f5b342]/14 bg-[linear-gradient(180deg,rgba(10,12,14,.88),rgba(9,10,12,.94))] px-4 py-3 shadow-[0_0_26px_rgba(0,0,0,.22)]">
      <div className="flex items-center gap-3">
        <span className="h-10 w-10 rounded-2xl border border-white/6" style={{ background: `radial-gradient(circle at 40% 40%, ${palette.glow}, rgba(11,14,18,.9))` }}>
          <span className="mx-auto mt-[14px] block h-3 w-3 rounded-full" style={{ backgroundColor: palette.dot, boxShadow: `0 0 14px ${palette.dot}` }} />
        </span>
        <div>
          <div className="text-[10px] font-black uppercase tracking-[.18em] text-[#fff7e6]/42">{title}</div>
          <div className="mt-1 text-sm font-black uppercase tracking-[.08em]" style={{ color: palette.dot }}>{value}</div>
        </div>
      </div>
    </div>
  );
}

function LiveActivityFeedCard() {
  return (
    <ShellCard className="rounded-[24px] p-4">
      <PanelHeader title="Live Activity Feed" action="View All" />
      <div className="space-y-2.5">
        {COMMAND_ACTIVITY_FEED.map((item) => (
          <div key={item.text} className="flex items-start gap-3 text-[13px]">
            <span className="mt-1.5 h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.color, boxShadow: `0 0 12px ${item.color}` }} />
            <div className="min-w-0 flex-1 text-[#fff7e6]/78">{item.text}</div>
            <div className="text-xs text-[#fff7e6]/36">{item.time}</div>
          </div>
        ))}
      </div>
    </ShellCard>
  );
}

function AgentOverviewCard({ totalAgents }) {
  return (
    <ShellCard className="rounded-[24px] p-4">
      <PanelHeader title="Agent Overview" action={`${totalAgents} Active`} />
      <div className="flex items-center gap-4">
        <div className="scale-[.88] origin-left">
          <DonutChart segments={COMMAND_OVERVIEW_SEGMENTS} total={totalAgents} />
        </div>
        <div className="flex-1 space-y-2.5 text-[13px]">
          {COMMAND_OVERVIEW_SEGMENTS.map((segment) => (
            <div key={segment.label} className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: segment.color }} />
                <span className="text-[#fff7e6]/68">{segment.label}</span>
              </div>
              <span className="text-[#fff7e6]/52">{segment.value} ({Math.round((segment.value / totalAgents) * 100)}%)</span>
            </div>
          ))}
        </div>
      </div>
    </ShellCard>
  );
}

function PerformanceSummaryCard() {
  const perfItems = [
    { label: "Win Rate", value: "68.42%", color: "#2fe0ad", values: [34, 38, 36, 44, 46, 51, 49, 57, 60, 68] },
    { label: "Profit Factor", value: "2.18", color: "#2fe0ad", values: [1.2, 1.3, 1.28, 1.42, 1.39, 1.54, 1.68, 1.75, 1.96, 2.18] },
    { label: "Avg. R Multiple", value: "1.86", color: "#57d2ff", values: [0.8, 0.92, 1.02, 1.18, 1.1, 1.36, 1.44, 1.62, 1.7, 1.86] },
    { label: "Max Drawdown", value: "7.31%", color: "#ff5f6d", values: [12, 10, 11, 9.5, 8.8, 8.2, 8.7, 7.9, 7.4, 7.31] },
  ];

  return (
    <ShellCard className="rounded-[24px] p-4">
      <PanelHeader title="Performance Summary" action="30D" />
      <div className="grid gap-3 sm:grid-cols-2">
        {perfItems.map((item) => (
          <div key={item.label} className="rounded-[20px] border border-[#f5b342]/10 bg-black/22 p-3">
            <div className="text-[10px] font-black uppercase tracking-[.18em] text-[#fff7e6]/42">{item.label}</div>
            <div className="mt-1.5 text-xl font-black" style={{ color: item.color }}>{item.value}</div>
            <div className="mt-2">
              <Sparkline values={item.values} color={item.color} />
            </div>
          </div>
        ))}
      </div>
    </ShellCard>
  );
}

function KpiSummaryCard({ title, value, sub, color, values }) {
  return (
    <ShellCard className="rounded-[20px] border-[#f5b342]/10 bg-[linear-gradient(180deg,rgba(11,12,15,.92),rgba(8,9,12,.98))] p-3">
      <div className="flex items-start justify-between gap-2.5">
        <div className="grid h-8 w-8 place-items-center rounded-lg border border-white/6" style={{ background: `radial-gradient(circle at 35% 35%, ${color}33, rgba(9,12,16,.95))` }}>
          <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color, boxShadow: `0 0 14px ${color}` }} />
        </div>
        <div className="text-right">
          <div className="text-[10px] font-black uppercase tracking-[.18em] text-[#fff7e6]/40">{title}</div>
          <div className="mt-1 text-[22px] font-black leading-none" style={{ color }}>{value}</div>
          <div className="mt-0.5 text-xs text-[#fff7e6]/56">{sub}</div>
        </div>
      </div>
      <div className="mt-2">
        <Sparkline values={values} color={color} />
      </div>
    </ShellCard>
  );
}

function CommandCenter({
  timeframe,
  setTimeframe,
  systemState,
  stats,
  health,
  agents,
  selectedAgent,
  setSelectedAgent,
  busyLabel,
  pipelineConnected,
  mockMode,
  onRunPipeline,
  onRunBatch,
  onOptimize,
  latestBatch,
  optimizerResult,
  isGenerating,
  graphPhase,
}) {
  const displayAgentCount = COMMAND_ORBIT_GROUPS.reduce((total, group) => total + group.items.length, 0);
  const kpiCards = [
    { title: "Strategies", value: String(stats?.total_strategies || 107), sub: "Tracked", color: "#b36cff", values: [82, 88, 84, 91, 95, 90, 94, 98, 103, 107] },
    { title: "Backtests", value: String(stats?.total_backtests || 523), sub: "Completed", color: "#4b88ff", values: [360, 388, 396, 418, 405, 436, 452, 470, 497, 523] },
    { title: "Profitable", value: String(stats?.profitable_strategies || 68), sub: "12.96%", color: "#2fe0ad", values: [36, 41, 38, 47, 52, 49, 55, 57, 63, 68] },
    { title: "Best Profit", value: formatCurrency(stats?.best_net_profit ?? 68927.89), sub: "Champion", color: "#f0b547", values: [18000, 22000, 21000, 34000, 32000, 47000, 43000, 58000, 61000, 68927.89] },
    { title: "Agents", value: String(displayAgentCount), sub: "Active", color: "#57d2ff", values: [14, 17, 16, 19, 21, 20, 22, 23, 24, displayAgentCount] },
    { title: "Batch", value: `${latestBatch?.profitable ?? 15} / ${latestBatch?.tested ?? 100}`, sub: "Profitable", color: "#4b88ff", values: [4, 5, 6, 5, 8, 9, 8, 12, 13, 15] },
    { title: "Optimizer", value: optimizerResult?.final_win_rate ? `${optimizerResult.final_win_rate.toFixed(1)}%` : "--", sub: "Win rate", color: "#b36cff", values: [32, 35, 34, 38, 36, 41, 44, 48, 53, 58] },
  ];
  const healthValue = health?.services?.backend?.status === "online" && health?.services?.database?.status === "online" ? "Excellent" : "Degraded";
  const liveModeValue = pipelineConnected ? "Active" : mockMode ? "Active" : "Standby";

  return (
    <div className="relative h-screen overflow-hidden bg-[#050403] px-2 text-[#fff7e6]">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_42%_26%,rgba(37,99,235,.08),transparent_28%),radial-gradient(circle_at_60%_38%,rgba(34,211,238,.08),transparent_34%),linear-gradient(180deg,#060504,#070707)]" />
      <div className="relative z-20 flex h-screen w-full flex-col gap-2.5 overflow-hidden px-2 py-3">
        <ShellCard className="rounded-[26px] border-[#f5b342]/12 bg-[linear-gradient(180deg,rgba(13,11,8,.96),rgba(11,10,8,.88))] p-3">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex min-w-0 flex-1 flex-wrap items-center gap-3">
              <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} className="rounded-[16px] border border-[#f5b342]/20 bg-[#0e0d0b] px-4 py-2.5 text-sm font-black text-[#f5b342] shadow-[inset_0_0_0_1px_rgba(245,179,66,.02)]">
                {TIMEFRAMES.map((tf) => (<option key={tf}>{tf}</option>))}
              </select>
              <button
                onClick={onRunPipeline}
                disabled={Boolean(busyLabel)}
                className="rounded-[16px] border border-[#f5b342]/26 px-5 py-2.5 text-sm font-black text-[#2b1700] shadow-[0_0_38px_rgba(245,179,66,.24)] transition hover:brightness-110 disabled:opacity-50"
                style={{ background: "linear-gradient(135deg,#f2bb48,#b77616)" }}
              >
                {isGenerating ? "Generating Strategy..." : "Generate Strategy"}
              </button>
              <button onClick={onRunBatch} disabled={Boolean(busyLabel)} className="rounded-[16px] border border-[#f5b342]/16 bg-[#0d0c0a] px-5 py-2.5 text-sm font-black text-[#fff7e6]/82 transition hover:border-[#f5b342]/26 hover:bg-[#f5b342]/6 disabled:opacity-50">Run 100 Batch Test</button>
              <button onClick={onOptimize} disabled={Boolean(busyLabel)} className="rounded-[16px] border border-[#f5b342]/16 bg-[#0d0c0a] px-5 py-2.5 text-sm font-black text-[#fff7e6]/82 transition hover:border-[#f5b342]/26 hover:bg-[#f5b342]/6 disabled:opacity-50">Optimize Win Rate</button>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <StatusPillCard title="System Health" value={healthValue} tone="gold" />
              <StatusPillCard title="Live Mode" value={liveModeValue} tone="teal" />
            </div>
          </div>
        </ShellCard>

        <div className="min-h-0 flex-1">
          <ShellCard className="relative flex h-full min-h-0 min-w-0 flex-col overflow-hidden rounded-[28px] border-[#f5b342]/12 bg-[linear-gradient(180deg,rgba(11,12,14,.98),rgba(8,8,10,.92))] p-3.5">
            <PanelHeader title="Agent Orbit" />
            <div className="relative mt-2.5 min-h-0 flex-1 overflow-hidden rounded-[26px] border border-[#f5b342]/12 bg-[linear-gradient(180deg,rgba(6,10,14,.94),rgba(5,8,10,.98))]">
              <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_42%,rgba(87,210,255,.12),transparent_30%),radial-gradient(circle_at_50%_50%,rgba(47,224,173,.10),transparent_50%)]" />
              <EnhancedAgentNetworkGraph
                agents={agents}
                selectedAgent={selectedAgent}
                onSelectAgent={setSelectedAgent}
                systemState={systemState}
                stats={{ totalStrategies: stats?.total_strategies }}
                isGenerating={isGenerating}
                graphPhase={graphPhase}
                immersive
              />
              {selectedAgent ? (
                <AgentDrawer
                  agent={selectedAgent}
                  onClose={() => setSelectedAgent(null)}
                  systemState={systemState}
                  className="right-4 top-4 w-[360px] border-[#f5b342]/18 bg-[#080501]/88 p-4"
                />
              ) : null}
            </div>
          </ShellCard>
        </div>

        <div className="grid shrink-0 gap-2 xl:grid-cols-7">
          {kpiCards.map((card) => (
            <KpiSummaryCard key={card.title} {...card} />
          ))}
        </div>
      </div>

      <div className="group/right fixed inset-y-0 right-0 z-[70] w-[28px] transition-[width] duration-300 hover:w-[352px]">
        <div className="absolute right-2 top-1/2 z-[80] -translate-y-1/2 transition-all duration-300 group-hover/right:translate-x-[12px] group-hover/right:opacity-0">
          <div className="flex h-20 w-6 items-center justify-center rounded-l-full border border-[#f5b342]/18 bg-[linear-gradient(180deg,rgba(20,16,10,.92),rgba(10,8,6,.96))] shadow-[0_0_24px_rgba(245,179,66,.14)]">
            <span className="text-[10px] font-black tracking-[.2em] text-[#f5b342]/80">{"<<"}</span>
          </div>
        </div>
        <div className="absolute bottom-[102px] right-0 top-[96px] flex w-[352px] translate-x-[320px] flex-col gap-2.5 px-2 opacity-0 transition-all duration-300 group-hover/right:translate-x-0 group-hover/right:opacity-100">
          <LiveActivityFeedCard />
          <AgentOverviewCard totalAgents={displayAgentCount} />
          <PerformanceSummaryCard />
        </div>
      </div>
    </div>
  );
}

function PageShell({ title, subtitle, children, action }) {
  return (
    <div className="space-y-5">
      <ShellCard className="p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-xs font-black uppercase tracking-[.22em] text-[#f5b342]">MedXora AI</div>
            <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">{title}</h1>
            <p className="mt-2 max-w-3xl text-sm text-[#fff7e6]/52 sm:text-base">{subtitle}</p>
          </div>
          {action}
        </div>
      </ShellCard>
      {children}
    </div>
  );
}

function StrategyDetailsModal({
  strategy,
  loading,
  onClose,
  onBacktest,
  onEvolve,
  onOpenEvaluation,
  mockMode,
  contextLabel = "Strategy Lab",
  showActions = true,
}) {
  const calendarYears = useMemo(() => buildCalendarYears(strategy), [strategy]);
  const [selectedCalendarYear, setSelectedCalendarYear] = useState(null);
  const resolvedCalendarYear = calendarYears.some((entry) => entry.year === selectedCalendarYear)
    ? selectedCalendarYear
    : calendarYears[calendarYears.length - 1]?.year ?? null;

  const activeCalendarYear =
    calendarYears.find((entry) => entry.year === resolvedCalendarYear) ||
    calendarYears[calendarYears.length - 1] ||
    null;

  if (!strategy && !loading) return null;

  return (
    <div className="fixed inset-0 z-[90] bg-black/75 p-5 backdrop-blur-md">
      <div className="mx-auto h-full max-w-[1500px] overflow-y-auto rounded-[30px] border border-[#f5b342]/25 bg-[#080501] p-6 text-[#fff7e6] shadow-[0_30px_100px_rgba(0,0,0,.55)]">
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <button onClick={onClose} className="mb-4 text-xs font-black uppercase tracking-[.2em] text-[#f5b342]">
              {`<- Back to ${contextLabel}`}
            </button>
            <h2 className="text-3xl font-black">{strategy?.name || "Loading..."}</h2>
            <p className="mt-1 text-sm text-[#fff7e6]/45">
              {strategy?.symbol || "EURUSD"} · {strategy?.timeframe || "M15"} · {strategy?.type || "strategy"}
            </p>
          </div>
          {strategy && showActions && (
            <div className="flex gap-2">
              <button onClick={() => onBacktest(strategy.name)} className="rounded-xl border border-[#f5b342]/20 bg-[#f5b342]/10 px-4 py-2 text-xs font-black text-[#f5b342]">{mockMode ? "Mock Backtest" : "Real Backtest"}</button>
              <button onClick={() => onEvolve(strategy.name)} className="rounded-xl border border-[#f5b342]/20 bg-[#f5b342]/10 px-4 py-2 text-xs font-black text-[#f5b342]">Evolve</button>
              <button onClick={() => onOpenEvaluation?.(strategy)} className="rounded-xl border border-sky-400/20 bg-sky-400/10 px-4 py-2 text-xs font-black text-sky-300">Evaluation</button>
              <a href={downloadMql5Url(strategy.name)} className="rounded-xl bg-[#f5b342] px-4 py-2 text-xs font-black text-black">Export .mq5</a>
            </div>
          )}
        </div>

        {loading || !strategy ? (
          <div className="flex h-[60vh] items-center justify-center text-lg font-black text-[#f5b342]">Loading strategy detail...</div>
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
              <StatCard label="Net Profit" value={strategy.profit} sub="total P&L" state="profit" />
              <StatCard label="Start Balance" value={formatCurrency(strategy.initialBalance)} sub="mission backtest" />
              <StatCard label="Backtest Window" value={formatBacktestRange(strategy.startDate, strategy.endDate)} sub="dataset period" />
              <StatCard label="Win Rate" value={strategy.win} sub="closed trades" />
              <StatCard label="Max DD" value={strategy.dd} sub="drawdown" state="loss" />
            </div>

            <div className="mt-5 grid gap-5 xl:grid-cols-2">
              <ShellCard className="p-5">
                <h3 className="mb-4 text-lg font-black">Strategy Parameters</h3>
                <div className="grid gap-3 sm:grid-cols-2">
                  {Object.entries(strategy.params || {}).map(([key, value]) => (
                    <div key={key} className="rounded-2xl bg-[#f5b342]/8 p-4">
                      <div className="text-[10px] font-black uppercase tracking-wide text-[#fff7e6]/40">{key}</div>
                      <div className="mt-1 text-xl font-black text-[#f5b342]">{String(value)}</div>
                    </div>
                  ))}
                </div>
              </ShellCard>

              <ShellCard className="p-5">
                <h3 className="mb-4 text-lg font-black">Backtest History</h3>
                <div className="space-y-3">
                  {(strategy.backtests || []).slice(0, 6).map((backtest) => (
                    <div key={backtest.id} className="rounded-2xl border border-[#f5b342]/10 bg-[#f5b342]/8 p-4 text-sm">
                      <div className="flex items-center justify-between">
                        <b>{formatCurrency(backtest.net_profit)}</b>
                        <span className="text-[#fff7e6]/45">{formatPercent(backtest.win_rate)}</span>
                      </div>
                      <div className="mt-2 flex gap-4 text-xs text-[#fff7e6]/55">
                        <span>DD {formatPercent(backtest.max_drawdown)}</span>
                        <span>PF {backtest.profit_factor?.toFixed?.(2) || "--"}</span>
                        <span>Trades {backtest.total_trades || 0}</span>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-4 text-xs text-[#fff7e6]/45">
                        <span>Balance {formatCurrency(backtest.initial_balance)}</span>
                        <span>Dataset {formatBacktestRange(backtest.start_date, backtest.end_date)}</span>
                        <span>Saved {formatMonthYear(backtest.created_at)}</span>
                      </div>
                    </div>
                  ))}
                  {!strategy.backtests?.length && <div className="text-sm text-[#fff7e6]/45">No backtest records yet.</div>}
                </div>
              </ShellCard>
            </div>

            <ShellCard className="mt-5 p-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h3 className="text-lg font-black">Profit & Loss Calendar View</h3>
                  <p className="mt-1 text-sm text-[#fff7e6]/45">
                    Switch the year to review the yearly profit and monthly profit pattern for this strategy.
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {calendarYears.map((entry) => (
                    <button
                      key={entry.year}
                      onClick={() => setSelectedCalendarYear(entry.year)}
                      className={cn(
                        "rounded-xl border px-3 py-2 text-xs font-black transition",
                        activeCalendarYear?.year === entry.year
                          ? "border-[#f5b342]/35 bg-[#f5b342] text-black"
                          : "border-[#f5b342]/16 bg-[#f5b342]/8 text-[#f5d18b] hover:bg-[#f5b342]/12",
                      )}
                    >
                      {entry.year}
                    </button>
                  ))}
                </div>
              </div>

              {activeCalendarYear ? (
                <>
                  <div className="mt-5 grid gap-4 md:grid-cols-3">
                    <div className="rounded-2xl border border-emerald-400/16 bg-emerald-400/8 p-4">
                      <div className="text-[10px] font-black uppercase tracking-[.18em] text-[#d0fbe5]/45">Yearly Profit</div>
                      <div className={cn("mt-2 text-xl font-black", activeCalendarYear.total >= 0 ? "text-emerald-300" : "text-red-300")}>
                        {formatCurrency(activeCalendarYear.total)}
                      </div>
                    </div>
                    <div className="rounded-2xl border border-[#f5b342]/12 bg-[#f5b342]/8 p-4">
                      <div className="text-[10px] font-black uppercase tracking-[.18em] text-[#fff7e6]/38">Average Monthly Profit</div>
                      <div className={cn("mt-2 text-xl font-black", activeCalendarYear.total >= 0 ? "text-emerald-300" : "text-red-300")}>
                        {formatCurrency(activeCalendarYear.total / 12)}
                      </div>
                    </div>
                    <div className="rounded-2xl border border-[#f5b342]/12 bg-[#f5b342]/8 p-4">
                      <div className="text-[10px] font-black uppercase tracking-[.18em] text-[#fff7e6]/38">Backtest Window</div>
                      <div className="mt-2 text-xl font-black text-[#f5b342]">{formatBacktestRange(strategy.startDate, strategy.endDate)}</div>
                    </div>
                  </div>

                  <div className="mt-5 grid gap-4 xl:grid-cols-3">
                    {activeCalendarYear.months.map((month) => (
                      <div key={`${activeCalendarYear.year}-${month.monthIndex}`} className="rounded-[24px] border border-[#f5b342]/10 bg-[#120f0b]/88 p-4">
                        <div className="flex items-center justify-between gap-3">
                          <div className="text-sm font-black text-[#fff7e6]">{month.label} {activeCalendarYear.year}</div>
                          <div className={cn("text-sm font-black", month.profit >= 0 ? "text-emerald-300" : "text-red-300")}>
                            {formatCurrency(month.profit)}
                          </div>
                        </div>
                        <div className="mt-3 grid grid-cols-7 gap-1 text-[10px] uppercase tracking-[.12em] text-[#fff7e6]/28">
                          {WEEKDAY_LABELS.map((day) => (
                            <div key={`${month.label}-${day}`} className="text-center">{day.slice(0, 1)}</div>
                          ))}
                        </div>
                        <div className="mt-2 grid grid-cols-7 gap-1">
                          {month.cells.map((cell, index) => (
                            <div
                              key={`${month.label}-${index}`}
                              className={cn(
                                "min-h-[44px] rounded-xl border p-1.5 text-[10px]",
                                !cell ? "border-transparent bg-transparent" : "",
                                cell?.value > 0 ? "border-emerald-400/14 bg-emerald-400/10 text-emerald-200" : "",
                                cell?.value < 0 ? "border-red-400/14 bg-red-400/10 text-red-200" : "",
                                cell?.value === 0 ? "border-white/8 bg-white/5 text-[#fff7e6]/55" : "",
                              )}
                            >
                              {cell ? (
                                <>
                                  <div className="font-black text-[#fff7e6]/72">{cell.day}</div>
                                  <div className="mt-1 font-semibold">
                                    {cell.value >= 0 ? "+" : ""}{Math.round(cell.value)}
                                  </div>
                                </>
                              ) : null}
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              ) : null}
            </ShellCard>

            <ShellCard className="mt-5 p-5">
              <h3 className="mb-4 text-lg font-black">MQL5 Preview</h3>
              <pre className="max-h-[420px] overflow-auto rounded-2xl bg-black/40 p-4 text-xs text-[#fff7e6]/80">{strategy.mql5Code || "No generated MQL5 code available."}</pre>
            </ShellCard>
          </>
        )}
      </div>
    </div>
  );
}

function StrategyLab({ strategies, selectedStrategy, detailLoading, onOpenStrategy, onCloseStrategy, onRunPipeline, onBacktest, onEvolve, onOpenEvaluation, mockMode }) {
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("All");
  const [sortBy, setSortBy] = useState("score");
  const deferredQuery = useDeferredValue(query);

  const evaluatedStrategies = useMemo(
    () => strategies.map((strategy) => {
      const evaluationScore = computeStrategyEvaluationScore(strategy);
      const tier = getStrategyEvaluationTier(evaluationScore);
      const searchable = [strategy.name, strategy.symbol, strategy.timeframe, strategy.type, strategy.status]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return {
        ...strategy,
        evaluationScore,
        evaluationTier: tier.label,
        evaluationBadgeClass: tier.badgeClass,
        evaluationMeterClass: tier.meterClass,
        searchable,
        isProfitable: (strategy.netProfit ?? 0) > 0,
        isStable: (strategy.maxDrawdown ?? Number.POSITIVE_INFINITY) <= 12 && (strategy.profitFactor ?? 0) >= 1.4,
      };
    }),
    [strategies],
  );

  const filteredStrategies = useMemo(() => {
    const normalizedQuery = deferredQuery.trim().toLowerCase();
    return evaluatedStrategies
      .filter((strategy) => {
        const matchesQuery = !normalizedQuery || strategy.searchable.includes(normalizedQuery);
        const matchesFilter =
          statusFilter === "All" ||
          (statusFilter === "Completed" && strategy.status === "Completed") ||
          (statusFilter === "Profitable" && strategy.isProfitable) ||
          (statusFilter === "Stable" && strategy.isStable) ||
          (statusFilter === "Pending" && strategy.status === "Pending");
        return matchesQuery && matchesFilter;
      })
      .sort((left, right) => compareStrategyRows(left, right, sortBy));
  }, [deferredQuery, evaluatedStrategies, sortBy, statusFilter]);

  const topStrategies = filteredStrategies.slice(0, 18);
  const averageScore = averageMetric(filteredStrategies, "evaluationScore");
  const averageWinRate = averageMetric(filteredStrategies, "winRate");
  const averageDrawdown = averageMetric(filteredStrategies, "maxDrawdown");
  const strongestStrategy = filteredStrategies[0] || null;
  return (
    <PageShell
      title="Strategy Lab"
      subtitle="Live strategy inventory from the backend, presented in your custom UI."
      action={<button onClick={onRunPipeline} className="rounded-xl bg-[#f5b342] px-4 py-2 text-xs font-black text-black">+ Generate Strategy</button>}
    >
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard label="Total" value={String(strategies.length)} sub="generated" />
        <StatCard label="Profitable" value={String(strategies.filter((item) => (item.netProfit || 0) > 0).length)} sub="validated" state="profit" />
        <StatCard label="Pending" value={String(strategies.filter((item) => item.netProfit == null).length)} sub="queue" />
        <StatCard label="Best" value={strategies[0]?.profit || "--"} sub={strategies[0]?.name || "champion"} state="profit" />
        <StatCard label="Types" value={String(new Set(strategies.map((item) => item.type)).size)} sub="variants" />
      </div>

      <ShellCard className="overflow-hidden p-5">
        <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-black">Strategy Evaluation Board</h2>
            <p className="mt-1 text-xs text-[#fff7e6]/45">Review the strongest candidates, compare risk against return, and open any row for the full strategy profile.</p>
          </div>
          <div className="rounded-xl border border-[#f5b342]/20 bg-[#f5b342]/10 px-4 py-2 text-xs font-black text-[#f5b342]">
            {topStrategies.length} of {filteredStrategies.length} visible
          </div>
        </div>

        <div className="grid gap-3 border-y border-[#f5b342]/10 py-4 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-[22px] border border-white/8 bg-white/5 p-4">
            <div className="text-[10px] font-black uppercase tracking-[.18em] text-[#fff7e6]/35">Average Score</div>
            <div className="mt-2 text-2xl font-black text-[#f5b342]">{averageScore != null ? Math.round(averageScore) : "--"}</div>
            <div className="mt-1 text-xs text-[#fff7e6]/45">Across the current filtered set</div>
          </div>
          <div className="rounded-[22px] border border-white/8 bg-white/5 p-4">
            <div className="text-[10px] font-black uppercase tracking-[.18em] text-[#fff7e6]/35">Average Win Rate</div>
            <div className="mt-2 text-2xl font-black text-emerald-300">{averageWinRate != null ? formatPercent(averageWinRate) : "--"}</div>
            <div className="mt-1 text-xs text-[#fff7e6]/45">Closed-trade strike rate</div>
          </div>
          <div className="rounded-[22px] border border-white/8 bg-white/5 p-4">
            <div className="text-[10px] font-black uppercase tracking-[.18em] text-[#fff7e6]/35">Average Drawdown</div>
            <div className="mt-2 text-2xl font-black text-red-300">{averageDrawdown != null ? formatPercent(averageDrawdown) : "--"}</div>
            <div className="mt-1 text-xs text-[#fff7e6]/45">Current risk pressure</div>
          </div>
          <div className="rounded-[22px] border border-white/8 bg-white/5 p-4">
            <div className="text-[10px] font-black uppercase tracking-[.18em] text-[#fff7e6]/35">Top Candidate</div>
            <div className="mt-2 truncate text-base font-black text-[#fff7e6]">{strongestStrategy?.name || "--"}</div>
            <div className="mt-1 text-xs text-[#fff7e6]/45">
              {strongestStrategy ? `${strongestStrategy.profit} / score ${strongestStrategy.evaluationScore}` : "No matching strategy"}
            </div>
          </div>
        </div>

        <div className="mt-5 flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex flex-1 flex-col gap-3 md:flex-row">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search by strategy, symbol, timeframe, or type"
              className="min-w-0 flex-1 rounded-2xl border border-[#f5b342]/20 bg-black/30 px-4 py-3 text-sm text-[#fff7e6] outline-none transition focus:border-[#f5b342]/50 focus:bg-black/45"
            />
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
              className="rounded-2xl border border-[#f5b342]/20 bg-black/30 px-4 py-3 text-sm font-semibold text-[#fff7e6] outline-none transition focus:border-[#f5b342]/50"
            >
              {["All", "Completed", "Profitable", "Stable", "Pending"].map((option) => (
                <option key={option}>{option}</option>
              ))}
            </select>
            <select
              value={sortBy}
              onChange={(event) => setSortBy(event.target.value)}
              className="rounded-2xl border border-[#f5b342]/20 bg-black/30 px-4 py-3 text-sm font-semibold text-[#fff7e6] outline-none transition focus:border-[#f5b342]/50"
            >
              <option value="score">Best score</option>
              <option value="profit">Highest profit</option>
              <option value="winRate">Highest win rate</option>
              <option value="drawdown">Lowest drawdown</option>
              <option value="profitFactor">Best profit factor</option>
              <option value="recent">Most recent</option>
            </select>
          </div>
          <div className="rounded-2xl border border-[#57d2ff]/20 bg-[#57d2ff]/10 px-4 py-3 text-xs font-black uppercase tracking-[.18em] text-[#9de7ff]">
            Ranked by evaluation confidence
          </div>
        </div>

        <div className="mt-5 overflow-hidden rounded-[26px] border border-[#f5b342]/10 bg-black/20">
          <div className="overflow-x-auto">
            <table className="min-w-[1220px] w-full text-left text-sm">
              <thead className="sticky top-0 z-10 bg-[#16120b]/96 text-[11px] uppercase tracking-[.18em] text-[#fff7e6]/45 backdrop-blur">
                <tr>
                  {["Rank", "Strategy", "Evaluation", "Performance", "Risk", "Edge", "Momentum", "Status"].map((header) => (
                    <th key={header} className="border-b border-[#f5b342]/10 px-4 py-4 font-black">{header}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {topStrategies.map((row, index) => (
                  <tr
                    key={row.id}
                    onClick={() => onOpenStrategy(row.id)}
                    className="cursor-pointer border-b border-[#f5b342]/10 align-top transition hover:bg-[#f5b342]/8"
                  >
                    <td className="px-4 py-4">
                      <div className="flex flex-col gap-2">
                        <div className="text-base font-black text-[#f5b342]">#{index + 1}</div>
                        <div className="text-[11px] uppercase tracking-[.16em] text-[#fff7e6]/35">Gen {row.generation ?? 0}</div>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <div className="max-w-[280px]">
                        <div className="truncate text-sm font-black text-[#fff7e6]">{row.name}</div>
                        <div className="mt-1 text-xs text-[#fff7e6]/42">{row.symbol} / {row.timeframe} / {row.type}</div>
                        <div className="mt-3 inline-flex rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-semibold text-[#fff7e6]/65">
                          Saved {formatDateTime(row.createdAt)}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <div className="min-w-[180px]">
                        <div className="flex items-center justify-between gap-3">
                          <span className={cn("rounded-full border px-3 py-1 text-[11px] font-black uppercase tracking-[.16em]", row.evaluationBadgeClass)}>
                            {row.evaluationTier}
                          </span>
                          <span className="text-lg font-black text-[#fff7e6]">{row.evaluationScore}</span>
                        </div>
                        <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/8">
                          <div className={cn("h-full rounded-full", row.evaluationMeterClass)} style={{ width: `${row.evaluationScore}%` }} />
                        </div>
                        <div className="mt-2 text-xs text-[#fff7e6]/45">Weighted from profit, win rate, drawdown, and efficiency</div>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <div className="space-y-2">
                        <div className={cn("text-base font-black", (row.netProfit ?? 0) >= 0 ? "text-emerald-300" : "text-red-300")}>{row.profit}</div>
                        <div className="text-xs text-[#fff7e6]/48">Win rate {row.win}</div>
                        <div className="text-xs text-[#fff7e6]/48">Monthly avg {row.monthlyProfit}</div>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <div className="space-y-2">
                        <div className="text-base font-black text-red-300">{row.dd}</div>
                        <div className="text-xs text-[#fff7e6]/48">Trades {formatCompact(row.totalTrades)}</div>
                        <div className="text-xs text-[#fff7e6]/48">{row.isStable ? "Controlled profile" : "Needs monitoring"}</div>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <div className="space-y-2">
                        <div className="text-base font-black text-[#fff7e6]">PF {row.pf}</div>
                        <div className="text-xs text-[#fff7e6]/48">Sharpe {row.sharpe}</div>
                        <div className="text-xs text-[#fff7e6]/48">
                          {row.profitFactor != null && row.profitFactor >= 1.5 ? "Healthy edge" : "Thin edge"}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <div className="min-w-[150px]">
                        <Sparkline values={row.monthlySeries.slice(-8)} color={(row.netProfit ?? 0) >= 0 ? "#2fe0ad" : "#ff7d7d"} />
                        <div className="mt-2 text-xs text-[#fff7e6]/45">Recent synthetic monthly curve</div>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex flex-col gap-2">
                        <span className={cn(
                          "w-fit rounded-full border px-3 py-1 text-[11px] font-black uppercase tracking-[.16em]",
                          row.status === "Completed"
                            ? "border-emerald-400/25 bg-emerald-400/12 text-emerald-300"
                            : "border-[#f5b342]/25 bg-[#f5b342]/10 text-[#f5d18b]",
                        )}>
                          {row.status}
                        </span>
                        <span className="text-xs text-[#fff7e6]/45">Open details</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {!topStrategies.length ? (
            <div className="px-6 py-10 text-center text-sm text-[#fff7e6]/55">
              No strategies match the current search and filter combination.
            </div>
          ) : null}
        </div>
      </ShellCard>

      {(selectedStrategy || detailLoading) && (
        <StrategyDetailsModal
          strategy={selectedStrategy}
          loading={detailLoading}
          onClose={onCloseStrategy}
          onBacktest={onBacktest}
          onEvolve={onEvolve}
          onOpenEvaluation={onOpenEvaluation}
          mockMode={mockMode}
        />
      )}
    </PageShell>
  );
}

function AgentRoom({ agents }) {
  const [query, setQuery] = useState("");
  const [role, setRole] = useState("All");
  const [selected, setSelected] = useState(null);
  const roles = ["All", ...Array.from(new Set(agents.map((agent) => agent.category)))];
  const filtered = agents.filter((agent) => {
    const roleMatch = role === "All" || agent.category === role;
    const queryMatch = agent.name.toLowerCase().includes(query.toLowerCase()) || agent.file.toLowerCase().includes(query.toLowerCase());
    return roleMatch && queryMatch;
  });
  const avgScore = Math.round(filtered.reduce((sum, agent) => sum + agent.score, 0) / Math.max(filtered.length, 1));
  const totalRuns = filtered.reduce((sum, agent) => sum + agent.runs, 0);
  const totalRejected = filtered.reduce((sum, agent) => sum + agent.rejected, 0);

  return (
    <PageShell title="Agent Control Room" subtitle="Live agent registry, filtered and surfaced through the custom UI.">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Agents" value={String(filtered.length)} sub="active" />
        <StatCard label="Avg Score" value={`${avgScore}%`} sub="quality" />
        <StatCard label="Total Runs" value={formatCompact(totalRuns)} sub="executions" />
        <StatCard label="Rejected" value={formatCompact(totalRejected)} sub="filtered" state="loss" />
      </div>

      <ShellCard className="p-5">
        <div className="flex flex-wrap items-center gap-3">
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search agent or file..." className="min-w-[260px] flex-1 rounded-xl border border-[#f5b342]/20 bg-black/40 px-4 py-2 text-sm outline-none" />
          <select value={role} onChange={(event) => setRole(event.target.value)} className="rounded-xl border border-[#f5b342]/20 bg-black/40 px-3 py-2 text-sm text-[#f5b342]">
            {roles.map((item) => <option key={item}>{item}</option>)}
          </select>
        </div>
      </ShellCard>

      <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
        {filtered.map((agent) => (
          <ShellCard key={agent.id} className="p-5 transition hover:scale-[1.01]" onClick={() => setSelected(agent)}>
            <div className="flex items-start justify-between">
              <div className="grid h-12 w-12 place-items-center rounded-2xl bg-[#f5b342]/12 text-sm font-black text-[#f5b342]">{agent.short}</div>
              <span className="rounded-full border border-[#f5b342]/25 bg-[#f5b342]/10 px-3 py-1 text-xs font-black text-[#f5b342]">Active</span>
            </div>
            <div className="mt-5 text-lg font-black">{agent.name}</div>
            <div className="mt-1 text-sm text-[#fff7e6]/50">{agent.file} · {agent.role}</div>
            <div className="mt-4 rounded-2xl bg-[#f5b342]/8 p-3 text-sm text-[#fff7e6]/70">{agent.description}</div>
            <div className="mt-4 grid grid-cols-3 gap-3 text-center text-xs">
              <div className="rounded-2xl bg-[#f5b342]/8 p-3"><b className="block text-lg text-[#f5b342]">{agent.score}%</b>Score</div>
              <div className="rounded-2xl bg-[#f5b342]/8 p-3"><b className="block text-lg text-[#f5b342]">{agent.runs}</b>Runs</div>
              <div className="rounded-2xl bg-red-500/10 p-3"><b className="block text-lg text-red-400">{agent.rejected}</b>Reject</div>
            </div>
          </ShellCard>
        ))}
      </div>

      {selected && <AgentDrawer agent={selected} onClose={() => setSelected(null)} systemState="idle" />}
    </PageShell>
  );
}

function EvolutionLab({ champion, strategies, selectedEvolutionStrategy, evolutionResult, onSelectEvolutionStrategy, onEvolve, optimizeResult, busyLabel }) {
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);

  const activeStrategy = selectedEvolutionStrategy || champion || null;
  const evolvedSnapshot = useMemo(
    () => evolutionResult?.evolvedStrategy || buildEvolutionSnapshot(activeStrategy, evolutionResult),
    [activeStrategy, evolutionResult],
  );

  const strategyOptions = useMemo(() => {
    const normalizedQuery = deferredQuery.trim().toLowerCase();
    return strategies
      .filter((strategy) => {
        if (!normalizedQuery) return true;
        return [strategy.name, strategy.symbol, strategy.timeframe, strategy.type]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(normalizedQuery);
      })
      .slice(0, 12);
  }, [deferredQuery, strategies]);

  const lineage = useMemo(() => {
    if (evolutionResult?.generations?.length) {
      let parentName = evolutionResult.original || activeStrategy?.name || "Original";
      return evolutionResult.generations.map((generation) => {
        const entry = {
          parent: parentName,
          child: generation.best_name,
          score: generation.best_score,
        };
        parentName = generation.best_name;
        return entry;
      });
    }
    if (!activeStrategy) return [];
    const seed = hashNumber(activeStrategy.name);
    return Array.from({ length: 3 }, (_, index) => ({
      parent: index === 0 ? activeStrategy.name : `${activeStrategy.name.slice(0, -4)}${String((seed + index) % 9999).padStart(4, "0")}`,
      child: `${activeStrategy.name.slice(0, -4)}${String((seed + index + 11) % 9999).padStart(4, "0")}`,
      score: null,
    }));
  }, [activeStrategy, evolutionResult]);

  const beforeScore = activeStrategy ? computeStrategyEvaluationScore(activeStrategy) : null;
  const afterScore = evolvedSnapshot ? computeStrategyEvaluationScore(evolvedSnapshot) : null;

  const comparisonCards = [
    {
      label: "Net Profit",
      before: activeStrategy?.profit || "--",
      after: evolvedSnapshot?.profit || "--",
      delta: formatEvolutionDelta(activeStrategy?.netProfit, evolvedSnapshot?.netProfit, "currency"),
    },
    {
      label: "Win Rate",
      before: activeStrategy?.win || "--",
      after: evolvedSnapshot?.win || "--",
      delta: formatEvolutionDelta(activeStrategy?.winRate, evolvedSnapshot?.winRate, "percent"),
    },
    {
      label: "Max Drawdown",
      before: activeStrategy?.dd || "--",
      after: evolvedSnapshot?.dd || "--",
      delta: formatEvolutionDelta(activeStrategy?.maxDrawdown, evolvedSnapshot?.maxDrawdown, "percent", true),
    },
    {
      label: "Profit Factor",
      before: activeStrategy?.pf || "--",
      after: evolvedSnapshot?.pf || "--",
      delta: formatEvolutionDelta(activeStrategy?.profitFactor, evolvedSnapshot?.profitFactor),
    },
  ];

  return (
    <PageShell title="Evolution Lab" subtitle="Search for a strategy to evolve, review its performance first, and compare it with the evolved result after evaluation.">
      <div className="grid gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
        <ShellCard className="p-6">
          <h2 className="text-xl font-black">Search Strategy To Evolve</h2>
          <p className="mt-2 text-sm text-[#fff7e6]/52">Pick any saved strategy here, or jump from Strategy Lab using the Evaluation button.</p>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search strategy, symbol, timeframe..."
            className="mt-5 w-full rounded-2xl border border-[#f5b342]/20 bg-black/30 px-4 py-3 text-sm text-[#fff7e6] outline-none transition focus:border-[#f5b342]/50"
          />

          <div className="mt-5 space-y-3">
            {strategyOptions.map((strategy) => (
              <button
                key={strategy.id}
                onClick={() => onSelectEvolutionStrategy(strategy)}
                className={cn(
                  "w-full rounded-[22px] border px-4 py-4 text-left transition",
                  activeStrategy?.id === strategy.id
                    ? "border-[#f5b342]/32 bg-[#f5b342]/12"
                    : "border-[#f5b342]/10 bg-[#f5b342]/6 hover:bg-[#f5b342]/10",
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-black text-[#fff7e6]">{strategy.name}</div>
                    <div className="mt-1 text-xs text-[#fff7e6]/45">{strategy.symbol} / {strategy.timeframe} / {strategy.type}</div>
                  </div>
                  <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[10px] font-black uppercase tracking-[.16em] text-[#fff7e6]/65">
                    Gen {strategy.generation || 0}
                  </span>
                </div>
                <div className="mt-3 flex flex-wrap gap-3 text-xs text-[#fff7e6]/55">
                  <span>{strategy.profit}</span>
                  <span>Win {strategy.win}</span>
                  <span>PF {strategy.pf}</span>
                </div>
              </button>
            ))}
            {!strategyOptions.length ? (
              <div className="rounded-[22px] border border-dashed border-[#f5b342]/16 bg-[#f5b342]/6 p-4 text-sm text-[#fff7e6]/55">
                No strategies matched your search.
              </div>
            ) : null}
          </div>
        </ShellCard>

        <div className="space-y-6">
          <ShellCard className="p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2 className="text-xl font-black">Evaluation Overview</h2>
                <p className="mt-2 text-sm text-[#fff7e6]/52">See how the strategy performed before evolution, then compare it with the evolved output after evaluation.</p>
              </div>
              <button
                onClick={() => activeStrategy && onEvolve(activeStrategy)}
                disabled={!activeStrategy || Boolean(busyLabel)}
                className="rounded-xl bg-[#f5b342] px-5 py-3 text-sm font-black text-black disabled:opacity-50"
              >
                {busyLabel ? "Evolution Running..." : "Run Evolution"}
              </button>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <StatCard label="Selected Strategy" value={activeStrategy?.name || "--"} sub={activeStrategy ? `${activeStrategy.symbol} / ${activeStrategy.timeframe}` : "choose a strategy"} />
              <StatCard label="Before Score" value={beforeScore != null ? String(beforeScore) : "--"} sub="pre-evolution" />
              <StatCard label="After Score" value={afterScore != null ? String(afterScore) : "--"} sub={evolutionResult ? (evolutionResult.improved ? "improved result" : "no improvement") : "waiting for evolution"} state={evolutionResult?.improved ? "profit" : "idle"} />
              <StatCard label="Optimizer" value={optimizeResult?.final_win_rate ? `${optimizeResult.final_win_rate.toFixed(1)}%` : "--"} sub="latest win-rate tune" state="profit" />
            </div>

            {evolutionResult?.evaluation ? (
              <div className="mt-5 rounded-[24px] border border-violet-400/16 bg-violet-400/8 p-5">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <div className="text-[10px] font-black uppercase tracking-[.18em] text-violet-200/70">Evaluation Source</div>
                    <div className="mt-2 text-lg font-black text-[#fff7e6]">
                      {evolutionResult.evaluation.provider} / {evolutionResult.evaluation.target}
                    </div>
                  </div>
                  <div className="rounded-full border border-white/10 bg-black/20 px-3 py-1 text-[11px] font-black uppercase tracking-[.16em] text-[#fff7e6]/65">
                    Logged in backend logs
                  </div>
                </div>
                <div className="mt-4 text-sm leading-6 text-[#f4ecff]">
                  {evolutionResult.evaluation.advice?.summary || "Evaluation details are available in the logs."}
                </div>
              </div>
            ) : null}

            <div className="mt-6 grid gap-4 xl:grid-cols-2">
              <div className="rounded-[24px] border border-[#f5b342]/12 bg-[#f5b342]/8 p-5">
                <div className="text-[10px] font-black uppercase tracking-[.18em] text-[#fff7e6]/35">Before Evaluation</div>
                <div className="mt-3 text-xl font-black text-[#fff7e6]">{activeStrategy?.name || "Select a strategy"}</div>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  {comparisonCards.map((item) => (
                    <div key={`before-${item.label}`} className="rounded-2xl border border-white/8 bg-black/20 p-3">
                      <div className="text-[10px] uppercase tracking-[.18em] text-[#fff7e6]/35">{item.label}</div>
                      <div className="mt-1 text-sm font-black text-[#fff7e6]">{item.before}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-[24px] border border-emerald-400/14 bg-emerald-400/8 p-5">
                <div className="text-[10px] font-black uppercase tracking-[.18em] text-[#d0fbe5]/45">After Evaluation</div>
                <div className="mt-3 text-xl font-black text-[#fff7e6]">{evolvedSnapshot?.name || "Run evolution to compare"}</div>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  {comparisonCards.map((item) => (
                    <div key={`after-${item.label}`} className="rounded-2xl border border-white/8 bg-black/20 p-3">
                      <div className="text-[10px] uppercase tracking-[.18em] text-[#fff7e6]/35">{item.label}</div>
                      <div className="mt-1 text-sm font-black text-[#fff7e6]">{item.after}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="mt-6 rounded-[24px] border border-sky-400/14 bg-sky-400/8 p-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="text-[10px] font-black uppercase tracking-[.18em] text-sky-200/70">Comparison Summary</div>
                  <div className="mt-2 text-lg font-black text-[#fff7e6]">Before vs After Evaluation</div>
                </div>
                <div className="rounded-full border border-white/10 bg-black/20 px-3 py-1 text-[11px] font-black uppercase tracking-[.16em] text-[#fff7e6]/70">
                  {evolutionResult ? (evolutionResult.improved ? "Improved" : "No Improvement") : "Waiting"}
                </div>
              </div>

              <div className="mt-5 overflow-hidden rounded-2xl border border-white/8 bg-black/20">
                <div className="grid grid-cols-[minmax(0,1.2fr)_minmax(120px,.8fr)_minmax(120px,.8fr)_110px_110px] gap-3 border-b border-white/8 px-4 py-3 text-[11px] font-black uppercase tracking-[.16em] text-[#fff7e6]/42">
                  <div>Metric</div>
                  <div>Before</div>
                  <div>After</div>
                  <div>Change</div>
                  <div>Verdict</div>
                </div>
                {comparisonCards.map((item) => (
                  <div key={`compare-${item.label}`} className="grid grid-cols-[minmax(0,1.2fr)_minmax(120px,.8fr)_minmax(120px,.8fr)_110px_110px] gap-3 border-b border-white/8 px-4 py-3 text-sm last:border-b-0">
                    <div className="font-black text-[#fff7e6]">{item.label}</div>
                    <div className="text-[#fff7e6]/72">{item.before}</div>
                    <div className="text-[#fff7e6]/72">{item.after}</div>
                    <div className={cn(
                      "font-black",
                      item.delta.improved == null
                        ? "text-[#fff7e6]/55"
                        : item.delta.improved
                          ? "text-emerald-300"
                          : "text-red-300",
                    )}>
                      {item.delta.label}
                    </div>
                    <div>
                      <span className={cn(
                        "rounded-full border px-3 py-1 text-[10px] font-black uppercase tracking-[.16em]",
                        item.delta.improved == null
                          ? "border-white/10 bg-white/5 text-[#fff7e6]/55"
                          : item.delta.improved
                            ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-300"
                            : "border-red-400/20 bg-red-400/10 text-red-300",
                      )}>
                        {item.delta.improved == null ? "Flat" : item.delta.improved ? "Better" : "Worse"}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </ShellCard>

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
            <ShellCard className="p-6">
              <h2 className="text-xl font-black">Evolution Lineage</h2>
              <div className="mt-5 space-y-3">
                {lineage.map((item, index) => (
                  <div key={`${item.parent}-${item.child}-${index}`} className="flex flex-wrap items-center gap-3 rounded-2xl border border-[#f5b342]/10 bg-[#f5b342]/8 px-4 py-3 text-sm">
                    <span className="rounded bg-black/25 px-2 py-1 text-[#fff7e6]/78">{item.parent}</span>
                    <span>{"->"}</span>
                    <span className="rounded bg-[#f5b342]/18 px-2 py-1 font-black text-[#f5b342]">{item.child}</span>
                    {item.score != null ? <span className="text-xs text-[#fff7e6]/45">score {item.score.toFixed(2)}</span> : null}
                  </div>
                ))}
                {!lineage.length ? <div className="text-sm text-[#fff7e6]/45">No lineage yet. Select a strategy to begin.</div> : null}
              </div>
            </ShellCard>

            <ShellCard className="p-6">
              <h2 className="text-xl font-black">Performance Surface</h2>
              <div className="mt-5 rounded-3xl border border-[#f5b342]/12 bg-[#f5b342]/8 p-5">
                <div className="text-xs text-[#fff7e6]/45">Current evaluation profile</div>
                <div className="mt-2 text-2xl font-black">{activeStrategy?.name || "No active strategy"}</div>
                <div className="font-black text-emerald-400">{activeStrategy ? `${activeStrategy.profit} / PF ${activeStrategy.pf}` : "Select a strategy from the left."}</div>
              </div>
              <div className="mt-6 flex h-24 items-end gap-2">
                {buildSyntheticSeries(activeStrategy || champion || { name: "seed", net_profit: 4000 }).yearly.map((value, index) => (
                  <div key={index} className="flex-1 rounded bg-[#f5b342]/20" style={{ height: `${Math.max(18, Math.abs(value) / 180)}px` }} />
                ))}
              </div>
              {evolutionResult ? (
                <div className="mt-5 rounded-2xl border border-sky-400/16 bg-sky-400/8 p-4 text-sm text-[#dff4ff]">
                  {evolutionResult.improved
                    ? `The evolved strategy improved the evaluation and is now tracked as ${evolvedSnapshot?.name || evolutionResult.evolved?.name}.`
                    : "The evolution run finished, but no child outperformed the original strategy."}
                </div>
              ) : null}
            </ShellCard>
          </div>
        </div>
      </div>
    </PageShell>
  );
}

function PortfolioOptimizer({ portfolio }) {
  const strategies = portfolio?.strategies || [];
  return (
    <PageShell title="Portfolio Optimizer" subtitle="Backend-selected portfolio mix surfaced in the custom UI.">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Portfolio Size" value={String(portfolio?.portfolio_size || 0)} sub="strategies" />
        <StatCard label="Combined Profit" value={formatCurrency(portfolio?.total_combined_profit)} sub="total" state="profit" />
        <StatCard label="Avg Drawdown" value={formatPercent(portfolio?.avg_drawdown)} sub="risk" state="loss" />
        <StatCard label="Timeframes" value={String(portfolio?.timeframes_covered?.length || 0)} sub="covered" />
      </div>

      <ShellCard className="p-6">
        <h2 className="mb-4 text-lg font-black">Portfolio Strategies</h2>
        {!strategies.length ? (
          <div className="text-sm text-[#fff7e6]/50">No portfolio selection yet.</div>
        ) : (
          strategies.map((strategy) => (
            <div key={strategy.strategy_id} className="mb-3 rounded-2xl border border-[#f5b342]/10 bg-[#f5b342]/8 p-4">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="font-black">{strategy.strategy_name}</div>
                  <div className="text-xs text-[#fff7e6]/45">{strategy.symbol} · {strategy.timeframe} · {strategy.strategy_type}</div>
                </div>
                <div className="text-right">
                  <div className="font-black text-[#f5b342]">{strategy.allocation_pct}%</div>
                  <div className="text-xs text-[#fff7e6]/45">{formatCurrency(strategy.net_profit)}</div>
                </div>
              </div>
            </div>
          ))
        )}
      </ShellCard>
    </PageShell>
  );
}

function LogsPage({ logs, refresh }) {
  const [apiName, setApiName] = useState("");
  const [apiValue, setApiValue] = useState("");
  const [keys, setKeys] = useState([]);
  const [newModel, setNewModel] = useState("");
  const [localModels, setLocalModels] = useState(LOCAL_MODEL_DEFAULTS);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");

  useEffect(() => {
    let active = true;
    getIntegrationSettings()
      .then((response) => {
        if (!active) return;
        const data = response.data || {};
        setKeys(
          (data.api_keys || []).map((item, index) => ({
            id: Date.now() + index,
            name: item.name || `API Key ${index + 1}`,
            value: "",
            maskedValue: item.masked_value || "",
          })),
        );
        setLocalModels(data.local_models?.length ? data.local_models : LOCAL_MODEL_DEFAULTS);
      })
      .catch(() => {
        if (!active) return;
        setSaveMessage("Saved integrations could not be loaded right now.");
      });
    return () => {
      active = false;
    };
  }, []);

  const addKey = () => {
    if (!apiName.trim() || !apiValue.trim()) return;
    setKeys((current) => [...current, { id: Date.now(), name: apiName.trim(), value: apiValue.trim(), maskedValue: "" }]);
    setApiName("");
    setApiValue("");
    setSaveMessage("");
  };

  const addModel = () => {
    if (!newModel.trim()) return;
    setLocalModels((current) => [...current, newModel.trim()]);
    setNewModel("");
    setSaveMessage("");
  };

  const handleSaveIntegrations = async () => {
    setSaving(true);
    setSaveMessage("");
    try {
      const payload = {
        api_keys: keys
          .filter((key) => key.value?.trim())
          .map((key) => ({ name: key.name, value: key.value.trim() })),
        local_models: localModels,
      };
      const response = await saveIntegrationSettings(payload);
      const saved = response.data?.settings || {};
      setKeys(
        (saved.api_keys || []).map((item, index) => ({
          id: Date.now() + index,
          name: item.name || `API Key ${index + 1}`,
          value: "",
          maskedValue: item.masked_value || "",
        })),
      );
      setLocalModels(saved.local_models?.length ? saved.local_models : LOCAL_MODEL_DEFAULTS);
      setSaveMessage("Mission Control will now try your API keys first, then local models, then the built-in fallback.");
      await refresh?.();
    } catch (error) {
      setSaveMessage(error.message || "Failed to save integrations.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <PageShell title="Logs and Integrations" subtitle="Real backend logs, plus your live AI model setup for Mission Control.">
      <div className="grid gap-6 xl:grid-cols-2">
        <ShellCard className="p-6">
          <h2 className="text-lg font-black mb-3">API Keys</h2>
          <p className="mb-4 text-sm text-[#fff7e6]/58">
            Mission Control tries the saved API keys in order. If one fails, it automatically moves to the next one.
          </p>
          <div className="grid grid-cols-2 gap-3">
            <input value={apiName} onChange={(event) => setApiName(event.target.value)} placeholder="Key Name" className="rounded border border-[#f5b342]/20 bg-black/40 p-2 text-[#fff7e6]" />
            <input value={apiValue} onChange={(event) => setApiValue(event.target.value)} placeholder="API Key" className="rounded border border-[#f5b342]/20 bg-black/40 p-2 text-[#fff7e6]" />
          </div>
          <button onClick={addKey} className="mt-3 rounded bg-[#f5b342] px-4 py-2 font-black text-black">+ Add Key</button>
          <div className="mt-4 space-y-2">
            {keys.map((key) => (
              <div key={key.id} className="rounded-2xl border border-[#f5b342]/10 bg-[#f5b342]/8 px-4 py-3 text-sm">
                <b>{key.name}</b>
                <div className="text-xs text-[#fff7e6]/45">{key.maskedValue || (key.value ? `${key.value.slice(0, 6)}****` : "Ready to save")}</div>
              </div>
            ))}
            {!keys.length ? <div className="text-sm text-[#fff7e6]/50">No API keys saved yet.</div> : null}
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button onClick={handleSaveIntegrations} disabled={saving} className="rounded bg-[#f5b342] px-4 py-2 font-black text-black disabled:opacity-50">
              {saving ? "Saving..." : "Save Integrations"}
            </button>
            {saveMessage ? <div className="text-sm text-[#fff7e6]/55">{saveMessage}</div> : null}
          </div>
        </ShellCard>

        <ShellCard className="p-6">
          <h2 className="text-lg font-black mb-3">Local Models</h2>
          <p className="mb-4 text-sm text-[#fff7e6]/58">
            If every API key fails, Mission Control will try these local models next before falling back to the built-in mission prompt.
          </p>
          <div className="flex gap-3">
            <input value={newModel} onChange={(event) => setNewModel(event.target.value)} placeholder="e.g. llama3" className="flex-1 rounded border border-[#f5b342]/20 bg-black/40 p-2 text-[#fff7e6]" />
            <button onClick={addModel} className="rounded bg-[#f5b342] px-4 font-black text-black">+ Add</button>
          </div>
          <div className="mt-3 space-y-2">
            {localModels.map((model) => (
              <div key={model} className="rounded-2xl border border-[#f5b342]/10 bg-[#f5b342]/8 px-4 py-3 text-sm">✓ {model}</div>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button onClick={handleSaveIntegrations} disabled={saving} className="rounded bg-[#f5b342] px-4 py-2 font-black text-black disabled:opacity-50">
              {saving ? "Saving..." : "Save Integrations"}
            </button>
            {saveMessage ? <div className="text-sm text-[#fff7e6]/55">{saveMessage}</div> : null}
          </div>
        </ShellCard>
      </div>

      <ShellCard className="p-6">
        <h2 className="mb-4 text-xl font-black">System Logs</h2>
        <div className="space-y-3">
          {logs.slice(0, 20).map((log, index) => (
            <div key={`${log.timestamp || index}-${index}`} className="rounded-2xl border border-[#f5b342]/10 bg-[#f5b342]/8 px-4 py-3 text-sm">
              <div className="flex items-center justify-between gap-4">
                <span className={cn("text-xs font-black uppercase", statusTone(log.level))}>{log.level || "INFO"}</span>
                <span className="text-xs text-[#fff7e6]/40">{log.source || "system"}</span>
              </div>
              <div className="mt-2">{log.message}</div>
            </div>
          ))}
          {!logs.length && <div className="text-sm text-[#fff7e6]/50">No logs available yet.</div>}
        </div>
      </ShellCard>
    </PageShell>
  );
}

function RiskCenter({ risk, backtests }) {
  const highest = [...backtests].sort((left, right) => (right.max_drawdown || 0) - (left.max_drawdown || 0)).slice(0, 4);
  return (
    <PageShell title="Risk Center" subtitle="Risk analytics from the backend, kept in the same custom shell.">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard label="Portfolio Risk" value={risk ? formatPercent(risk.avg_drawdown) : "--"} sub="average DD" state="loss" />
        <StatCard label="Max DD" value={formatPercent(risk?.max_drawdown)} sub="worst" state="loss" />
        <StatCard label="VaR Proxy" value={formatPercent((risk?.avg_drawdown || 0) * 1.2)} sub="95% proxy" state="loss" />
        <StatCard label="Profitable" value={String(risk?.profitable_count || 0)} sub="strategies" state="profit" />
        <StatCard label="Backtests" value={String(backtests.length)} sub="tracked" />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <ShellCard className="p-6">
          <h2 className="mb-3 text-lg font-black">Risk Distribution</h2>
          {Object.entries(risk?.risk_distribution || {}).map(([label, value]) => (
            <div key={label} className="mb-4">
              <div className="mb-1 flex justify-between text-sm"><span>{label}</span><b className="text-[#f5b342]">{value}</b></div>
              <div className="h-2 rounded bg-black/40">
                <div className="h-2 rounded bg-[#f5b342]" style={{ width: `${Math.min(100, value * 8)}%` }} />
              </div>
            </div>
          ))}
        </ShellCard>

        <ShellCard className="p-6">
          <h2 className="mb-3 text-lg font-black">Highest Drawdown Strategies</h2>
          {highest.map((item) => (
            <div key={item.id} className="mb-3 rounded-2xl border border-[#f5b342]/10 bg-[#f5b342]/8 px-4 py-3 text-sm">
              <div className="flex justify-between">
                <b>{item.strategy_name}</b>
                <span className="text-red-400">{formatPercent(item.max_drawdown)}</span>
              </div>
              <div className="mt-1 text-xs text-[#fff7e6]/45">{formatCurrency(item.net_profit)} · {formatPercent(item.win_rate)}</div>
            </div>
          ))}
        </ShellCard>
      </div>
    </PageShell>
  );
}

function SettingsPage({ health, timeframe, setTimeframe, mockMode, setMockMode, refresh, pipelineConnected }) {
  return (
    <PageShell
      title="Settings"
      subtitle="Operate the system from the custom UI without falling back to the old dashboard."
      action={<button onClick={refresh} className="rounded-xl bg-[#f5b342] px-4 py-2 text-xs font-black text-black">Refresh Live Data</button>}
    >
      <div className="grid gap-6 xl:grid-cols-2">
        <ShellCard className="p-6">
          <h2 className="text-lg font-black mb-3">Execution Mode</h2>
          <div className="flex items-center justify-between text-sm mb-3">
            <span>Mock Mode</span>
            <button onClick={() => setMockMode((current) => !current)} className={mockMode ? "text-[#f5b342]" : "text-emerald-400"}>{mockMode ? "ENABLED" : "LIVE"}</button>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span>Pipeline Socket</span>
            <span className={pipelineConnected ? "text-emerald-400" : "text-red-400"}>{pipelineConnected ? "CONNECTED" : "OFFLINE"}</span>
          </div>
        </ShellCard>

        <ShellCard className="p-6">
          <h2 className="text-lg font-black mb-3">Default Timeframe</h2>
          <select value={timeframe} onChange={(event) => setTimeframe(event.target.value)} className="w-full rounded border border-[#f5b342]/20 bg-black/40 p-2 text-[#f5b342]">
            {TIMEFRAMES.map((item) => <option key={item}>{item}</option>)}
          </select>
        </ShellCard>

        <ShellCard className="p-6">
          <h2 className="text-lg font-black mb-3">Backend Services</h2>
          <div className="space-y-3 text-sm">
            {Object.entries(health?.services || {}).slice(0, 6).map(([key, value]) => (
              <div key={key} className="flex items-center justify-between rounded-2xl border border-[#f5b342]/10 bg-[#f5b342]/8 px-4 py-3">
                <span>{key}</span>
                <span className={statusTone(value?.status)}>{serviceLabel(value)}</span>
              </div>
            ))}
          </div>
        </ShellCard>

        <ShellCard className="p-6">
          <h2 className="text-lg font-black mb-3">Environment Notes</h2>
          <div className="space-y-3 text-sm text-[#fff7e6]/65">
            <div>MT5 terminal: {health?.services?.mt5_terminal?.detail || "Not detected"}</div>
            <div>Database: {health?.services?.database?.path || "Unavailable"}</div>
            <div>Gemini: {health?.services?.gemini?.detail || "Not configured"}</div>
          </div>
        </ShellCard>
      </div>
    </PageShell>
  );
}

function Topbar({ page, timeframe, setTimeframe, mockMode, setMockMode, onGenerate, busyLabel }) {
  return (
    <header className="sticky top-0 z-40 flex flex-wrap items-center justify-between gap-4 border-b border-[#f5b342]/15 bg-[#080501]/92 px-6 py-4 text-[#fff7e6] backdrop-blur-xl">
      <div className="flex items-center gap-3">
        <div className="grid h-9 w-9 place-items-center rounded-xl bg-[#f5b342] font-black text-black"><MedXoraLogo size={28} /></div>
        <div>
          <div className="text-sm font-black">MedXora AI</div>
          <div className="text-[10px] uppercase tracking-[.2em] text-[#fff7e6]/40">{page}</div>
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-end gap-3">
        <select value={timeframe} onChange={(event) => setTimeframe(event.target.value)} className="rounded-xl border border-[#f5b342]/20 bg-[#f5b342]/8 px-4 py-2 text-sm font-semibold text-[#fff7e6]/80">
          {TIMEFRAMES.map((item) => <option key={item}>{item}</option>)}
        </select>
        <button onClick={() => setMockMode((current) => !current)} className="rounded-xl border border-[#f5b342]/20 bg-[#f5b342]/8 px-4 py-2 text-sm font-semibold text-[#fff7e6]/80">{mockMode ? "Mock" : "Real MT5"}</button>
        <button onClick={onGenerate} disabled={Boolean(busyLabel)} className="rounded-xl bg-[#f5b342] px-5 py-2.5 text-sm font-black text-black disabled:opacity-50">+ Generate</button>
      </div>
    </header>
  );
}

function MissionControlPage({ refreshDashboard }) {
  return <MissionControlWorkspacePage refreshDashboard={refreshDashboard} />;
}

function MissionControlWorkspacePage({ refreshDashboard }) {
  const [goal, setGoal] = useState("Create a low-risk EURUSD strategy on M15, backtest it, evolve for 3 generations, and export the champion MQL5 EA.");
  const [strategyName, setStrategyName] = useState("");
  const [strategyDescription, setStrategyDescription] = useState("Low-risk EURUSD strategy with clean entries, controlled drawdown, and steady profit behavior.");
  const [pair, setPair] = useState("EURUSD");
  const [missionTimeframe, setMissionTimeframe] = useState("M15");
  const [activeMission, setActiveMission] = useState(null);
  const [generatedStrategies, setGeneratedStrategies] = useState([]);
  const [selectedMissionStrategy, setSelectedMissionStrategy] = useState(null);
  const [strategyDetailLoading, setStrategyDetailLoading] = useState(false);
  const [missions, setMissions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [actionLoading, setActionLoading] = useState("");
  const [mcpStatus, setMcpStatus] = useState(null);
  const [error, setError] = useState(null);
  const [liveEvents, setLiveEvents] = useState([]);
  const activeMissionId = activeMission?.mission?.id || null;
  const activeMissionStatus = activeMission?.mission?.status || null;

  const fetchMission = useCallback(async (id) => {
    if (!id) return null;
    try {
      const missionRes = await getMission(id);
      const missionPayload = missionRes.data;
      setActiveMission(missionPayload);
      const eventsRes = await getMissionEvents(id).catch(() => ({ data: [] }));
      setLiveEvents(Array.isArray(eventsRes.data) ? eventsRes.data : []);
      return missionPayload;
    } catch (fetchError) {
      setError(fetchError.message || "Failed to load mission details");
      return null;
    }
  }, []);

  const openMissionStrategy = useCallback(async (strategyId) => {
    if (!strategyId) return;
    setStrategyDetailLoading(true);
    setError(null);
    try {
      const { data } = await getStrategy(strategyId);
      setSelectedMissionStrategy(normalizeStrategyDetail(data));
    } catch (detailError) {
      setError(detailError.message || "Failed to load strategy details");
    } finally {
      setStrategyDetailLoading(false);
    }
  }, []);

  const refreshOverview = useCallback(async ({ silent = false, targetMissionId = null, selectLatest = false } = {}) => {
    if (!silent) setRefreshing(true);
    try {
      const [missionsRes, statusRes, strategiesRes] = await Promise.all([
        listMissions(12),
        getMcpStatus().catch(() => null),
        listStrategies().catch(() => ({ data: [] })),
      ]);
      const missionList = missionsRes.data?.missions || [];
      const orderedStrategies = [...(strategiesRes?.data || [])]
        .sort((left, right) => {
          const leftTime = new Date(left.created_at || 0).getTime();
          const rightTime = new Date(right.created_at || 0).getTime();
          return rightTime - leftTime || (right.id || 0) - (left.id || 0);
        })
        .map((item) => normalizeStrategySummary(item));
      setMissions(missionList);
      setGeneratedStrategies(orderedStrategies);
      if (statusRes?.data) {
        setMcpStatus(statusRes.data);
      }

      const resolvedMissionId =
        targetMissionId ||
        activeMission?.mission?.id ||
        (selectLatest ? missionList[0]?.id : null);

      if (resolvedMissionId) {
        await fetchMission(resolvedMissionId);
      } else if (selectLatest) {
        setActiveMission(null);
      }
    } catch (refreshError) {
      setError(refreshError.message || "Failed to refresh Mission Control");
    } finally {
      if (!silent) setRefreshing(false);
    }
  }, [activeMission, fetchMission]);

  const advanceMissionUntilCheckpoint = useCallback(async (missionId, iterations = 20) => {
    for (let index = 0; index < iterations; index += 1) {
      const advanceRes = await advanceMission(missionId);
      const latestMission = await fetchMission(missionId);
      const latestStatus = advanceRes.data?.status || latestMission?.mission?.status;
      if (["completed", "waiting_approval", "failed", "paused", "stopped"].includes(latestStatus)) {
        break;
      }
      await sleep(400);
    }
  }, [fetchMission]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      refreshOverview({ selectLatest: true }).catch(() => {});
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [refreshOverview]);

  useEffect(() => {
    if (!activeMissionId || !["active", "running", "pending", "waiting_approval"].includes(activeMissionStatus)) {
      return undefined;
    }

    const interval = setInterval(() => {
      refreshOverview({ silent: true, targetMissionId: activeMissionId }).catch(() => {});
    }, activeMissionStatus === "waiting_approval" ? 5000 : 2500);

    return () => clearInterval(interval);
  }, [activeMissionId, activeMissionStatus, refreshOverview]);

  const handleStartMission = useCallback(async () => {
    if (!goal.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const missionBrief = [
        strategyName.trim() ? `Preferred strategy name: ${strategyName.trim()}.` : "",
        strategyDescription.trim() ? `Strategy description: ${strategyDescription.trim()}.` : "",
        goal.trim(),
      ]
        .filter(Boolean)
        .join(" ");

      const res = await createMission({
        mission: missionBrief,
        symbol: pair,
        timeframe: missionTimeframe,
        max_drawdown: 15,
        target_sharpe: 1.2,
        min_trades: 50,
        use_evolution: true,
      }).catch(() => startMission(missionBrief, pair, missionTimeframe));
      const mission = res.data?.mission || { id: res.data?.mission_id, status: res.data?.status };
      if (!mission?.id && !res.data?.mission_id) {
        throw new Error("Mission did not start correctly");
      }
      const missionId = mission.id || res.data?.mission_id;
      setActiveMission({ mission: { ...mission, id: missionId }, steps: [], reasoning_trace: [] });
      await refreshOverview({ targetMissionId: missionId });
      await advanceMissionUntilCheckpoint(mission.id);
      await refreshOverview({ targetMissionId: mission.id });
      await refreshDashboard?.();
    } catch (startError) {
      setError(startError.message || "Failed to start mission");
    } finally {
      setLoading(false);
    }
  }, [advanceMissionUntilCheckpoint, goal, missionTimeframe, pair, refreshDashboard, refreshOverview, strategyDescription, strategyName]);

  const handleApprove = useCallback(async (stepId, approved) => {
    if (!activeMission?.mission?.id) return;
    setError(null);
    try {
      await approveStep(activeMission.mission.id, stepId, approved);
      await fetchMission(activeMission.mission.id);
      await advanceMissionUntilCheckpoint(activeMission.mission.id, 10);
      await refreshOverview({ targetMissionId: activeMission.mission.id });
      await refreshDashboard?.();
    } catch (approveError) {
      setError(approveError.message || "Failed to update approval");
    }
  }, [activeMission, advanceMissionUntilCheckpoint, fetchMission, refreshDashboard, refreshOverview]);

  const handlePause = useCallback(async () => {
    if (!activeMission?.mission?.id) return;
    setActionLoading("pause");
    setError(null);
    try {
      await pauseMission(activeMission.mission.id);
      await refreshOverview({ targetMissionId: activeMission.mission.id });
      await refreshDashboard?.();
    } catch (pauseError) {
      setError(pauseError.message || "Failed to pause mission");
    } finally {
      setActionLoading("");
    }
  }, [activeMission, refreshDashboard, refreshOverview]);

  const handleResume = useCallback(async () => {
    if (!activeMission?.mission?.id) return;
    setActionLoading("resume");
    setError(null);
    try {
      await resumeMission(activeMission.mission.id);
      await advanceMissionUntilCheckpoint(activeMission.mission.id, 10);
      await refreshOverview({ targetMissionId: activeMission.mission.id });
      await refreshDashboard?.();
    } catch (resumeError) {
      setError(resumeError.message || "Failed to resume mission");
    } finally {
      setActionLoading("");
    }
  }, [activeMission, advanceMissionUntilCheckpoint, refreshDashboard, refreshOverview]);

  const handleStop = useCallback(async () => {
    if (!activeMission?.mission?.id) return;
    setActionLoading("stop");
    setError(null);
    try {
      await stopMission(activeMission.mission.id);
      await refreshOverview({ targetMissionId: activeMission.mission.id });
      await refreshDashboard?.();
    } catch (stopError) {
      setError(stopError.message || "Failed to stop mission");
    } finally {
      setActionLoading("");
    }
  }, [activeMission, refreshDashboard, refreshOverview]);

  const statusMeta = (status) => {
    const normalized = String(status || "idle").toLowerCase();
    if (["completed", "approved", "active"].includes(normalized)) {
      return {
        badge: "border-emerald-400/25 bg-emerald-400/10 text-emerald-300",
        bar: "bg-emerald-400",
        soft: "border-emerald-400/16 bg-emerald-400/8",
      };
    }
    if (["failed", "stopped", "rejected"].includes(normalized)) {
      return {
        badge: "border-red-400/25 bg-red-400/10 text-red-300",
        bar: "bg-red-400",
        soft: "border-red-400/16 bg-red-400/8",
      };
    }
    if (normalized === "waiting_approval") {
      return {
        badge: "border-[#f5b342]/25 bg-[#f5b342]/12 text-[#f7d38d]",
        bar: "bg-[#f5b342]",
        soft: "border-[#f5b342]/16 bg-[#f5b342]/8",
      };
    }
    if (["running", "pending"].includes(normalized)) {
      return {
        badge: "border-sky-400/25 bg-sky-400/10 text-sky-300",
        bar: "bg-sky-400",
        soft: "border-sky-400/16 bg-sky-400/8",
      };
    }
    if (normalized === "paused") {
      return {
        badge: "border-violet-400/25 bg-violet-400/10 text-violet-300",
        bar: "bg-violet-400",
        soft: "border-violet-400/16 bg-violet-400/8",
      };
    }
    return {
      badge: "border-white/10 bg-white/5 text-[#fff7e6]/70",
      bar: "bg-white/40",
      soft: "border-white/10 bg-white/5",
    };
  };

  const missionData = activeMission?.mission || null;
  const missionStrategy = normalizeMissionStrategySnapshot(activeMission?.strategy);
  const strategyParams = Object.entries(missionStrategy?.parameters || {}).filter(([, value]) => value != null);
  const steps = activeMission?.steps || [];
  const waitingStep = steps.find((step) => step.status === "waiting_approval");
  const completedSteps = steps.filter((step) => ["completed", "approved"].includes(step.status)).length;
  const missionProgress = steps.length ? Math.round((completedSteps / steps.length) * 100) : 0;
  const connectedPartners = mcpStatus
    ? Object.entries(mcpStatus).filter(([key, value]) => key !== "active_source" && ["connected", "active"].includes(String(value?.status || "").toLowerCase())).length
    : 0;
  const approvalCount = missions.filter((mission) => mission.status === "waiting_approval").length;
  const inFlightCount = missions.filter((mission) => ["running", "active", "pending"].includes(mission.status)).length;
  const activeStatusMeta = statusMeta(missionData?.status);
  const approvalDetail = (() => {
    if (!waitingStep) return "";
    const raw = String(waitingStep.input?.description || "").trim();
    if (raw && raw.length > 18) return raw;
    return `Please review "${waitingStep.step_name}" before the mission continues.`;
  })();
  const goalPresets = [
    {
      label: "Low-Risk M15",
      prompt: "Create a low-risk EURUSD strategy on M15 and show the final profit and quality metrics.",
    },
    {
      label: "Scalping M5",
      prompt: "Build a conservative EURUSD scalping strategy on M5, backtest it, and save the best result.",
    },
    {
      label: "Intraday H1",
      prompt: "Generate an EURUSD intraday strategy on H1, improve it, and export the final MQL5 file.",
    },
  ];
  const missionGuide = (() => {
    const status = String(missionData?.status || "").toLowerCase();
    if (!missionData) {
      return {
        title: "Ready to start",
        detail: "Write a goal, choose the timeframe, and start the mission. Mission Control will save the generated strategy and show its results here.",
      };
    }
    if (waitingStep) {
      return {
        title: "Waiting for your approval",
        detail: approvalDetail,
      };
    }
    if (status === "completed") {
      return {
        title: "Mission completed",
        detail: missionStrategy
          ? `The final strategy is saved and ready to review. Current net profit: ${missionStrategy.profit}.`
          : "The mission completed successfully and the final strategy is ready to review.",
      };
    }
    if (status === "paused") {
      return {
        title: "Mission paused",
        detail: "You can resume the mission at any time and it will continue from the same point.",
      };
    }
    if (status === "failed" || status === "stopped") {
      return {
        title: "Mission stopped",
        detail: "This mission is no longer running. You can start a new one when you are ready.",
      };
    }
    return {
      title: "Mission in progress",
      detail: "Mission Control is building, testing, and improving the strategy in the background.",
    };
  })();

  return (
    <PageShell
      title="Mission Control"
      subtitle="MedXora AI Command Center · Autonomous MT5 strategy research, validation, evolution, and MQL5 deployment."
      action={
        <button
          onClick={() => refreshOverview({ targetMissionId: missionData?.id })}
          disabled={refreshing}
          className="rounded-xl border border-[#f5b342]/20 bg-[#f5b342]/10 px-4 py-2 text-xs font-black text-[#f5b342] transition hover:bg-[#f5b342]/16 disabled:opacity-50"
        >
          {refreshing ? "Refreshing..." : "Refresh"}
        </button>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard label="Saved Missions" value={String(missions.length)} sub="latest missions" />
        <StatCard label="Running Now" value={String(inFlightCount)} sub="active right now" />
        <StatCard label="Needs Approval" value={String(approvalCount)} sub="waiting for you" state={approvalCount ? "loss" : "idle"} />
        <StatCard label="Connections" value={String(connectedPartners)} sub={mcpStatus?.active_source ? `via ${mcpStatus.active_source}` : "services online"} />
        <StatCard label="Progress" value={missionData ? `${missionProgress}%` : "--"} sub={missionData ? `mission #${missionData.id}` : "no mission yet"} state={missionProgress >= 100 ? "profit" : "idle"} />
      </div>

      {error ? (
        <ShellCard className="border-red-400/25 bg-red-500/10 p-4 text-sm text-red-200" state="loss">
          {error}
        </ShellCard>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_380px]">
        <ShellCard className="p-6">
          <PanelHeader title="MedXora AI Command Center" action="guided setup" />
          <h2 className="text-2xl font-black">Tell Mission Control what you want to build</h2>
          <p className="mt-2 max-w-3xl text-sm text-[#fff7e6]/52">
            Describe the kind of EURUSD strategy you want, then Mission Control will generate it, backtest it, improve it, and save the result for you.
          </p>
          <div className="mt-5 grid gap-4 lg:grid-cols-2">
            <div>
              <div className="mb-2 text-[10px] font-black uppercase tracking-[.18em] text-[#fff7e6]/38">Strategy Name</div>
              <input
                value={strategyName}
                onChange={(event) => setStrategyName(event.target.value)}
                className="w-full rounded-[20px] border border-[#f5b342]/14 bg-black/35 px-4 py-3 text-sm text-[#fff7e6] outline-none transition placeholder:text-[#fff7e6]/28 focus:border-[#f5b342]/35"
                placeholder="Example: Atlas M15"
              />
            </div>
            <div>
              <div className="mb-2 text-[10px] font-black uppercase tracking-[.18em] text-[#fff7e6]/38">Strategy Description</div>
              <input
                value={strategyDescription}
                onChange={(event) => setStrategyDescription(event.target.value)}
                className="w-full rounded-[20px] border border-[#f5b342]/14 bg-black/35 px-4 py-3 text-sm text-[#fff7e6] outline-none transition placeholder:text-[#fff7e6]/28 focus:border-[#f5b342]/35"
                placeholder="Example: Conservative trend-following strategy with strict drawdown control."
              />
            </div>
          </div>
          <textarea
            value={goal}
            onChange={(event) => setGoal(event.target.value)}
            rows={4}
            className="mt-5 w-full rounded-[24px] border border-[#f5b342]/14 bg-black/35 px-4 py-4 text-sm text-[#fff7e6] outline-none transition placeholder:text-[#fff7e6]/28 focus:border-[#f5b342]/35"
            placeholder="Describe the strategy you want agents to build..."
          />
          <div className="mt-4 flex flex-wrap gap-2">
            {goalPresets.map((preset) => (
              <button
                key={preset.label}
                onClick={() => setGoal(preset.prompt)}
                className="rounded-full border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-[#fff7e6]/75 transition hover:border-[#f5b342]/24 hover:bg-[#f5b342]/10 hover:text-[#fff7e6]"
              >
                {preset.label}
              </button>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <select value={pair} onChange={(event) => setPair(event.target.value)} className="rounded-xl border border-[#f5b342]/18 bg-[#090704] px-4 py-3 text-sm text-[#fff7e6] outline-none">
              {["EURUSD"].map((item) => <option key={item}>{item}</option>)}
            </select>
            <select value={missionTimeframe} onChange={(event) => setMissionTimeframe(event.target.value)} className="rounded-xl border border-[#f5b342]/18 bg-[#090704] px-4 py-3 text-sm text-[#fff7e6] outline-none">
              {["M1", "M5", "M15", "M30", "H1", "H4", "D1"].map((item) => <option key={item}>{item}</option>)}
            </select>
            <button onClick={handleStartMission} disabled={loading} className="rounded-xl bg-[#f5b342] px-5 py-3 text-sm font-black text-black transition hover:brightness-105 disabled:opacity-50">
              {loading ? "Starting Mission..." : "Start Agent Mission"}
            </button>
            <button onClick={handleStop} className="rounded-xl border border-red-400/20 bg-red-400/10 px-4 py-3 text-xs font-black text-red-300 transition hover:bg-red-400/16">Stop Mission</button>
            <button onClick={async () => missionStrategy?.id && exportMQL5(missionStrategy.id)} className="rounded-xl border border-[#f5b342]/20 bg-[#f5b342]/10 px-4 py-3 text-xs font-black text-[#f5b342] transition hover:bg-[#f5b342]/16">Export Champion</button>
            <button onClick={() => document.getElementById('mission-report')?.scrollIntoView({ behavior: 'smooth' })} className="rounded-xl border border-white/15 bg-white/5 px-4 py-3 text-xs font-black text-[#fff7e6] transition hover:bg-white/10">View Report</button>
          </div>
          {waitingStep && missionData ? (
            <div className="mt-4 rounded-[24px] border border-[#f5b342]/24 bg-[#f5b342]/10 p-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="text-[10px] font-black uppercase tracking-[.2em] text-[#f5d18b]">Approval Needed</div>
                  <h3 className="mt-3 text-lg font-black text-[#fff7e6]">{waitingStep.step_name}</h3>
                  <p className="mt-2 max-w-3xl text-sm leading-6 text-[#fff7e6]/72">
                    {approvalDetail}
                  </p>
                </div>
                <div className="flex flex-wrap gap-3">
                  <button onClick={() => handleApprove(waitingStep.id, true)} className="rounded-xl bg-emerald-400 px-4 py-2.5 text-xs font-black text-black transition hover:brightness-105">
                    Approve And Continue
                  </button>
                  <button onClick={() => handleApprove(waitingStep.id, false)} className="rounded-xl bg-red-400 px-4 py-2.5 text-xs font-black text-black transition hover:brightness-105">
                    Reject Mission Step
                  </button>
                </div>
              </div>
            </div>
          ) : null}
          <div className="mt-4 rounded-2xl border border-emerald-400/16 bg-emerald-400/8 p-4 text-sm text-[#def8ea]">
            Mission Control currently uses EURUSD real tick data for backtests, then saves the generated strategy and shows the result here.
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            <div className="rounded-2xl border border-[#f5b342]/12 bg-[#f5b342]/8 p-4">
              <div className="text-[10px] font-black uppercase tracking-[.2em] text-[#fff7e6]/38">Market</div>
              <div className="mt-2 text-lg font-black text-[#f5b342]">{pair}</div>
            </div>
            <div className="rounded-2xl border border-[#f5b342]/12 bg-[#f5b342]/8 p-4">
              <div className="text-[10px] font-black uppercase tracking-[.2em] text-[#fff7e6]/38">Timeframe</div>
              <div className="mt-2 text-lg font-black text-[#f5b342]">{missionTimeframe}</div>
            </div>
            <div className="rounded-2xl border border-[#f5b342]/12 bg-[#f5b342]/8 p-4">
              <div className="text-[10px] font-black uppercase tracking-[.2em] text-[#fff7e6]/38">Flow</div>
              <div className="mt-2 text-lg font-black text-emerald-300">Guided + Saved</div>
            </div>
          </div>
        </ShellCard>

        <div className="space-y-6">
          <ShellCard className="p-6">
            <PanelHeader title="What Is Happening Now" action={missionData ? `mission #${missionData.id}` : "standby"} />
            {!missionData ? (
              <div className="rounded-2xl border border-dashed border-[#f5b342]/18 bg-[#f5b342]/6 p-5 text-sm text-[#fff7e6]/55">
                No mission is running yet. Start one from the left and its live progress will appear here.
              </div>
            ) : (
              <>
                <div className="flex flex-wrap items-center gap-3">
                  <span className={cn("rounded-full border px-3 py-1 text-[11px] font-black uppercase tracking-[.18em]", activeStatusMeta.badge)}>
                    {String(missionData.status || "unknown").replace(/_/g, " ")}
                  </span>
                  <span className="text-xs text-[#fff7e6]/40">Started {formatDateTime(missionData.created_at)}</span>
                </div>
                <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-4">
                  <div className="text-sm font-black text-[#fff7e6]">{missionGuide.title}</div>
                  <p className="mt-2 text-sm leading-6 text-[#fff7e6]/65">{missionGuide.detail}</p>
                </div>
                <div className="mt-4 space-y-3 text-sm text-[#fff7e6]/72">
                  <div className="flex items-center justify-between">
                    <span>Progress</span>
                    <b className="text-[#f5b342]">{completedSteps}/{steps.length || 0}</b>
                  </div>
                  <div className="h-2 rounded-full bg-black/35">
                    <div className={cn("h-2 rounded-full", activeStatusMeta.bar)} style={{ width: `${Math.max(8, missionProgress)}%` }} />
                  </div>
                </div>
                <div className="mt-5 rounded-2xl border border-[#f5b342]/12 bg-black/25 p-4">
                  <div className="text-[10px] font-black uppercase tracking-[.18em] text-[#fff7e6]/35">Generated Strategy</div>
                  {missionStrategy ? (
                    <>
                      <div className="mt-2 text-sm font-black text-[#fff7e6]">{missionStrategy.name}</div>
                      <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-[#fff7e6]/48">
                        <span>{missionStrategy.symbol}</span>
                        <span>{missionStrategy.timeframe}</span>
                        <span>{missionStrategy.type}</span>
                        <span>Gen {missionStrategy.generation}</span>
                      </div>
                      <div className="mt-4 grid gap-3 sm:grid-cols-2">
                        <div>
                          <div className="text-[10px] uppercase tracking-[.18em] text-[#fff7e6]/35">Net Profit</div>
                          <div className={cn("mt-1 text-lg font-black", (missionStrategy.netProfit ?? 0) >= 0 ? "text-emerald-300" : "text-red-300")}>{missionStrategy.profit}</div>
                        </div>
                        <div>
                          <div className="text-[10px] uppercase tracking-[.18em] text-[#fff7e6]/35">Profit Factor</div>
                          <div className="mt-1 text-lg font-black text-[#f5b342]">{missionStrategy.pf}</div>
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="mt-2 text-sm text-[#fff7e6]/55">
                      Strategy details will appear here as soon as the mission generates and tests one.
                    </div>
                  )}
                </div>
              </>
            )}
          </ShellCard>

          <ShellCard className="p-6">
            <PanelHeader title="Connected Services" action={mcpStatus?.active_source || "service health"} />
            <div className="space-y-3">
              {mcpStatus ? Object.entries(mcpStatus)
                .filter(([key]) => key !== "active_source")
                .map(([key, value]) => {
                  const connected = ["connected", "active"].includes(String(value?.status || "").toLowerCase());
                  return (
                    <div key={key} className={cn("rounded-2xl border px-4 py-3", connected ? "border-emerald-400/16 bg-emerald-400/8" : "border-[#f5b342]/12 bg-[#f5b342]/8")}>
                      <div className="text-[10px] font-black uppercase tracking-[.18em] text-[#fff7e6]/38">{key.replace(/_/g, " ")}</div>
                      <div className={cn("mt-2 text-sm font-black", connected ? "text-emerald-300" : "text-[#f5d9a8]")}>{value?.status || "unknown"}</div>
                      <div className="mt-1 text-xs text-[#fff7e6]/45">{value?.detail || "No extra message right now."}</div>
                    </div>
                  );
                }) : (
                <div className="rounded-2xl border border-dashed border-[#f5b342]/18 bg-[#f5b342]/6 p-4 text-sm text-[#fff7e6]/55">
                  Service connection details are not available yet.
                </div>
              )}
            </div>
          </ShellCard>
        </div>
      </div>

      <ShellCard className="p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <PanelHeader title="Current Mission" action={missionData ? `#${missionData.id}` : "waiting"} />
            <h2 className="text-2xl font-black">{missionData ? missionData.user_goal : "No mission selected yet"}</h2>
            <p className="mt-2 max-w-4xl text-sm text-[#fff7e6]/52">
              {missionData
                ? "Everything important about the current mission is summarized below."
                : "Start a mission to see its progress, approvals, and generated strategy result."}
            </p>
          </div>
          {missionData ? (
            <div className="flex flex-wrap gap-2">
              <button onClick={handlePause} disabled={actionLoading === "pause" || ["paused", "completed", "failed", "stopped"].includes(missionData.status)} className="rounded-xl border border-[#f5b342]/20 bg-[#f5b342]/10 px-4 py-2 text-xs font-black text-[#f5b342] transition hover:bg-[#f5b342]/16 disabled:opacity-40">
                {actionLoading === "pause" ? "Pausing..." : "Pause Mission"}
              </button>
              <button onClick={handleResume} disabled={actionLoading === "resume" || !["paused", "waiting_approval"].includes(missionData.status)} className="rounded-xl border border-sky-400/20 bg-sky-400/10 px-4 py-2 text-xs font-black text-sky-300 transition hover:bg-sky-400/16 disabled:opacity-40">
                {actionLoading === "resume" ? "Resuming..." : "Resume Mission"}
              </button>
              <button onClick={handleStop} disabled={actionLoading === "stop" || ["completed", "failed", "stopped"].includes(missionData.status)} className="rounded-xl border border-red-400/20 bg-red-400/10 px-4 py-2 text-xs font-black text-red-300 transition hover:bg-red-400/16 disabled:opacity-40">
                {actionLoading === "stop" ? "Stopping..." : "Stop Mission"}
              </button>
            </div>
          ) : null}
        </div>

        {!missionData ? (
          <div className="mt-6 rounded-[26px] border border-dashed border-[#f5b342]/18 bg-[#0b0906] p-8 text-center text-sm text-[#fff7e6]/50">
            Mission details will appear here once a mission is started or selected.
          </div>
        ) : (
          <>
            <div className="mt-6 grid gap-4 lg:grid-cols-4">
              <div className={cn("rounded-[24px] border p-4", activeStatusMeta.soft)}>
                <div className="text-[10px] font-black uppercase tracking-[.18em] text-[#fff7e6]/38">Status</div>
                <div className="mt-2 text-lg font-black">{String(missionData.status || "unknown").replace(/_/g, " ")}</div>
              </div>
              <div className="rounded-[24px] border border-[#f5b342]/12 bg-[#f5b342]/8 p-4">
                <div className="text-[10px] font-black uppercase tracking-[.18em] text-[#fff7e6]/38">Created</div>
                <div className="mt-2 text-lg font-black">{formatDateTime(missionData.created_at)}</div>
              </div>
              <div className="rounded-[24px] border border-[#f5b342]/12 bg-[#f5b342]/8 p-4">
                <div className="text-[10px] font-black uppercase tracking-[.18em] text-[#fff7e6]/38">Approval Gates</div>
                <div className="mt-2 text-lg font-black">{steps.filter((step) => step.requires_approval).length}</div>
              </div>
              <div className="rounded-[24px] border border-[#f5b342]/12 bg-[#f5b342]/8 p-4">
                <div className="text-[10px] font-black uppercase tracking-[.18em] text-[#fff7e6]/38">Mission Progress</div>
                <div className="mt-2 text-lg font-black">{missionProgress}%</div>
              </div>
            </div>

            {missionData.gemini_reasoning ? (
              <div className="mt-6 rounded-[24px] border border-sky-400/18 bg-sky-400/8 p-5">
                <div className="text-[10px] font-black uppercase tracking-[.2em] text-sky-300">Mission Notes</div>
                <p className="mt-3 text-sm leading-6 text-[#e5eefc]">{missionData.gemini_reasoning}</p>
              </div>
            ) : null}
            <div className="mt-6 rounded-[24px] border border-[#f5b342]/12 bg-[#0b0906] p-5">
              <div className="text-[10px] font-black uppercase tracking-[.2em] text-[#f5d18b]">Live Agent Timeline</div>
              <div className="mt-3 space-y-2">
                {(liveEvents.length ? liveEvents : [{ id: "sample", timestamp: new Date().toISOString(), agent: "Mission Planner Agent", event_type: "info", message: "No active mission events yet. Start Agent Mission to begin live timeline." }]).slice(-12).map((event) => (
                  <div key={event.id} className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-white/5 px-3 py-2">
                    <div className="text-xs text-[#fff7e6]/80"><span className="font-black text-[#f5b342]">{event.agent || "Agent"}</span> · {event.message}</div>
                    <div className="text-[10px] text-[#fff7e6]/45">{formatDateTime(event.timestamp)}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="mt-6 rounded-[24px] border border-[#f5b342]/14 bg-[#0b0906] p-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="text-[10px] font-black uppercase tracking-[.2em] text-[#f5d18b]">Generated Strategy</div>
                  <h3 className="mt-3 text-xl font-black text-[#fff7e6]">
                    {missionStrategy ? missionStrategy.name : "Waiting for the mission to generate a strategy"}
                  </h3>
                  <p className="mt-2 text-sm text-[#fff7e6]/58">
                    {missionStrategy
                      ? "This strategy was created by the mission, backtested on EURUSD real tick data, and saved for review."
                      : "Once the mission creates and tests a strategy, its performance details will appear here."}
                  </p>
                </div>
                {missionStrategy ? (
                  <span
                    className={cn(
                      "rounded-full border px-3 py-1 text-[11px] font-black uppercase tracking-[.18em]",
                      (missionStrategy.netProfit ?? 0) > 0
                        ? "border-emerald-400/25 bg-emerald-400/10 text-emerald-300"
                        : "border-[#f5b342]/20 bg-[#f5b342]/10 text-[#f5d18b]",
                    )}
                  >
                    {(missionStrategy.netProfit ?? 0) > 0 ? "Performing" : "Saved"}
                  </span>
                ) : null}
              </div>

              {missionStrategy ? (
                <>
                  <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    <div className="rounded-[22px] border border-emerald-400/16 bg-emerald-400/8 p-4">
                      <div className="text-[10px] font-black uppercase tracking-[.18em] text-[#d0fbe5]/45">Net Profit</div>
                      <div className={cn("mt-2 text-xl font-black", (missionStrategy.netProfit ?? 0) >= 0 ? "text-emerald-300" : "text-red-300")}>{missionStrategy.profit}</div>
                    </div>
                    <div className="rounded-[22px] border border-[#f5b342]/12 bg-[#f5b342]/8 p-4">
                      <div className="text-[10px] font-black uppercase tracking-[.18em] text-[#fff7e6]/38">Win Rate</div>
                      <div className="mt-2 text-xl font-black text-[#f5b342]">{missionStrategy.win}</div>
                    </div>
                    <div className="rounded-[22px] border border-[#f5b342]/12 bg-[#f5b342]/8 p-4">
                      <div className="text-[10px] font-black uppercase tracking-[.18em] text-[#fff7e6]/38">Max Drawdown</div>
                      <div className="mt-2 text-xl font-black text-[#f5b342]">{missionStrategy.dd}</div>
                    </div>
                    <div className="rounded-[22px] border border-[#f5b342]/12 bg-[#f5b342]/8 p-4">
                      <div className="text-[10px] font-black uppercase tracking-[.18em] text-[#fff7e6]/38">Profit Factor</div>
                      <div className="mt-2 text-xl font-black text-[#f5b342]">{missionStrategy.pf}</div>
                    </div>
                  </div>

                  <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,.85fr)]">
                    <div className="rounded-[22px] border border-[#f5b342]/10 bg-black/20 p-4">
                      <div className="text-[10px] font-black uppercase tracking-[.18em] text-[#fff7e6]/35">Strategy Details</div>
                      <div className="mt-4 grid gap-3 sm:grid-cols-2">
                        <div className="rounded-2xl border border-white/8 bg-white/5 p-3">
                          <div className="text-[10px] uppercase tracking-[.18em] text-[#fff7e6]/35">Market</div>
                          <div className="mt-1 text-sm font-black text-[#fff7e6]">{missionStrategy.symbol} / {missionStrategy.timeframe}</div>
                        </div>
                        <div className="rounded-2xl border border-white/8 bg-white/5 p-3">
                          <div className="text-[10px] uppercase tracking-[.18em] text-[#fff7e6]/35">Type</div>
                          <div className="mt-1 text-sm font-black text-[#fff7e6]">{missionStrategy.type}</div>
                        </div>
                        <div className="rounded-2xl border border-white/8 bg-white/5 p-3">
                          <div className="text-[10px] uppercase tracking-[.18em] text-[#fff7e6]/35">Generation</div>
                          <div className="mt-1 text-sm font-black text-[#fff7e6]">{missionStrategy.generation}</div>
                        </div>
                        <div className="rounded-2xl border border-white/8 bg-white/5 p-3">
                          <div className="text-[10px] uppercase tracking-[.18em] text-[#fff7e6]/35">Backtest Data</div>
                          <div className="mt-1 text-sm font-black text-[#fff7e6]">{missionStrategy.dataSource}</div>
                        </div>
                        <div className="rounded-2xl border border-white/8 bg-white/5 p-3">
                          <div className="text-[10px] uppercase tracking-[.18em] text-[#fff7e6]/35">Start Balance</div>
                          <div className="mt-1 text-sm font-black text-[#fff7e6]">{formatCurrency(missionStrategy.initialBalance)}</div>
                        </div>
                        <div className="rounded-2xl border border-white/8 bg-white/5 p-3">
                          <div className="text-[10px] uppercase tracking-[.18em] text-[#fff7e6]/35">Dataset Window</div>
                          <div className="mt-1 text-sm font-black text-[#fff7e6]">{formatBacktestRange(missionStrategy.startDate, missionStrategy.endDate)}</div>
                        </div>
                        <div className="rounded-2xl border border-white/8 bg-white/5 p-3">
                          <div className="text-[10px] uppercase tracking-[.18em] text-[#fff7e6]/35">Sharpe Ratio</div>
                          <div className="mt-1 text-sm font-black text-[#fff7e6]">
                            {missionStrategy.sharpeRatio != null ? Number(missionStrategy.sharpeRatio).toFixed(2) : "--"}
                          </div>
                        </div>
                        <div className="rounded-2xl border border-white/8 bg-white/5 p-3">
                          <div className="text-[10px] uppercase tracking-[.18em] text-[#fff7e6]/35">Trades</div>
                          <div className="mt-1 text-sm font-black text-[#fff7e6]">
                            {missionStrategy.totalTrades != null ? formatCompact(missionStrategy.totalTrades) : "--"}
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="rounded-[22px] border border-violet-400/14 bg-violet-400/8 p-4">
                      <div className="text-[10px] font-black uppercase tracking-[.18em] text-violet-200/70">Parameters</div>
                      {strategyParams.length ? (
                        <div className="mt-4 flex flex-wrap gap-2">
                          {strategyParams.map(([key, value]) => (
                            <span key={key} className="rounded-full border border-violet-300/16 bg-black/20 px-3 py-1.5 text-xs font-semibold text-[#f4ecff]">
                              {key.replace(/_/g, " ")}: {String(value)}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <div className="mt-3 text-sm text-[#fff7e6]/55">Parameters will appear once the strategy payload is available.</div>
                      )}
                      <div className="mt-5 grid gap-3">
                        <div className="rounded-2xl border border-violet-300/16 bg-black/20 p-3">
                          <div className="text-[10px] uppercase tracking-[.18em] text-[#fff7e6]/35">Expected Payoff</div>
                          <div className="mt-1 text-sm font-black text-[#fff7e6]">{formatCurrency(missionStrategy.expectedPayoff)}</div>
                        </div>
                        <div className="rounded-2xl border border-violet-300/16 bg-black/20 p-3">
                          <div className="text-[10px] uppercase tracking-[.18em] text-[#fff7e6]/35">Recovery Factor</div>
                          <div className="mt-1 text-sm font-black text-[#fff7e6]">
                            {missionStrategy.recoveryFactor != null ? Number(missionStrategy.recoveryFactor).toFixed(2) : "--"}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </>
              ) : null}
            </div>

          </>
        )}
      </ShellCard>

      <ShellCard className="p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <PanelHeader title="Generated Strategies" action={`${generatedStrategies.length} saved`} />
            <h2 className="text-2xl font-black">All generated strategies in order</h2>
            <p className="mt-2 text-sm text-[#fff7e6]/52">
              The newest generated strategies appear first. Click any strategy to open its full details.
            </p>
          </div>
          <div className="rounded-xl border border-[#f5b342]/20 bg-[#f5b342]/10 px-4 py-2 text-xs font-black text-[#f5b342]">
            Ordered by latest created
          </div>
        </div>

        {generatedStrategies.length ? (
          <div className="mt-6 overflow-hidden rounded-[24px] border border-[#f5b342]/10 bg-black/20">
            <div className="grid grid-cols-[72px_minmax(0,1.4fr)_120px_120px_150px] gap-3 border-b border-[#f5b342]/10 bg-[#f5b342]/8 px-4 py-4 text-[11px] font-black uppercase tracking-[.18em] text-[#fff7e6]/45">
              <div>Order</div>
              <div>Strategy</div>
              <div>Profit</div>
              <div>Status</div>
              <div>Created</div>
            </div>
            <div className="max-h-[420px] overflow-y-auto">
              {generatedStrategies.map((strategy, index) => (
                <button
                  key={strategy.id}
                  onClick={() => openMissionStrategy(strategy.id)}
                  className="grid w-full grid-cols-[72px_minmax(0,1.4fr)_120px_120px_150px] gap-3 border-b border-[#f5b342]/10 px-4 py-4 text-left transition hover:bg-[#f5b342]/8"
                >
                  <div className="text-sm font-black text-[#f5b342]">#{index + 1}</div>
                  <div className="min-w-0">
                    <div className="truncate text-sm font-black text-[#fff7e6]">{strategy.name}</div>
                    <div className="mt-1 truncate text-xs text-[#fff7e6]/42">
                      {strategy.symbol} / {strategy.timeframe} / {strategy.type}
                    </div>
                  </div>
                  <div className={cn("text-sm font-black", (strategy.netProfit ?? 0) >= 0 ? "text-emerald-300" : "text-red-300")}>
                    {strategy.profit}
                  </div>
                  <div>
                    <span className="rounded-full border border-[#f5b342]/20 bg-[#f5b342]/10 px-3 py-1 text-[10px] font-black uppercase tracking-[.18em] text-[#f5d18b]">
                      {strategy.status}
                    </span>
                  </div>
                  <div className="text-xs text-[#fff7e6]/48">{formatDateTime(strategy.createdAt)}</div>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="mt-6 rounded-[24px] border border-dashed border-[#f5b342]/18 bg-[#f5b342]/6 p-6 text-sm text-[#fff7e6]/55">
            No generated strategies are saved yet.
          </div>
        )}
      </ShellCard>

      {(selectedMissionStrategy || strategyDetailLoading) && (
        <StrategyDetailsModal
          strategy={selectedMissionStrategy}
          loading={strategyDetailLoading}
          onClose={() => setSelectedMissionStrategy(null)}
          onBacktest={() => {}}
          onEvolve={() => {}}
          mockMode={false}
          contextLabel="Mission Control"
          showActions={false}
        />
      )}

    </PageShell>
  );
}

function GenericPage(props) {
  switch (props.page) {
    case "Mission Control":
      return <MissionControlPage refreshDashboard={props.refresh} />;
    case "Strategy Lab":
      return <StrategyLab {...props} />;
    case "Dataset Engine":
      return <DatasetEnginePage refreshDashboard={props.refresh} />;
    case "Agent Control Room":
      return <AgentRoom agents={props.agents} />;
    case "Evolution Lab":
      return (
        <EvolutionLab
          champion={props.champion}
          strategies={props.strategies}
          selectedEvolutionStrategy={props.selectedEvolutionStrategy}
          evolutionResult={props.evolutionResult}
          onSelectEvolutionStrategy={props.onSelectEvolutionStrategy}
          onEvolve={props.onEvolve}
          optimizeResult={props.optimizeResult}
          busyLabel={props.busyLabel}
        />
      );
    case "Portfolio Optimizer":
      return <PortfolioOptimizer portfolio={props.portfolio} />;
    case "Risk Center":
      return <RiskCenter risk={props.risk} backtests={props.backtests} />;
    case "Logs":
      return <LogsPage logs={props.logs} refresh={props.refresh} />;
    case "Settings":
      return <SettingsPage health={props.health} timeframe={props.timeframe} setTimeframe={props.setTimeframe} mockMode={props.mockMode} setMockMode={props.setMockMode} refresh={props.refresh} pipelineConnected={props.pipelineConnected} />;
    default:
      return null;
  }
}

export default function AgentGraphUI() {
  const [page, setPage] = useState("Command Center");
  const [timeframe, setTimeframe] = useState("M15");
  const [mockMode, setMockMode] = useState(true);
  const [stats, setStats] = useState(null);
  const [health, setHealth] = useState(null);
  const [strategies, setStrategies] = useState([]);
  const [agents, setAgents] = useState([]);
  const [logs, setLogs] = useState([]);
  const [backtests, setBacktests] = useState([]);
  const [risk, setRisk] = useState(null);
  const [portfolio, setPortfolio] = useState(null);
  const [winRateStats, setWinRateStats] = useState(null);
  const [latestBatch, setLatestBatch] = useState(null);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [selectedStrategy, setSelectedStrategy] = useState(null);
  const [selectedEvolutionStrategy, setSelectedEvolutionStrategy] = useState(null);
  const [evolutionResult, setEvolutionResult] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [busyLabel, setBusyLabel] = useState("");
  const [toast, setToast] = useState("");
  const [pipelineEvents, setPipelineEvents] = useState([]);
  const [pipelineConnected, setPipelineConnected] = useState(false);
  const [graphPhase, setGraphPhase] = useState(0);
  const toastTimeoutRef = useRef(null);

  const showToast = useCallback((message) => {
    setToast(message);
    window.clearTimeout(toastTimeoutRef.current);
    toastTimeoutRef.current = window.setTimeout(() => setToast(""), 3200);
  }, []);

  useEffect(() => () => window.clearTimeout(toastTimeoutRef.current), []);

  const refresh = useCallback(async () => {
    const [
      statsRes,
      healthRes,
      strategiesRes,
      agentsRes,
      logsRes,
      backtestsRes,
      riskRes,
      portfolioRes,
      winRateRes,
      batchRes,
    ] = await Promise.allSettled([
      getStats(),
      getHealth(),
      listStrategies(),
      getAllAgents(),
      getLogs(80, ""),
      listBacktests(),
      getRiskDashboard(),
      getPortfolioBestMix(5, 0, 30),
      getWinRateStats(),
      getLatestBatch(),
    ]);

    const failedSources = [];
    const readData = (result, fallback, label) => {
      if (result.status === "fulfilled") return result.value.data;
      failedSources.push(label);
      return fallback;
    };

    const statsData = readData(statsRes, null, "Stats");
    const healthData = readData(healthRes, { services: {} }, "Backend health");
    const strategiesData = readData(strategiesRes, [], "Strategies");
    const agentsData = readData(agentsRes, { all_agents: [] }, "Agents");
    const logsData = readData(logsRes, { logs: [] }, "Logs");
    const backtestsData = readData(backtestsRes, [], "Backtests");
    const riskData = readData(riskRes, {}, "Risk dashboard");
    const portfolioData = readData(portfolioRes, {}, "Portfolio");
    const winRateData = readData(winRateRes, {}, "Win-rate stats");
    const batchData = readData(batchRes, null, "Batch status");

    setStats(statsData);
    setHealth(healthData);
    setStrategies(
      [...strategiesData]
        .map((item) => normalizeStrategySummary(item))
        .sort((left, right) => (right.netProfit ?? Number.NEGATIVE_INFINITY) - (left.netProfit ?? Number.NEGATIVE_INFINITY)),
    );
    setAgents((agentsData.all_agents || agentsData.agents || []).map(normalizeAgent));
    setLogs(logsData.logs || []);
    setBacktests(backtestsData || []);
    setRisk(riskData);
    setPortfolio(portfolioData);
    setWinRateStats(winRateData);
    setLatestBatch(batchData);
    if (failedSources.length) {
      showToast(`Backend sync partial: ${failedSources.join(", ")}`);
    }
  }, [showToast]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      refresh().catch((error) => showToast(`Refresh failed: ${error.message}`));
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [refresh, showToast]);

  useEffect(() => {
    const socket = connectPipelineSocket(
      (message) => setPipelineEvents((current) => [{ ...message, time: new Date().toISOString() }, ...current].slice(0, 20)),
      (connected) => setPipelineConnected(connected),
    );
    return () => {
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
        socket.close();
      }
    };
  }, []);

  useEffect(() => {
    let frameId = 0;
    let lastTime = window.performance.now();

    const tick = (now) => {
      const delta = now - lastTime;
      lastTime = now;
      const speed = busyLabel ? 0.0085 : 0.0038;
      setGraphPhase((current) => current + (delta * speed));
      frameId = window.requestAnimationFrame(tick);
    };

    frameId = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frameId);
  }, [busyLabel]);

  const autoSystemState = useMemo(() => {
    if (!stats) return "idle";
    if ((stats.best_net_profit || 0) > 0 && (risk?.avg_drawdown || 0) < 15) {
      return "profit";
    }
    if ((risk?.max_drawdown || 0) > 20) {
      return "loss";
    }
    return "idle";
  }, [risk, stats]);

  const systemState = autoSystemState;
  const isGenerating = Boolean(busyLabel);

  const champion = strategies[0] || null;
  const optimizeResult = winRateStats?.latest_optimization || null;

  const openStrategy = useCallback(async (strategyId) => {
    setDetailLoading(true);
    try {
      const { data } = await getStrategy(strategyId);
      setSelectedStrategy(normalizeStrategyDetail(data));
    } catch (error) {
      showToast(`Strategy detail failed: ${error.message}`);
    } finally {
      setDetailLoading(false);
    }
  }, [showToast]);

  const loadStrategyByName = useCallback(async (strategyName) => {
    const { data } = await listStrategies();
    const match = (data || []).find((item) => item.name === strategyName);
    if (!match?.id) return null;
    const detail = await getStrategy(match.id);
    return normalizeStrategyDetail(detail.data);
  }, []);

  const openEvaluationForStrategy = useCallback((strategy) => {
    if (!strategy) return;
    setSelectedEvolutionStrategy(strategy);
    setEvolutionResult(null);
    setSelectedStrategy(null);
    setPage("Evolution Lab");
  }, []);

  const runWithBusy = useCallback(async (label, task, successMessage) => {
    setBusyLabel(label);
    try {
      const result = await task();
      await refresh();
      if (successMessage) showToast(successMessage(result));
      return result;
    } catch (error) {
      showToast(error.response?.data?.detail || error.message);
      throw error;
    } finally {
      setBusyLabel("");
    }
  }, [refresh, showToast]);

  const handleRunPipeline = useCallback(() => runWithBusy(
    "Running full AI research pipeline...",
    () => runFinalPipeline(mockMode, timeframe).then((response) => response.data),
    (data) => `Created ${data.strategy_name || data.strategy?.name}`,
  ), [mockMode, runWithBusy, timeframe]);

  const handleRunBatch = useCallback(() => runWithBusy(
    "Running 100 strategy batch test...",
    () => runBatchTest(100, mockMode, timeframe).then((response) => response.data),
    (data) => `Batch complete: ${data.profitable || 0} profitable`,
  ), [mockMode, runWithBusy, timeframe]);

  const handleOptimize = useCallback(() => runWithBusy(
    "Optimizing win rate...",
    () => optimizeStrategyWinRate(70, 5, 100, mockMode, timeframe).then((response) => response.data),
    (data) => `Optimizer reached ${data.final_win_rate?.toFixed?.(1) || "--"}%`,
  ), [mockMode, runWithBusy, timeframe]);

  const handleBacktest = useCallback((strategyName) => runWithBusy(
    mockMode ? "Running mock backtest..." : "Running MT5 backtest...",
    () => runBacktest(strategyName, mockMode).then((response) => response.data),
    () => `Backtest complete for ${strategyName}`,
  ).then(async () => {
    const refreshed = await getStrategy(selectedStrategy?.id || champion?.id || 0).catch(() => null);
    if (refreshed?.data) {
      setSelectedStrategy(normalizeStrategyDetail(refreshed.data));
    }
  }), [champion?.id, mockMode, runWithBusy, selectedStrategy?.id]);

  const handleEvolve = useCallback(async (strategyInput) => {
    const sourceStrategy = typeof strategyInput === "string"
      ? selectedEvolutionStrategy || selectedStrategy || strategies.find((item) => item.name === strategyInput) || champion
      : strategyInput;
    const strategyName = typeof strategyInput === "string" ? strategyInput : strategyInput?.name;
    if (!strategyName) return null;

    const result = await runWithBusy(
      "Running evolution...",
      () => evolveStrategy(strategyName, 3).then((response) => response.data),
      (data) => data.improved ? `Evolved ${data.evolved?.name || strategyName}` : `No improvement for ${strategyName}`,
    );

    const refreshedSource = sourceStrategy?.id ? await getStrategy(sourceStrategy.id).then((response) => normalizeStrategyDetail(response.data)).catch(() => sourceStrategy) : sourceStrategy;
    const fallbackEvolved = buildEvolutionSnapshot(refreshedSource || sourceStrategy || null, result);
    const refreshedEvolved = result?.improved && result?.evolved?.name
      ? await loadStrategyByName(result.evolved.name).catch(() => null)
      : null;

    setSelectedEvolutionStrategy(refreshedSource || sourceStrategy || null);
    setEvolutionResult({
      ...result,
      sourceStrategy: refreshedSource || sourceStrategy || null,
      evolvedStrategy: mergeEvolutionStrategy(refreshedEvolved, fallbackEvolved),
    });
    setPage("Evolution Lab");
    return result;
  }, [champion, loadStrategyByName, runWithBusy, selectedEvolutionStrategy, selectedStrategy, strategies]);

  return (
    <div className="min-h-screen bg-[#050403] text-[#fff7e6]">
      <HoverSidebar page={page} setPage={(nextPage) => { setPage(nextPage); setSelectedStrategy(null); }} health={health} />
      {page === "Command Center" ? (
        <CommandCenter
          timeframe={timeframe}
          setTimeframe={setTimeframe}
          systemState={systemState}
          stats={stats}
          health={health}
          agents={agents}
          selectedAgent={selectedAgent}
          setSelectedAgent={setSelectedAgent}
          events={pipelineEvents}
          busyLabel={busyLabel}
          pipelineConnected={pipelineConnected}
          mockMode={mockMode}
          onRunPipeline={handleRunPipeline}
          onRunBatch={handleRunBatch}
          onOptimize={handleOptimize}
          latestBatch={latestBatch}
          optimizerResult={optimizeResult}
          isGenerating={isGenerating}
          graphPhase={graphPhase}
        />
      ) : (
        <div className="pl-[18px]">
          <Topbar page={page} timeframe={timeframe} setTimeframe={setTimeframe} mockMode={mockMode} setMockMode={setMockMode} onGenerate={handleRunPipeline} busyLabel={busyLabel} />
          <main className="mx-auto max-w-[1680px] px-6 py-8">
            <GenericPage
              page={page}
              agents={agents}
              champion={champion}
              portfolio={portfolio}
              risk={risk}
              backtests={backtests}
              logs={logs}
              health={health}
              timeframe={timeframe}
              setTimeframe={setTimeframe}
              mockMode={mockMode}
              setMockMode={setMockMode}
              pipelineConnected={pipelineConnected}
              refresh={refresh}
              strategies={strategies}
              selectedStrategy={selectedStrategy}
              selectedEvolutionStrategy={selectedEvolutionStrategy}
              evolutionResult={evolutionResult}
              detailLoading={detailLoading}
              onOpenStrategy={openStrategy}
              onCloseStrategy={() => setSelectedStrategy(null)}
              onOpenEvaluation={openEvaluationForStrategy}
              onSelectEvolutionStrategy={(strategy) => {
                setSelectedEvolutionStrategy(strategy);
                setEvolutionResult(null);
              }}
              onRunPipeline={handleRunPipeline}
              onBacktest={handleBacktest}
              onEvolve={handleEvolve}
              optimizeResult={optimizeResult}
              busyLabel={busyLabel}
            />
          </main>
        </div>
      )}
      <Toast message={toast} />
    </div>
  );
}
