/**
 * api.js — Axios client for the MedXora AI backend
 *
 * Base URL: http://127.0.0.1:8000  (FastAPI, running via uvicorn)
 *
 * All functions return an Axios response promise.
 * Caller receives: { data, status, headers, ... }
 */

import axios from "axios";

const localHosts = new Set(["localhost", "127.0.0.1"]);
const browserOrigin = typeof window !== "undefined" ? window.location.origin : "";
const defaultBaseUrl =
  typeof window !== "undefined" && localHosts.has(window.location.hostname)
    ? "http://127.0.0.1:8000"
    : browserOrigin || "http://127.0.0.1:8000";

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || defaultBaseUrl).replace(/\/$/, "");
export const PIPELINE_WS_URL = API_BASE_URL.replace(/^http/, "ws") + "/ws/pipeline";

const api = axios.create({ baseURL: API_BASE_URL });

// ── Phase 2: Strategy Generator ───────────────────────────────────────────────
/** Generate a random strategy JSON preview (no DB save, no file written). */
export const generateStrategy = () => api.get("/api/strategy/generate");
export const generateStrategyWithTimeframe = (timeframe) =>
  api.get("/api/strategy/generate", { params: { timeframe } });

// ── Phase 3: MQL5 Code Generator ──────────────────────────────────────────────
/** One-shot: generate strategy + write .mq5 + save to DB. */
export const generateMql5Pipeline = (timeframe = "M15") =>
  api.get("/api/strategy/generate-mql5", { params: { timeframe } });
/** Save an existing strategy JSON to DB and write its .mq5 file. */
export const generateCode = (strategy) => api.post("/api/strategy/generate-code", strategy);
/** Download .mq5 file as a browser attachment. Returns a URL string (not a promise). */
export const downloadMql5Url = (name) =>
  `${API_BASE_URL}/api/strategy/download/${name}`;

// ── Risk check ────────────────────────────────────────────────────────────────
export const riskCheck = (strategy) => api.post("/api/strategy/risk-check", strategy);

// ── Phase 5: MT5 Config Generator ─────────────────────────────────────────────
/** Create MT5 tester .ini config for a saved strategy. */
export const createBacktestConfig = (name, params = {}) =>
  api.get(`/api/backtest/create-config/${name}`, { params });

// ── Phase 6: MT5 Auto Backtest Runner ─────────────────────────────────────────
/** Launch MT5 and run a real backtest (requires MT5 installed). */
export const runMt5Backtest = (name) => api.get(`/api/backtest/run/${name}`);
/**
 * Run a mock or real backtest and save the result to the DB.
 * @param {string}  name  strategy name
 * @param {boolean} mock  true = instant seeded mock, false = real MT5 run
 */
export const runBacktest = (name, mock = true) =>
  api.post(`/api/backtest/${name}?mock=${mock}`);

// ── Phase 7: Backtest Report Parser ───────────────────────────────────────────
/** Parse the latest MT5 HTML report for a strategy. */
export const parseBacktestReport = (name) => api.get(`/api/backtest/parse/${name}`);

// ── Phase 9: Strategy APIs ────────────────────────────────────────────────────
export const listStrategies = () => api.get("/api/strategies");
export const getStrategy    = (id) => api.get(`/api/strategies/${id}`);
/** Return only the MQL5 source code for a strategy. */
export const getStrategyCode    = (id) => api.get(`/api/strategies/${id}/code`);
/** Return all backtest results for a strategy. */
export const getStrategyBacktest = (id) => api.get(`/api/strategies/${id}/backtest`);

// ── Phase 10: Dashboard stats ─────────────────────────────────────────────────
export const getStats = () => api.get("/api/dashboard/stats");
export const getHealth = () => api.get("/api/health");
/** Most recent backtest results across all strategies. */
export const listBacktests = () => api.get("/api/backtest/results");

// ── Phase 9: Full Pipeline ────────────────────────────────────────────────────
/**
 * One-shot pipeline: generate strategy → .mq5 → backtest → save → return metrics.
 * @param {boolean} mock  true = instant mock (default), false = real MT5 run
 */
export const runPipeline = (mock = true, timeframe = "M15") =>
  api.post("/api/pipeline/create-and-backtest", null, { params: { mock, timeframe } });
export const runLivePipeline = (mock = true, timeframe = "M15") =>
  api.post("/api/pipeline/live", null, { params: { mock, timeframe } });
