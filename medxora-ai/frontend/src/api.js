/**
 * api.js - Axios client for the MedXora AI backend
 *
 * Local development:
 * - default REST traffic uses the Vite proxy via relative "/api"
 * - default websocket traffic uses the current browser host via "/ws/pipeline"
 *
 * Override with:
 * - VITE_API_BASE_URL
 * - VITE_PIPELINE_WS_URL
 */

import axios from "axios";

const localHosts = new Set(["localhost", "127.0.0.1"]);
const hasWindow = typeof window !== "undefined";
const isLocalBrowser = hasWindow && localHosts.has(window.location.hostname);

const sanitizeUrl = (value) => String(value || "").replace(/\/$/, "");

const resolveApiBaseUrl = () => {
  const configured = sanitizeUrl(import.meta.env.VITE_API_BASE_URL);
  if (configured) return configured;
  if (isLocalBrowser) return "";
  return "http://127.0.0.1:8000";
};

const resolvePipelineWsUrl = (apiBaseUrl) => {
  const configured = sanitizeUrl(import.meta.env.VITE_PIPELINE_WS_URL);
  if (configured) return configured;

  if (apiBaseUrl) {
    return `${apiBaseUrl.replace(/^http/, "ws")}/ws/pipeline`;
  }

  if (hasWindow) {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    return `${protocol}://${window.location.host}/ws/pipeline`;
  }

  return "ws://127.0.0.1:8000/ws/pipeline";
};

export const API_BASE_URL = resolveApiBaseUrl();
export const PIPELINE_WS_URL = resolvePipelineWsUrl(API_BASE_URL);

const api = axios.create({
  baseURL: API_BASE_URL || undefined,
  timeout: 20000,
  headers: {
    Accept: "application/json",
  },
});

const longRunningApi = axios.create({
  baseURL: API_BASE_URL || undefined,
  timeout: 0,
  headers: {
    Accept: "application/json",
  },
});

const responseErrorHandler = (error) => {
  const detail =
    error?.response?.data?.detail ||
    error?.response?.data?.message ||
    error?.response?.data?.error ||
    error?.message ||
    "Request failed";

  return Promise.reject(new Error(detail));
};

api.interceptors.response.use((response) => response, responseErrorHandler);
longRunningApi.interceptors.response.use((response) => response, responseErrorHandler);

// -- Phase 2: Strategy Generator -------------------------------------------------------
export const generateStrategy = () => api.get("/api/strategy/generate");
export const generateStrategyWithTimeframe = (timeframe) =>
  api.get("/api/strategy/generate", { params: { timeframe } });

// -- Phase 3: MQL5 Code Generator ------------------------------------------------------
export const generateMql5Pipeline = (timeframe = "M15") =>
  api.get("/api/strategy/generate-mql5", { params: { timeframe } });
export const generateCode = (strategy) => api.post("/api/strategy/generate-code", strategy);
export const downloadMql5Url = (name) => `${API_BASE_URL}/api/strategy/download/${name}`;

// -- Risk check ------------------------------------------------------------------------
export const riskCheck = (strategy) => api.post("/api/strategy/risk-check", strategy);

// -- Phase 5: MT5 Config Generator -----------------------------------------------------
export const createBacktestConfig = (name, params = {}) =>
  api.get(`/api/backtest/create-config/${name}`, { params });

// -- Phase 6: MT5 Auto Backtest Runner -------------------------------------------------
export const runMt5Backtest = (name) => api.get(`/api/backtest/run/${name}`);
export const runBacktest = (name, mock = true) =>
  api.post(`/api/backtest/${name}?mock=${mock}`);

// -- Phase 7: Backtest Report Parser ---------------------------------------------------
export const parseBacktestReport = (name) => api.get(`/api/backtest/parse/${name}`);

// -- Phase 9: Strategy APIs ------------------------------------------------------------
export const listStrategies = () => api.get("/api/strategies");
export const getStrategy = (id) => api.get(`/api/strategies/${id}`);
export const getStrategyCode = (id) => api.get(`/api/strategies/${id}/code`);
export const getStrategyBacktest = (id) => api.get(`/api/strategies/${id}/backtest`);

// -- Phase 10: Dashboard stats ---------------------------------------------------------
export const getStats = () => api.get("/api/dashboard/stats");
export const getHealth = () => api.get("/api/health");
export const listBacktests = () => api.get("/api/backtest/results");
export const getDatasetStatus = () => api.get("/api/datasets/status");
export const convertMT5EURUSD = () => longRunningApi.post("/api/datasets/convert-mt5-eurusd");
export const generateEURUSDOHLCV = () => longRunningApi.post("/api/datasets/generate-ohlcv-eurusd");
export const runEURUSDBacktest = (payload) => longRunningApi.post("/api/backtest/eurusd-demo", payload);

// -- Phase 9: Full Pipeline ------------------------------------------------------------
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
export const getPipelineCheckpoints = (name) => api.get(`/api/pipeline/checkpoints/${name}`);