export const runFinalPipeline = (mock = true, timeframe = "M15") =>
  api.post("/api/pipeline/final", null, { params: { mock, timeframe } });
export const runBatchTest = (count = 100, mock = true, timeframe = "M15") =>
  api.post("/api/batch/run", null, { params: { count, mock, timeframe } });
export const getLatestBatch = () => api.get("/api/batch/latest");
export const getWinRateStats = () => api.get("/api/stats/win-rate");
export const optimizeStrategyWinRate = (target = 70, generations = 5, batchSize = 100, mock = true, timeframe = "M15") =>
  api.post("/api/optimize/win-rate", null, {
    params: { target, generations, batch_size: batchSize, mock, timeframe },
  });
export const filterCheck = (payload) => api.post("/api/strategy/filter-check", payload);
export const resumeLivePipeline = (name, mock = true) =>
  api.post(`/api/pipeline/live/resume/${name}`, null, { params: { mock } });
export const getPipelineCheckpoints = (name) =>
  api.get(`/api/pipeline/checkpoints/${name}`);

// ── Phase 12: Evolution Engine ────────────────────────────────────────────────
export const evolveStrategy = (name, generations = 3) =>
  api.post(`/api/strategy/${name}/evolve?generations=${generations}`);

// ── Phase 13: AI Agents ───────────────────────────────────────────────────────
export const listAgents = () => api.get("/api/agents");
export const getAgentReview = (name) => api.get(`/api/strategy/${name}/agent-review`);
export const getStrategyMemory = (name) => api.get(`/api/memory/strategy/${name}`);

// ── Phase 14: Gemini AI Analyst ───────────────────────────────────────────────
export const aiAnalyze = (name) => api.post(`/api/strategy/${name}/ai-analyze`);

// ── Phase 15: System Logs ─────────────────────────────────────────────────────
/**
 * Fetch system log entries.
 * @param {number} limit  max entries (default 100)
 * @param {string} level  "INFO" | "WARN" | "ERROR" | "" (all)
 */
export const getLogs = (limit = 100, level = "") =>
  api.get("/api/logs", { params: { limit, level } });

// ── Strategy Types ────────────────────────────────────────────────────────────
export const listStrategyTypes = () => api.get("/api/strategy/types");

// ── Agent Stats / Leaderboard ─────────────────────────────────────────────────
export const getAgentStats = () => api.get("/api/agents/stats");
export const getAllAgents   = () => api.get("/api/agents/all");

// ── Monte Carlo ───────────────────────────────────────────────────────────────
export const runMonteCarlo = (name, simulations = 1000) =>
  api.post(`/api/strategy/${name}/monte-carlo`, null, { params: { simulations } });
export const getMonteCarloAgent = (name, simulations = 1000) =>
  api.get(`/api/strategy/${name}/monte-carlo`, { params: { simulations } });

// ── Production Readiness ──────────────────────────────────────────────────────
export const checkProductionReady = (name) =>
  api.get(`/api/strategy/${name}/production-ready`);

// ── Full AI Research Pipeline ─────────────────────────────────────────────────
export const runFullResearchPipeline = (mock = true, timeframe = "M15", strategy_type = null) => {
  const params = { mock, timeframe };
  if (strategy_type) params.strategy_type = strategy_type;
  return api.post("/api/pipeline/full-research", null, { params });
};

// ── Portfolio Intelligence ────────────────────────────────────────────────────
export const getPortfolioBestMix = (maxStrategies = 5, minProfit = 0, maxDrawdown = 30) =>
  api.get("/api/portfolio/best-mix", { params: { max_strategies: maxStrategies, min_profit: minProfit, max_drawdown: maxDrawdown } });
export const getPortfolioRebalance = () => api.get("/api/portfolio/rebalance");

// ── Risk Dashboard ────────────────────────────────────────────────────────────
export const getRiskDashboard = () => api.get("/api/risk/dashboard");

// ── Orchestration ─────────────────────────────────────────────────────────────
export const orchestrateStrategy = (name, mock = true) =>
  api.post(`/api/strategy/${name}/orchestrate`, null, { params: { mock } });