// -- Phase 12: Evolution Engine --------------------------------------------------------
export const evolveStrategy = (name, generations = 3) =>
  longRunningApi.post(`/api/strategy/${name}/evolve?generations=${generations}`);

// -- Phase 13: AI Agents ---------------------------------------------------------------
export const listAgents = () => api.get("/api/agents");
export const getAgentReview = (name) => api.get(`/api/strategy/${name}/agent-review`);
export const getStrategyMemory = (name) => api.get(`/api/memory/strategy/${name}`);

// -- Phase 14: Gemini AI Analyst -------------------------------------------------------
export const aiAnalyze = (name) => api.post(`/api/strategy/${name}/ai-analyze`);

// -- Phase 15: System Logs -------------------------------------------------------------
export const getLogs = (limit = 100, level = "") =>
  api.get("/api/logs", { params: { limit, level } });
export const getIntegrationSettings = () => api.get("/api/integrations/settings");
export const saveIntegrationSettings = (payload) => api.post("/api/integrations/settings", payload);

// -- Strategy Types --------------------------------------------------------------------
export const listStrategyTypes = () => api.get("/api/strategy/types");

// -- Agent Stats / Leaderboard ---------------------------------------------------------
export const getAgentStats = () => api.get("/api/agents/stats");
export const getAllAgents = () => api.get("/api/agents/all");

// -- Monte Carlo -----------------------------------------------------------------------
export const runMonteCarlo = (name, simulations = 1000) =>
  api.post(`/api/strategy/${name}/monte-carlo`, null, { params: { simulations } });
export const getMonteCarloAgent = (name, simulations = 1000) =>
  api.get(`/api/strategy/${name}/monte-carlo`, { params: { simulations } });

// -- Production Readiness --------------------------------------------------------------
export const checkProductionReady = (name) =>
  api.get(`/api/strategy/${name}/production-ready`);

// -- Full AI Research Pipeline ---------------------------------------------------------
export const runFullResearchPipeline = (mock = true, timeframe = "M15", strategy_type = null) => {
  const params = { mock, timeframe };
  if (strategy_type) params.strategy_type = strategy_type;
  return api.post("/api/pipeline/full-research", null, { params });
};

// -- Portfolio Intelligence ------------------------------------------------------------
export const getPortfolioBestMix = (maxStrategies = 5, minProfit = 0, maxDrawdown = 30) =>
  api.get("/api/portfolio/best-mix", {
    params: { max_strategies: maxStrategies, min_profit: minProfit, max_drawdown: maxDrawdown },
  });
export const getPortfolioRebalance = () => api.get("/api/portfolio/rebalance");

// -- Risk Dashboard --------------------------------------------------------------------
export const getRiskDashboard = () => api.get("/api/risk/dashboard");

// -- Orchestration ---------------------------------------------------------------------
export const orchestrateStrategy = (name, mock = true) =>
  api.post(`/api/strategy/${name}/orchestrate`, null, { params: { mock } });

// -- Intelligence Agents (v2) ----------------------------------------------------------
export const getSentimentAgent = (name) => api.get(`/api/strategy/${name}/sentiment`);
export const getMacroAgent = (name) => api.get(`/api/strategy/${name}/macro`);
export const getSeasonalityAgent = (name) => api.get(`/api/strategy/${name}/seasonality`);
export const getDrawdownRecovery = (name) => api.get(`/api/strategy/${name}/drawdown-recovery`);
export const getMultiSymbolCorr = (name) => api.get(`/api/strategy/${name}/multi-symbol-correlation`);
export const getRegimeChange = (name) => api.get(`/api/strategy/${name}/regime-change`);
export const getSlippageAgent = (name) => api.get(`/api/strategy/${name}/slippage`);
export const getRetirementCheck = (name) => api.get(`/api/strategy/${name}/retirement-check`);
export const getAlerts = (name, profitTarget = 1000, maxDrawdown = 20) =>
  api.get(`/api/strategy/${name}/alerts`, {
    params: { profit_target: profitTarget, max_drawdown_limit: maxDrawdown },
  });
export const getBenchmarkAgent = (name) => api.get(`/api/strategy/${name}/benchmark`);
export const getFullIntelligence = (name) => api.get(`/api/strategy/${name}/full-intelligence`);

// -- Advanced Agent endpoints ----------------------------------------------------------
export const getRegimeAgent = (name) => api.get(`/api/strategy/${name}/regime`);
export const getOverfitAgent = (name) => api.get(`/api/strategy/${name}/overfit`);
export const getSessionsAgent = (name) => api.get(`/api/strategy/${name}/sessions`);
export const getAdaptiveRisk = (name) => api.get(`/api/strategy/${name}/adaptive-risk`);
export const getCorrelationAgent = (name) => api.get(`/api/strategy/${name}/correlation`);
export const getDebateAgent = (name) => api.get(`/api/strategy/${name}/debate`);
export const getMultiTimeframeAgent = (name) => api.get(`/api/strategy/${name}/multi-timeframe`);
export const getNewsSentimentNlpAgent = (name) => api.get(`/api/strategy/${name}/news-sentiment-nlp`);
export const getRegimeAdaptiveAgent = (name) => api.get(`/api/strategy/${name}/regime-adaptive`);