// ── Intelligence Agents (v2) ──────────────────────────────────────────────────
export const getSentimentAgent   = (name) => api.get(`/api/strategy/${name}/sentiment`);
export const getMacroAgent       = (name) => api.get(`/api/strategy/${name}/macro`);
export const getSeasonalityAgent = (name) => api.get(`/api/strategy/${name}/seasonality`);
export const getDrawdownRecovery = (name) => api.get(`/api/strategy/${name}/drawdown-recovery`);
export const getMultiSymbolCorr  = (name) => api.get(`/api/strategy/${name}/multi-symbol-correlation`);
export const getRegimeChange     = (name) => api.get(`/api/strategy/${name}/regime-change`);
export const getSlippageAgent    = (name) => api.get(`/api/strategy/${name}/slippage`);
export const getRetirementCheck  = (name) => api.get(`/api/strategy/${name}/retirement-check`);
export const getAlerts           = (name, profitTarget = 1000, maxDrawdown = 20) =>
  api.get(`/api/strategy/${name}/alerts`, { params: { profit_target: profitTarget, max_drawdown_limit: maxDrawdown } });
export const getBenchmarkAgent   = (name) => api.get(`/api/strategy/${name}/benchmark`);
export const getFullIntelligence = (name) => api.get(`/api/strategy/${name}/full-intelligence`);

// ── Advanced Agent endpoints ──────────────────────────────────────────────────
export const getRegimeAgent      = (name) => api.get(`/api/strategy/${name}/regime`);
export const getOverfitAgent     = (name) => api.get(`/api/strategy/${name}/overfit`);
export const getSessionsAgent    = (name) => api.get(`/api/strategy/${name}/sessions`);
export const getAdaptiveRisk     = (name) => api.get(`/api/strategy/${name}/adaptive-risk`);
export const getCorrelationAgent = (name) => api.get(`/api/strategy/${name}/correlation`);

// ── Compare strategies ────────────────────────────────────────────────────────
export const compareStrategies = (ids) =>
  Promise.all(ids.map((id) => api.get(`/api/strategies/${id}`)));

export const getStrategies = listStrategies;
export const getStrategyDetail = getStrategy;
export function connectPipelineSocket(onMessage, onStatusChange) {
  const ws = new WebSocket(PIPELINE_WS_URL);

  ws.onopen = () => onStatusChange?.(true);
  ws.onclose = () => onStatusChange?.(false);
  ws.onerror = () => onStatusChange?.(false);
  ws.onmessage = (event) => {
    onMessage(JSON.parse(event.data));
  };

  return ws;
}

// ── Hackathon: Mission Control ────────────────────────────────────────────────
export const startMission = (goal, pair = "EURUSD", timeframe = "M15") =>
  api.post("/api/mission/start", { user_goal: goal, pair, timeframe });
export const listMissions = (limit = 20) => api.get("/api/mission/list", { params: { limit } });
export const getMission = (id) => api.get(`/api/mission/${id}`);
export const advanceMission = (id) => api.post(`/api/mission/${id}/advance`);
export const approveStep = (missionId, stepId, approved, notes = "") =>
  api.post(`/api/mission/${missionId}/approve-step`, { step_id: stepId, approved, notes });
export const pauseMission = (id) => api.post(`/api/mission/${id}/pause`);
export const resumeMission = (id) => api.post(`/api/mission/${id}/resume`);
export const stopMission = (id) => api.post(`/api/mission/${id}/stop`);
export const getReasoningTrace = (id) => api.get(`/api/agent/reasoning-trace/${id}`);
export const agentPlan = (goal, pair = "EURUSD", timeframe = "M15") =>
  api.post("/api/agent/plan", null, { params: { goal, pair, timeframe } });
export const runJudgeDemo = () => api.post("/api/demo/run-judge-demo");
export const getDemoStatus = () => api.get("/api/demo/status");
export const getMcpStatus = () => api.get("/api/mcp/status");
export const searchStrategiesMcp = (query) => api.post("/api/mcp/search-strategies", query);
export const runMonteCarloValidation = (strategyId) =>
  api.post(`/api/validation/monte-carlo/${strategyId}`);
export const runWalkForwardValidation = (strategyId) =>
  api.post(`/api/validation/walk-forward/${strategyId}`);
export const getValidationReports = (strategyId) =>
  api.get(`/api/validation/report/${strategyId}`);
export const getStrategyLineage = (strategyId) =>
  api.get(`/api/strategy/${strategyId}/lineage`);
export const exportMql5WithApproval = (strategyId, missionId = null) =>
  api.post(`/api/strategy/${strategyId}/export-mql5`, null, missionId ? { params: { mission_id: missionId } } : {});
export const geminiCritiqueStrategy = (name) =>
  api.post(`/api/agent/critique/${name}`);