// -- Compare strategies ----------------------------------------------------------------
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

// -- Hackathon: Mission Control --------------------------------------------------------
export const startMission = (goal, pair = "EURUSD", timeframe = "M15") =>
  longRunningApi.post("/api/mission/start", { user_goal: goal, pair, timeframe });
export const listMissions = (limit = 20) => api.get("/api/mission/list", { params: { limit } });
export const getMission = (id) => api.get(`/api/mission/${id}`);
export const advanceMission = (id) => longRunningApi.post(`/api/mission/${id}/advance`);
export const approveStep = (missionId, stepId, approved, notes = "") =>
  longRunningApi.post(`/api/mission/${missionId}/approve-step`, { step_id: stepId, approved, notes });
export const pauseMission = (id) => api.post(`/api/mission/${id}/pause`);
export const resumeMission = (id) => longRunningApi.post(`/api/mission/${id}/resume`);
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

// -- v2 unified APIs ------------------------------------------------------------------
export const getActiveMission = () => api.get("/api/missions/active");
export const getMissionEvents = (missionId) => api.get(`/api/missions/${missionId}/events`);
export const getAgentsStatus = () => api.get("/api/agents/status");
export const getDataSources = () => api.get("/api/data/sources");
export const getUploadedDatasets = () => api.get("/api/data/uploads");
export const validateDataset = (payload) => api.post("/api/data/validate", payload);
export const resampleDataset = (payload) => api.post("/api/data/resample", payload);
export const getMT5Accounts = () => api.get("/api/mt5/accounts");
export const addMT5Account = (payload) => api.post("/api/mt5/accounts", payload);
export const updateMT5Account = (accountId, payload) => api.put(`/api/mt5/accounts/${accountId}`, payload);
export const deleteMT5Account = (accountId) => api.delete(`/api/mt5/accounts/${accountId}`);
export const testMT5Connection = (accountId) => api.post(`/api/mt5/accounts/${accountId}/test-connection`);
export const setActiveMT5Account = (accountId) => api.post(`/api/mt5/accounts/${accountId}/set-active`);
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

// -- Agentic foundation endpoints ------------------------------------------------------
export const createMission = (payload) => longRunningApi.post('/api/missions/create', payload);
export const getAgents = () => api.get('/api/agents');
export const runAgent = (payload) => api.post('/api/agents/run', payload);
export const exportMQL5 = (strategyId) => api.post(`/api/strategies/${strategyId}/export-mql5`);
export const runBacktestV2 = (payload) => api.post('/api/backtest/run', payload);
export const getBacktest = (backtestId) => api.get(`/api/backtest/${backtestId}`);
export const getLeaderboard = () => api.get('/api/leaderboard');
export const getPortfolio = () => api.get('/api/portfolio');
export const getSystemHealth = () => api.get('/api/system/health');
export const getCoreAgents = () => api.get('/api/agents/core');
export const getAgent = (agentId) => api.get(`/api/agents/${agentId}`);
export const runAgentById = (agentId, payload) => api.post(`/api/agents/${agentId}/run`, payload);
export const getMissionAgents = (missionId) => api.get(`/api/missions/${missionId}/agents`);
export const getStrategyFamilyTree = (strategyId) => api.get(`/api/strategies/${strategyId}/family-tree`);
export const getMissionFamilyTree = (missionId) => api.get(`/api/missions/${missionId}/family-tree`);
export const getStrategyRobustness = (strategyId) => api.get(`/api/strategies/${strategyId}/robustness`);
export const calculateRobustness = (payload) => api.post('/api/robustness/calculate', payload);
export const getStrategyAuditTrail = (strategyId) => api.get(`/api/strategies/${strategyId}/audit-trail`);
export const getMissionAuditTrail = (missionId) => api.get(`/api/missions/${missionId}/audit-trail`);
export const getMQL5Export = (strategyId) => api.get(`/api/strategies/${strategyId}/mql5-export`);
export const compileMQL5 = (payload) => api.post('/api/mql5/compile', payload);
export const runMQL5Backtest = (payload) => api.post('/api/mql5/backtest', payload);
export const getMQL5Exports = () => api.get('/api/mql5/exports');
export const getMQL5ExportById = (exportId) => api.get(`/api/mql5/exports/${exportId}`);
export const requestStrategyApproval = (strategyId, payload) => api.post(`/api/strategies/${strategyId}/request-approval`, payload);
export const getPendingApprovals = () => api.get('/api/approvals/pending');
export const approveRequest = (approvalId, payload={}) => api.post(`/api/approvals/${approvalId}/approve`, payload);
export const rejectRequest = (approvalId, payload={}) => api.post(`/api/approvals/${approvalId}/reject`, payload);

export const getApiStatus = () => api.get('/api/status');
