import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  connectPipelineSocket,
  downloadMql5Url,
  evolveStrategy,
  getAllAgents,
  getHealth,
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
} from "./api";
import {
  startMission, listMissions, getMission, advanceMission, approveStep,
  pauseMission, resumeMission, stopMission, getReasoningTrace,
  runJudgeDemo, getMcpStatus, runMonteCarloValidation, getValidationReports,
} from "./api";

const GOLD = "#c99a45";
const GOLD_BRIGHT = "#f4d58d";
const SURFACE = "#11100e";
const TEXT = "#f8f1df";
const TIMEFRAMES = ["M1", "M15", "H1", "H4", "D1", "W1"];
const NAV = [
  ["Mission Control", "MC"],
  ["Command Center", "CC"],
  ["Strategy Lab", "SL"],
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
    role: agent.category || agent.role || "core",
    category: agent.category || "core",
    score: Math.max(55, Math.round((agent.weight || 0.7) * 100)),
    runs: agent.runs || 0,
    rejected: agent.strategies_rejected || 0,
    status: agent.description || "Watching the pipeline.",
    decision: agent.status || "active",
    capabilities: agent.capabilities || [],
    endpoint: agent.endpoint || "",
    weight: agent.weight || 0.7,
  };
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

function getAgentCategoryStyle(category) {
  return AGENT_CATEGORY_STYLES[category] || AGENT_CATEGORY_STYLES.core;
}

function compactAgentLabel(name) {
  return String(name || "Agent")
    .replace(/\bAgent\b/gi, "")
    .replace(/\s+/g, " ")
    .trim();
}

function buildAgentNetwork(agents, phase = 0, energetic = false, immersive = false) {
  const source = agents.length
    ? agents
    : Array.from({ length: 14 }, (_, index) =>
        normalizeAgent({ name: `Fallback Agent ${index + 1}`, category: ["technical", "risk", "research", "meta"][index % 4] }, index),
      );

  const core = { x: 460, y: 310 };
  const bounds = immersive
    ? { left: 122, right: 798, top: 152, bottom: 462 }
    : { left: 74, right: 846, top: 82, bottom: 500 };
  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
  const categoryAnchors = {
    technical: { x: bounds.left + 112, y: bounds.top + 28 },
    research: { x: bounds.right - 122, y: bounds.top + 24 },
    risk: { x: bounds.right - 54, y: core.y - 6 },
    intelligence: { x: bounds.right - 132, y: bounds.bottom - 22 },
    quantitative: { x: bounds.left + 156, y: bounds.bottom - 12 },
    meta: { x: bounds.left + 82, y: core.y + 16 },
    core,
  };
  const protectedRadius = immersive ? 156 : 116;
  const motionScale = energetic ? 1 : immersive ? 0.32 : 0.22;

  const nodes = source.map((agent, index) => {
    const style = getAgentCategoryStyle(agent.category);
    const seed = hashNumber(`${agent.name}-${agent.category}-${index}`);
    const anchor = categoryAnchors[agent.category] || categoryAnchors.core;
    const inwardAngle = Math.atan2(core.y - anchor.y, core.x - anchor.x);
    const spread = immersive ? 1.36 : 1.18;
    const spin = phase * motionScale * (0.02 + ((seed % 9) * 0.002));
    const fan = ((((seed % 1000) / 1000) - 0.5) * spread) + spin;
    const angle = inwardAngle + fan;
    const orbitBase = immersive ? (agent.category === "meta" ? 34 : 42) : agent.category === "meta" ? 26 : 34;
    const orbitRange = immersive ? (agent.category === "meta" ? 118 : 160) : agent.category === "meta" ? 92 : 128;
    const orbitWave = Math.sin(phase * (energetic ? 0.16 : 0.05) + index * 0.85 + (seed % 19)) * (immersive ? (energetic ? 10 : 6) : energetic ? 8 : 3);
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

  const minGapPadding = immersive ? 12 : 8;
  for (let iteration = 0; iteration < 5; iteration += 1) {
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
    sharpe: "--",
    trades: 0,
    params: strategy.parameters || {},
    netProfit: strategy.net_profit,
    winRate: strategy.win_rate,
    maxDrawdown: strategy.max_drawdown,
    profitFactor: strategy.profit_factor,
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
    monthlySeries: synthetic.monthly,
    yearlySeries: synthetic.yearly,
    dailySeries: synthetic.daily,
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

function HoverSidebar({ page, setPage, health }) {
  return (
    <aside className="fixed left-0 top-0 z-50 flex h-screen w-[300px] -translate-x-[254px] flex-col border-r border-[#f5b342]/20 bg-[#080501]/95 px-5 py-6 text-[#fff7e6] shadow-2xl shadow-black/50 backdrop-blur-xl transition-transform duration-300 hover:translate-x-0">
      <div className="absolute right-2 top-1/2 grid h-16 w-8 -translate-y-1/2 place-items-center rounded-full border border-[#f5b342]/20 bg-[#f5b342]/10 text-[#f5b342]">
        {" > "}
      </div>
      <div className="mb-7 flex items-center gap-3">
        <div className="grid h-12 w-12 place-items-center rounded-2xl bg-[#f5b342] shadow-lg shadow-[#f5b342]/20">
          <MedXoraLogo size={28} />
        </div>
        <div>
          <div className="text-lg font-black tracking-tight">MedXora AI</div>
          <div className="text-xs font-medium text-[#fff7e6]/45">Active Custom UI</div>
        </div>
      </div>
      <nav className="space-y-2">
        {NAV.map(([name, icon]) => (
          <button
            key={name}
            onClick={() => setPage(name)}
            className={cn(
              "flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left text-sm font-bold transition",
              page === name
                ? "bg-[#f5b342] text-black shadow-lg shadow-[#f5b342]/20"
                : "text-[#fff7e6]/62 hover:bg-[#f5b342]/10 hover:text-[#fff7e6]",
            )}
          >
            <span className="w-6 text-center">{icon}</span>
            <span>{name}</span>
          </button>
        ))}
      </nav>
      <ShellCard className="mt-auto p-4 text-xs">
        <div className="mb-3 font-black text-[#fff7e6]">System Status</div>
        {[
          ["FastAPI", serviceLabel(health?.services?.backend)],
          ["Database", serviceLabel(health?.services?.database)],
          ["MT5", serviceLabel(health?.services?.mt5_terminal)],
          ["Gemini", serviceLabel(health?.services?.gemini)],
        ].map(([name, status]) => (
          <div key={name} className="flex justify-between py-1 text-[#fff7e6]/55">
            <span>{name}</span>
            <b className={status === "Online" ? "text-emerald-400" : "text-[#f5b342]"}>{status}</b>
          </div>
        ))}
      </ShellCard>
    </aside>
  );
}

function AgentNetworkGraph({ agents, selectedAgent, onSelectAgent, systemState, stats, isGenerating, graphPhase, immersive = false }) {
  const theme = getReactiveTheme(systemState);
  const { nodes, edges, hubNode, core } = useMemo(
    () => buildAgentNetwork(agents, graphPhase, isGenerating, immersive),
    [agents, graphPhase, immersive, isGenerating],
  );
  const pulseRing = (Math.sin(graphPhase * 0.075) + 1) / 2;
  const secondaryPulse = (Math.cos(graphPhase * 0.058) + 1) / 2;

  return (
    <svg viewBox="0 0 920 620" className={cn("h-full w-full", immersive ? "" : "max-w-[1180px]")}>
      <defs>
        <radialGradient id="mx-field" cx="50%" cy="50%" r="58%">
          <stop offset="0%" stopColor={isGenerating ? "rgba(34,197,94,.24)" : immersive ? "rgba(0,212,255,.24)" : "rgba(0,212,255,.16)"} />
          <stop offset="55%" stopColor={isGenerating ? "rgba(20,184,166,.22)" : immersive ? "rgba(34,211,238,.16)" : theme.soft} />
          <stop offset="100%" stopColor="transparent" />
        </radialGradient>
        <linearGradient id="mx-edge" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor={isGenerating ? "rgba(16,185,129,.82)" : immersive ? "rgba(120,168,255,.72)" : "rgba(120,168,255,.58)"} />
          <stop offset="45%" stopColor={isGenerating ? "rgba(56,189,248,.72)" : immersive ? "rgba(216,145,255,.58)" : "rgba(216,145,255,.42)"} />
          <stop offset="100%" stopColor={isGenerating ? "rgba(244,114,182,.56)" : immersive ? "rgba(88,215,200,.54)" : "rgba(88,215,200,.38)"} />
        </linearGradient>
        <mask id="mx-core-cutout">
          <rect x="0" y="0" width="920" height="620" fill="white" />
          <circle cx={core.x} cy={core.y} r={immersive ? 118 : 86} fill="black" />
        </mask>
      </defs>
      <g>
        <rect
          x="26"
          y="24"
          width="868"
          height="572"
          rx="30"
          fill={immersive ? "rgba(2,4,7,.16)" : isGenerating ? "rgba(3,11,12,.94)" : "rgba(6,5,4,.92)"}
          stroke={immersive ? "rgba(45,212,191,.14)" : isGenerating ? "rgba(45,212,191,.18)" : "rgba(245,179,66,.14)"}
        />
        <circle cx={core.x} cy={core.y} r={immersive ? (isGenerating ? 302 : 286) : isGenerating ? 262 : 250} fill="url(#mx-field)" />
        <circle
          cx={core.x}
          cy={core.y}
          r={(immersive ? 108 : 88) + pulseRing * (immersive ? 18 : 10)}
          fill="none"
          stroke={isGenerating ? "rgba(52,211,153,.28)" : "rgba(120,168,255,.14)"}
          strokeWidth={immersive ? 1.2 : 1}
        />
        <circle
          cx={core.x}
          cy={core.y}
          r={(immersive ? 148 : 126) + secondaryPulse * (immersive ? 24 : 12)}
          fill="none"
          stroke={isGenerating ? "rgba(56,189,248,.2)" : "rgba(216,145,255,.12)"}
          strokeWidth={immersive ? 0.9 : 0.8}
        />
        <g mask="url(#mx-core-cutout)">
          {edges.map((edge) => {
            const from = nodes.find((node) => node.id === edge.from);
            const to = nodes.find((node) => node.id === edge.to);
            if (!from || !to) return null;

            const streamProgress = (((graphPhase * (edge.strength === "strong" ? 0.02 : edge.strength === "medium" ? 0.016 : 0.012)) + (edge.seed % 100) / 100) % 1 + 1) % 1;
            const streamProgress2 = (streamProgress + 0.38) % 1;
            const signalRadius = edge.strength === "strong" ? 2.6 : edge.strength === "medium" ? 2.1 : 1.7;
            const signalX = from.x + ((to.x - from.x) * streamProgress);
            const signalY = from.y + ((to.y - from.y) * streamProgress);
            const signalX2 = from.x + ((to.x - from.x) * streamProgress2);
            const signalY2 = from.y + ((to.y - from.y) * streamProgress2);

            return (
              <g key={`edge-${edge.from}-${edge.to}`}>
                <line
                  x1={from.x}
                  y1={from.y}
                  x2={to.x}
                  y2={to.y}
                  stroke="url(#mx-edge)"
                  strokeWidth={immersive ? (edge.strength === "strong" ? 2.3 : edge.strength === "medium" ? 1.6 : 1.15) : edge.strength === "strong" ? 1.85 : edge.strength === "medium" ? 1.3 : 0.9}
                  strokeOpacity={
                    isGenerating
                      ? edge.strength === "strong"
                        ? 0.95
                        : edge.strength === "medium"
                          ? 0.7
                          : 0.42
                      : immersive
                        ? edge.strength === "strong"
                          ? 0.92
                          : edge.strength === "medium"
                            ? 0.68
                            : 0.38
                        : edge.strength === "strong"
                          ? 0.85
                          : edge.strength === "medium"
                            ? 0.52
                            : 0.28
                  }
                />
                <circle cx={signalX} cy={signalY} r={signalRadius} fill={edge.strength === "strong" ? "#cffafe" : "#b8f7ef"} fillOpacity={isGenerating ? 0.95 : 0.68} />
                {(edge.strength === "strong" || immersive) ? (
                  <circle
                    cx={signalX2}
                    cy={signalY2}
                    r={Math.max(1.1, signalRadius - 0.4)}
                    fill={edge.strength === "strong" ? "#f5d0fe" : "#93c5fd"}
                    fillOpacity={isGenerating ? 0.74 : 0.42}
                  />
                ) : null}
              </g>
            );
          })}
        </g>
        <circle cx={core.x} cy={core.y} r={immersive ? (isGenerating ? 82 : 74) : isGenerating ? 68 : 60} fill={isGenerating ? "rgba(5,27,22,.95)" : "#09070d"} stroke={isGenerating ? "#22c55e" : theme.accent} strokeWidth="2.2" />
        <circle cx={core.x} cy={core.y} r={immersive ? (isGenerating ? 60 : 54) : isGenerating ? 50 : 44} fill={isGenerating ? "rgba(8,39,31,.92)" : "#15111b"} stroke={isGenerating ? "rgba(34,197,94,.44)" : "rgba(217,70,239,.35)"} strokeWidth="1.2" />
        <text x={core.x} y={core.y - 12} textAnchor="middle" fill={isGenerating ? "#6ee7b7" : theme.accent} fontSize={immersive ? "19" : "15"} fontWeight="900">MedXora</text>
        <text x={core.x} y={core.y + 6} textAnchor="middle" fill={isGenerating ? "#cffafe" : "#f5d0fe"} fontSize={immersive ? "12" : "10"} fontWeight="800">
          {isGenerating ? "Generating Strategy" : "AI Command Core"}
        </text>
        <text x={core.x} y={core.y + (immersive ? 22 : 18)} textAnchor="middle" fill="#fff7e6" fontSize={immersive ? "9" : "8"}>{nodes.length} agents active</text>
        <text x={core.x} y={core.y + (immersive ? 37 : 31)} textAnchor="middle" fill="#fff7e6" fontSize={immersive ? "9" : "8"}>{stats?.totalStrategies || 0} strategies tracked</text>

        {nodes.map((agent) => {
          const active = selectedAgent?.id === agent.id;
          const labelOnRight = agent.x < 650;
          const labelX = agent.x + (labelOnRight ? 11 : -11);
          const labelAnchor = labelOnRight ? "start" : "end";
          const haloFill = immersive
            ? agent.glow.replace(".28", ".18").replace(".24", ".16")
            : "rgba(255,255,255,.03)";
          const pulseRadius = agent.size + 4 + (agent.pulse * (immersive ? 5 : 3));
          const satelliteRadius = agent.size + (immersive ? 12 : 8) + agent.orbitPulse * 3;
          const satelliteX = agent.x + Math.cos(agent.satelliteAngle) * satelliteRadius;
          const satelliteY = agent.y + Math.sin(agent.satelliteAngle) * satelliteRadius;

          return (
            <g key={agent.id} onClick={() => onSelectAgent(agent)} className="cursor-pointer">
              <circle
                cx={agent.x}
                cy={agent.y}
                r={pulseRadius}
                fill="none"
                stroke={agent.color}
                strokeOpacity={active ? 0.46 : immersive ? 0.24 : 0.14}
                strokeWidth={active ? 1.25 : 0.9}
              />
              <circle cx={agent.x} cy={agent.y} r={active ? agent.size + 9 : agent.size + (isGenerating ? 6 : 5)} fill={active ? agent.glow : haloFill} />
              <circle cx={agent.x} cy={agent.y} r={active ? agent.size + 3 : agent.size + 1.6} fill="#091117" stroke={active ? "#f8fafc" : agent.color} strokeWidth={active ? 1.9 : immersive ? 1.45 : 1.2} />
              <circle cx={agent.x} cy={agent.y} r={Math.max(2.8, agent.size - 0.2)} fill={agent.color} fillOpacity={active ? 0.96 : isGenerating ? 0.86 : immersive ? 0.88 : 0.74} />
              <line x1={agent.x} y1={agent.y} x2={satelliteX} y2={satelliteY} stroke={agent.color} strokeOpacity={immersive ? 0.2 : 0.12} strokeWidth="0.8" />
              <circle cx={satelliteX} cy={satelliteY} r={immersive ? 1.9 : 1.4} fill={agent.color} fillOpacity={0.9} />
              <text x={labelX} y={agent.y - 2} textAnchor={labelAnchor} fontSize="8.4" fill={active ? "#fff7e6" : "rgba(255,247,230,.82)"} fontWeight={active ? "800" : "600"}>
                {agent.label}
              </text>
              <text x={labelX} y={agent.y + 9} textAnchor={labelAnchor} fontSize="6.9" fill={active ? agent.color : "rgba(255,247,230,.56)"}>
                {agent.category}
              </text>
            </g>
          );
        })}
        {hubNode && !immersive ? (
          <text x="46" y="56" fill="#fff7e6" fontSize="11" fontWeight="800">
            Hub: {hubNode.name}
          </text>
        ) : null}
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
            <div className="mt-5 rounded-2xl border border-[#f5b342]/15 bg-[#f5b342]/8 p-4 text-sm text-[#fff7e6]/70">{agent.status}</div>
      <div className="mt-4 grid grid-cols-3 gap-3 text-center text-xs">
        <div className="rounded-2xl bg-[#f5b342]/8 p-3"><b className="block text-lg text-[#f5b342]">{agent.score}%</b>Score</div>
        <div className="rounded-2xl bg-[#f5b342]/8 p-3"><b className="block text-lg text-[#f5b342]">{agent.runs}</b>Runs</div>
        <div className="rounded-2xl bg-red-500/10 p-3"><b className="block text-lg text-red-400">{agent.rejected}</b>Reject</div>
      </div>
      <div className="mt-5 space-y-3 text-sm">
        <div className="rounded-2xl border border-[#f5b342]/10 bg-black/30 px-4 py-3 text-[#fff7e6]/65">Decision state: {agent.decision}</div>
        <div className="rounded-2xl border border-[#f5b342]/10 bg-black/30 px-4 py-3 text-[#fff7e6]/65">Pipeline role: {agent.role}</div>
        <div className="rounded-2xl border border-[#f5b342]/10 bg-black/30 px-4 py-3 text-[#fff7e6]/65" style={{ color: theme.text }}>Runtime note: {agent.status}</div>
        {agent.capabilities?.length ? (
          <div className="rounded-2xl border border-[#f5b342]/10 bg-black/30 px-4 py-3 text-[#fff7e6]/65">
            Capabilities: {agent.capabilities.slice(0, 4).join(", ")}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function CommandCenter({
  timeframe,
  setTimeframe,
  systemState,
  setSystemState,
  stats,
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
  const theme = getReactiveTheme(systemState);
  const metrics = [
    ["Strategies", formatCompact(stats?.total_strategies || 0), "Tracked"],
    ["Backtests", formatCompact(stats?.total_backtests || 0), "Stored"],
    ["Profitable", formatCompact(stats?.profitable_strategies || 0), "Positive"],
    ["Best Profit", formatCurrency(stats?.best_net_profit), "Champion"],
    ["Agents", String(agents.length || 0), "Active"],
    ["Batch", `${latestBatch?.profitable ?? 0}/${latestBatch?.tested ?? stats?.total_strategies ?? 0}`, "Profitable"],
    ["Optimizer", optimizerResult?.final_win_rate ? `${optimizerResult.final_win_rate.toFixed(1)}%` : "--", "Win rate"],
  ];

  return (
    <div className="relative h-screen overflow-hidden bg-[#050403] text-[#fff7e6]">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_45%,rgba(14,116,144,.10)_0%,transparent_40%,rgba(0,0,0,.38)_78%,rgba(0,0,0,.86)_100%)]" />
      <div className="pointer-events-none absolute inset-0 border-[3px]" style={{ borderColor: theme.accent, boxShadow: `inset 0 0 44px ${theme.soft}` }} />
      <div className="absolute inset-x-2 bottom-24 top-[128px] z-20 sm:inset-x-4 xl:inset-x-10 xl:bottom-24 xl:top-[148px]">
        <div className="absolute inset-0 rounded-[36px] bg-[radial-gradient(circle_at_50%_50%,rgba(34,211,238,.16),transparent_48%),radial-gradient(circle_at_50%_50%,rgba(16,185,129,.14),transparent_68%)]" />
        <div className="absolute inset-0 rounded-[36px] bg-[linear-gradient(180deg,rgba(5,4,3,.04),rgba(5,4,3,.28))]" />
        <AgentNetworkGraph
          agents={agents}
          selectedAgent={selectedAgent}
          onSelectAgent={setSelectedAgent}
          systemState={systemState}
          stats={{ totalStrategies: stats?.total_strategies }}
          isGenerating={isGenerating}
          graphPhase={graphPhase}
          immersive
        />
      </div>

      <div className="relative z-30 mx-auto flex h-full max-w-[1700px] flex-col px-6 pb-4 pt-4 sm:px-10 xl:px-16">
        <ShellCard className="shrink-0 bg-[#0c0a08]/56 p-4 sm:p-5">
          <div className="flex flex-wrap items-start justify-between gap-5">
            <div className="flex min-w-[250px] items-center gap-4">
              <div className="grid h-12 w-12 place-items-center rounded-2xl bg-[#f5b342] shadow-lg shadow-[#f5b342]/25">
                <MedXoraLogo size={32} />
              </div>
              <div>
                <div className="text-lg font-black tracking-wide">MedXora AI</div>
                <div className="text-[10px] uppercase tracking-[.24em] text-[#fff7e6]/42">Elite Agentic Trading System</div>
              </div>
            </div>

            <div className="min-w-[300px] flex-1 space-y-3">
              <div className="flex flex-wrap items-center gap-3">
                <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} className="rounded-2xl border border-[#f5b342]/30 bg-black/40 px-4 py-2.5 text-[11px] font-black text-[#f5b342]">
                  {TIMEFRAMES.map((tf) => (<option key={tf}>{tf}</option>))}
                </select>
                <button
                  onClick={onRunPipeline}
                  disabled={Boolean(busyLabel)}
                  className="rounded-2xl px-5 py-2.5 text-sm font-black text-black shadow-[0_0_36px_rgba(45,212,191,.35)] transition hover:scale-[1.02] disabled:opacity-50"
                  style={{ background: isGenerating ? "linear-gradient(135deg,#34d399,#22d3ee)" : "linear-gradient(135deg,#f5b342,#f59e0b)" }}
                >
                  {isGenerating ? "Generating Strategy..." : "Generate Strategy"}
                </button>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <button onClick={onRunBatch} disabled={Boolean(busyLabel)} className="rounded-2xl border border-[#f5b342]/20 bg-white/[.05] px-4 py-2.5 text-xs font-black text-[#fff7e6]/80 hover:bg-[#f5b342]/10 disabled:opacity-50">Run 100 Batch Test</button>
                <button onClick={onOptimize} disabled={Boolean(busyLabel)} className="rounded-2xl border border-[#f5b342]/20 bg-white/[.05] px-4 py-2.5 text-xs font-black text-[#fff7e6]/80 hover:bg-[#f5b342]/10 disabled:opacity-50">Optimize Win Rate</button>
              </div>
            </div>

            <div className="flex shrink-0 flex-wrap items-center gap-2">
              {[["profit", "Profit"], ["idle", "Idle"], ["loss", "Risk"]].map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setSystemState(key)}
                  className="rounded-2xl border px-4 py-2.5 text-xs font-black transition"
                  style={{
                    borderColor: systemState === key ? theme.accent : "rgba(245,179,66,.18)",
                    background: systemState === key ? theme.soft : "rgba(255,255,255,.04)",
                    color: systemState === key ? theme.accent : "rgba(255,247,230,.65)",
                  }}
                >
                  {label}
                </button>
              ))}
              <div className="rounded-2xl border px-4 py-2.5 text-xs font-black" style={{ borderColor: theme.border, background: theme.soft, color: theme.accent }}>{theme.status}</div>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-3">
            <div className="rounded-2xl border border-cyan-300/12 bg-black/28 px-4 py-2.5 backdrop-blur">
              <div className="text-[10px] font-semibold uppercase tracking-[.2em] text-cyan-200">Live Agent Orbit</div>
            </div>
            <div className="rounded-2xl border border-[#f5b342]/12 bg-black/28 px-4 py-2.5 backdrop-blur">
              <div className="text-[10px] font-semibold uppercase tracking-[.2em]" style={{ color: isGenerating ? "#6ee7b7" : theme.accent }}>{isGenerating ? "Generation Motion Active" : pipelineConnected ? "Reactive System Active" : "Socket Offline"}</div>
            </div>
            <div className="rounded-2xl border border-[#f5b342]/12 bg-black/28 px-4 py-2.5 backdrop-blur">
              <div className="text-[10px] font-semibold uppercase tracking-[.2em]">{mockMode ? "Mock Mode" : "Real MT5 Mode"}</div>
            </div>
            <div className="rounded-2xl border border-[#f5b342]/12 bg-black/28 px-4 py-2.5 backdrop-blur">
              <div className="text-[10px] font-semibold uppercase tracking-[.2em] text-[#fff7e6]/70">{isGenerating ? "Agents moving and evaluating" : "One click starts the pipeline"}</div>
            </div>
          </div>
        </ShellCard>

        <div className="mt-4 flex min-h-0 flex-1 flex-col justify-end gap-4">
          <div className="grid shrink-0 gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-7">
            {metrics.map(([label, value, sub]) => (
              <div key={label} className="rounded-2xl border border-[#f5b342]/15 bg-[#090806]/48 px-4 py-3 shadow-xl backdrop-blur transition hover:border-[#f5b342]/30">
                <div className="text-[9px] font-semibold uppercase tracking-wider text-[#fff7e6]/38">{label}</div>
                <div className="mt-1.5 text-lg font-black text-emerald-400">{value}</div>
                <div className="text-[10px] text-[#f5b342]/58">{sub}</div>
              </div>
            ))}
          </div>
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

function StrategyDetailsModal({ strategy, loading, onClose, onBacktest, onEvolve, mockMode }) {
  if (!strategy && !loading) return null;

  return (
    <div className="fixed inset-0 z-[90] bg-black/75 p-5 backdrop-blur-md">
      <div className="mx-auto h-full max-w-[1500px] overflow-y-auto rounded-[30px] border border-[#f5b342]/25 bg-[#080501] p-6 text-[#fff7e6] shadow-[0_30px_100px_rgba(0,0,0,.55)]">
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <button onClick={onClose} className="mb-4 text-xs font-black uppercase tracking-[.2em] text-[#f5b342]">
              {"<- Back to Strategy Lab"}
            </button>
            <h2 className="text-3xl font-black">{strategy?.name || "Loading..."}</h2>
            <p className="mt-1 text-sm text-[#fff7e6]/45">
              {strategy?.symbol || "EURUSD"} · {strategy?.timeframe || "M15"} · {strategy?.type || "strategy"}
            </p>
          </div>
          {strategy && (
            <div className="flex gap-2">
              <button onClick={() => onBacktest(strategy.name)} className="rounded-xl border border-[#f5b342]/20 bg-[#f5b342]/10 px-4 py-2 text-xs font-black text-[#f5b342]">{mockMode ? "Mock Backtest" : "Real Backtest"}</button>
              <button onClick={() => onEvolve(strategy.name)} className="rounded-xl border border-[#f5b342]/20 bg-[#f5b342]/10 px-4 py-2 text-xs font-black text-[#f5b342]">Evolve</button>
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
              <StatCard label="Monthly Profit" value={strategy.monthlyProfit} sub="average" state="profit" />
              <StatCard label="Yearly Profit" value={strategy.yearlyProfit} sub="current year" state="profit" />
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
                    </div>
                  ))}
                  {!strategy.backtests?.length && <div className="text-sm text-[#fff7e6]/45">No backtest records yet.</div>}
                </div>
              </ShellCard>
            </div>

            <ShellCard className="mt-5 p-5">
              <h3 className="mb-4 text-lg font-black">Synthetic P&L Calendar View</h3>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {strategy.monthlySeries.map((value, index) => (
                  <div key={index} className="rounded-2xl border border-[#f5b342]/12 bg-[#f5b342]/8 p-4">
                    <div className="flex items-center justify-between">
                      <b>{["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][index]}</b>
                      <span className={value >= 0 ? "text-emerald-400" : "text-red-400"}>{formatCurrency(value)}</span>
                    </div>
                    <div className="mt-3 h-2 rounded-full bg-black/35">
                      <div className={cn("h-2 rounded-full", value >= 0 ? "bg-emerald-400" : "bg-red-400")} style={{ width: `${Math.min(100, Math.max(14, Math.abs(value) / 85))}%` }} />
                    </div>
                  </div>
                ))}
              </div>
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

function StrategyLab({ strategies, selectedStrategy, detailLoading, onOpenStrategy, onCloseStrategy, onRunPipeline, onBacktest, onEvolve, mockMode }) {
  const topStrategies = strategies.slice(0, 12);
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
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-black">Top Strategies</h2>
            <p className="mt-1 text-xs text-[#fff7e6]/45">Click any row for the full strategy profile.</p>
          </div>
          <div className="rounded-xl border border-[#f5b342]/20 bg-[#f5b342]/10 px-4 py-2 text-xs font-black text-[#f5b342]">{topStrategies.length} shown</div>
        </div>
        <div className="overflow-x-auto">
        <table className="min-w-[760px] w-full text-left text-sm">
          <thead className="bg-[#f5b342]/10 text-xs uppercase text-[#fff7e6]/50">
            <tr>
              {["#", "Strategy", "Net Profit", "Win", "DD", "PF", "Status"].map((header) => (
                <th key={header} className="px-4 py-4">{header}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {topStrategies.map((row, index) => (
              <tr key={row.id} onClick={() => onOpenStrategy(row.id)} className="cursor-pointer border-b border-[#f5b342]/10 transition hover:bg-[#f5b342]/10">
                <td className="px-4 py-4 font-black text-[#f5b342]">#{index + 1}</td>
                <td className="px-4 py-4 font-black">
                  {row.name}
                  <div className="text-xs font-normal text-[#fff7e6]/35">{row.symbol} · {row.timeframe} · {row.type}</div>
                </td>
                <td className="px-4 py-4 font-black text-emerald-400">{row.profit}</td>
                <td className="px-4 py-4">{row.win}</td>
                <td className="px-4 py-4 text-red-400">{row.dd}</td>
                <td className="px-4 py-4">{row.pf}</td>
                <td className="px-4 py-4"><span className="rounded-full bg-[#f5b342]/10 px-3 py-1 text-xs font-black text-[#f5b342]">{row.status}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </ShellCard>

      {(selectedStrategy || detailLoading) && (
        <StrategyDetailsModal
          strategy={selectedStrategy}
          loading={detailLoading}
          onClose={onCloseStrategy}
          onBacktest={onBacktest}
          onEvolve={onEvolve}
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
  const roles = ["All", ...Array.from(new Set(agents.map((agent) => agent.role)))];
  const filtered = agents.filter((agent) => {
    const roleMatch = role === "All" || agent.role === role;
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
            <div className="mt-4 rounded-2xl bg-[#f5b342]/8 p-3 text-sm text-[#fff7e6]/70">{agent.status}</div>
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

function EvolutionLab({ champion, onEvolve, optimizeResult }) {
  const lineage = useMemo(() => {
    if (!champion) return [];
    const seed = hashNumber(champion.name);
    return Array.from({ length: 3 }, (_, index) => ({
      parent: index === 0 ? champion.name : `${champion.name.slice(0, -4)}${String((seed + index) % 9999).padStart(4, "0")}`,
      child: `${champion.name.slice(0, -4)}${String((seed + index + 11) % 9999).padStart(4, "0")}`,
    }));
  }, [champion]);

  return (
    <PageShell title="Evolution Lab" subtitle="Drive the genetic engine from the same visual shell, with real backend mutation runs.">
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
        <ShellCard className="p-6">
          <h2 className="text-xl font-black">Champion and Lineage</h2>
          <div className="mt-5 rounded-3xl border border-[#f5b342]/25 bg-[#f5b342]/10 p-6">
            <div className="text-xs text-[#fff7e6]/50">Current Champion</div>
            <div className="text-2xl font-black">{champion?.name || "No champion yet"}</div>
            <div className="font-black text-emerald-400">{champion ? `${champion.profit} · PF ${champion.pf}` : "Run pipeline to create one."}</div>
          </div>
          <div className="mt-6">
            <div className="mb-2 text-sm font-black">Lineage Preview</div>
            {lineage.map((item) => (
              <div key={item.child} className="flex items-center gap-3 py-1 text-sm text-[#fff7e6]/70">
                <span className="rounded bg-[#f5b342]/10 px-2 py-1">{item.parent}</span>
                <span>{"->"}</span>
                <span className="rounded bg-[#f5b342]/20 px-2 py-1 text-[#f5b342]">{item.child}</span>
              </div>
            ))}
          </div>
        </ShellCard>

        <ShellCard className="p-6">
          <h2 className="text-xl font-black">Evolution Controls</h2>
          <div className="mt-4 space-y-4 text-sm">
            <div className="rounded-2xl border border-[#f5b342]/10 bg-[#f5b342]/8 p-4">
              <div className="text-xs uppercase tracking-[.18em] text-[#fff7e6]/40">Target</div>
              <div className="mt-2 text-lg font-black">{champion?.name || "No active strategy"}</div>
            </div>
            <div className="rounded-2xl border border-[#f5b342]/10 bg-[#f5b342]/8 p-4">
              <div className="text-xs uppercase tracking-[.18em] text-[#fff7e6]/40">Latest optimizer result</div>
              <div className="mt-2 text-lg font-black text-emerald-400">
                {optimizeResult?.final_win_rate ? `${optimizeResult.final_win_rate.toFixed(1)}% win rate` : "No optimization run yet"}
              </div>
            </div>
          </div>
          <button onClick={() => champion && onEvolve(champion.name)} disabled={!champion} className="mt-5 w-full rounded-xl bg-[#f5b342] py-4 font-black text-black disabled:opacity-50">Run Evolution</button>
        </ShellCard>
      </div>

      <ShellCard className="mt-6 p-6">
        <h3 className="mb-3 font-black">Synthetic Monte Carlo Surface</h3>
        <div className="flex h-24 items-end gap-2">
          {buildSyntheticSeries(champion || { name: "seed", net_profit: 4000 }).yearly.map((value, index) => (
            <div key={index} className="flex-1 rounded bg-[#f5b342]/20" style={{ height: `${Math.max(18, Math.abs(value) / 180)}px` }} />
          ))}
        </div>
      </ShellCard>
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

function LogsPage({ logs }) {
  const [apiName, setApiName] = useState("");
  const [apiValue, setApiValue] = useState("");
  const [keys, setKeys] = useState([]);
  const [newModel, setNewModel] = useState("");
  const [localModels, setLocalModels] = useState(LOCAL_MODEL_DEFAULTS);

  const addKey = () => {
    if (!apiName.trim() || !apiValue.trim()) return;
    setKeys((current) => [...current, { id: Date.now(), name: apiName.trim(), value: apiValue.trim() }]);
    setApiName("");
    setApiValue("");
  };

  const addModel = () => {
    if (!newModel.trim()) return;
    setLocalModels((current) => [...current, newModel.trim()]);
    setNewModel("");
  };

  return (
    <PageShell title="Logs and Integrations" subtitle="Real backend logs, plus your local integration panels.">
      <div className="grid gap-6 xl:grid-cols-2">
        <ShellCard className="p-6">
          <h2 className="text-lg font-black mb-3">API Keys</h2>
          <div className="grid grid-cols-2 gap-3">
            <input value={apiName} onChange={(event) => setApiName(event.target.value)} placeholder="Key Name" className="rounded border border-[#f5b342]/20 bg-black/40 p-2 text-[#fff7e6]" />
            <input value={apiValue} onChange={(event) => setApiValue(event.target.value)} placeholder="API Key" className="rounded border border-[#f5b342]/20 bg-black/40 p-2 text-[#fff7e6]" />
          </div>
          <button onClick={addKey} className="mt-3 rounded bg-[#f5b342] px-4 py-2 font-black text-black">+ Add Key</button>
          <div className="mt-4 space-y-2">
            {keys.map((key) => (
              <div key={key.id} className="rounded-2xl border border-[#f5b342]/10 bg-[#f5b342]/8 px-4 py-3 text-sm">
                <b>{key.name}</b>
                <div className="text-xs text-[#fff7e6]/45">{key.value.slice(0, 6)}****</div>
              </div>
            ))}
          </div>
        </ShellCard>

        <ShellCard className="p-6">
          <h2 className="text-lg font-black mb-3">Local Models</h2>
          <div className="flex gap-3">
            <input value={newModel} onChange={(event) => setNewModel(event.target.value)} placeholder="e.g. llama3" className="flex-1 rounded border border-[#f5b342]/20 bg-black/40 p-2 text-[#fff7e6]" />
            <button onClick={addModel} className="rounded bg-[#f5b342] px-4 font-black text-black">+ Add</button>
          </div>
          <div className="mt-3 space-y-2">
            {localModels.map((model) => (
              <div key={model} className="rounded-2xl border border-[#f5b342]/10 bg-[#f5b342]/8 px-4 py-3 text-sm">✓ {model}</div>
            ))}
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

function MissionControlPage({ theme, GOLD, TEXT, SURFACE }) {
  const [goal, setGoal] = useState("Create a low-risk EURUSD strategy on M15, backtest it, evolve for 3 generations, and export the champion MQL5 EA.");
  const [pair, setPair] = useState("EURUSD");
  const [timeframe, setTimeframe] = useState("M15");
  const [activeMission, setActiveMission] = useState(null);
  const [missions, setMissions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);
  const [mcpStatus, setMcpStatus] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchMissions();
    fetchMcpStatus();
  }, []);

  async function fetchMissions() {
    try {
      const res = await listMissions(10);
      setMissions(res.data?.missions || []);
    } catch {}
  }

  async function fetchMcpStatus() {
    try {
      const res = await getMcpStatus();
      setMcpStatus(res.data);
    } catch {}
  }

  async function fetchMission(id) {
    try {
      const res = await getMission(id);
      setActiveMission(res.data);
    } catch {}
  }

  async function handleStartMission() {
    if (!goal.trim()) return;
    setLoading(true); setError(null);
    try {
      const res = await startMission(goal, pair, timeframe);
      const mission = res.data.mission;
      setActiveMission({ mission, steps: [], reasoning_trace: [] });
      await fetchMissions();
      // Auto-advance non-approval steps
      let missionId = mission.id;
      for (let i = 0; i < 20; i++) {
        const adv = await advanceMission(missionId);
        await fetchMission(missionId);
        if (adv.data?.status === "completed" || adv.data?.status === "waiting_approval" || adv.data?.status === "failed") break;
        await new Promise(r => setTimeout(r, 400));
      }
    } catch (e) {
      setError(e?.response?.data?.detail || "Failed to start mission");
    }
    setLoading(false);
  }

  async function handleJudgeDemo() {
    setDemoLoading(true); setError(null);
    try {
      const res = await runJudgeDemo();
      setActiveMission(res.data);
      await fetchMissions();
    } catch (e) {
      setError(e?.response?.data?.detail || "Demo failed");
    }
    setDemoLoading(false);
  }

  async function handleApprove(stepId, approved) {
    if (!activeMission?.mission?.id) return;
    try {
      await approveStep(activeMission.mission.id, stepId, approved);
      await fetchMission(activeMission.mission.id);
      // Continue advancing after approval
      for (let i = 0; i < 10; i++) {
        const adv = await advanceMission(activeMission.mission.id);
        await fetchMission(activeMission.mission.id);
        if (adv.data?.status === "completed" || adv.data?.status === "waiting_approval" || adv.data?.status === "failed") break;
        await new Promise(r => setTimeout(r, 300));
      }
    } catch {}
  }

  async function handlePause() {
    if (!activeMission?.mission?.id) return;
    await pauseMission(activeMission.mission.id);
    await fetchMission(activeMission.mission.id);
  }

  async function handleStop() {
    if (!activeMission?.mission?.id) return;
    await stopMission(activeMission.mission.id);
    await fetchMission(activeMission.mission.id);
  }

  const statusColor = (s) => {
    if (!s) return "#8b949e";
    if (["completed", "approved", "active"].includes(s)) return "#3fb950";
    if (["failed", "stopped", "rejected"].includes(s)) return "#f85149";
    if (["waiting_approval"].includes(s)) return "#d29922";
    if (["running"].includes(s)) return "#58a6ff";
    return "#8b949e";
  };

  const missionData = activeMission?.mission || null;
  const steps = activeMission?.steps || [];
  const trace = activeMission?.reasoning_trace || [];
  const waitingStep = steps.find(s => s.status === "waiting_approval");

  const containerStyle = {
    background: SURFACE,
    minHeight: "100%",
    color: TEXT,
    fontFamily: "'JetBrains Mono', 'Fira Mono', monospace",
    padding: "24px",
    overflowY: "auto",
  };

  const cardStyle = {
    background: "rgba(255,255,255,0.04)",
    border: `1px solid rgba(255,255,255,0.08)`,
    borderRadius: 12,
    padding: 20,
    marginBottom: 20,
  };

  const btnStyle = (color) => ({
    background: color,
    color: "#000",
    border: "none",
    borderRadius: 8,
    padding: "8px 18px",
    fontSize: 13,
    fontWeight: 700,
    cursor: "pointer",
    marginRight: 8,
    marginTop: 8,
  });

  return (
    <div style={containerStyle}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 26, fontWeight: 800, color: GOLD, margin: 0 }}>
          Mission Control
        </h1>
        <p style={{ color: "#8b949e", fontSize: 13, margin: "6px 0 0" }}>
          Gemini-powered multi-step trading strategy research agent. Plan → Execute → Validate → Export.
        </p>
      </div>

      {error && (
        <div style={{ background: "rgba(248,81,73,0.1)", border: "1px solid #f85149", borderRadius: 8, padding: 12, marginBottom: 16, color: "#f85149", fontSize: 13 }}>
          {error}
        </div>
      )}

      {/* Mission Input */}
      <div style={cardStyle}>
        <h3 style={{ color: GOLD, fontSize: 14, fontWeight: 700, marginTop: 0, marginBottom: 14 }}>
          NEW MISSION — Enter your research goal
        </h3>
        <textarea
          value={goal}
          onChange={e => setGoal(e.target.value)}
          rows={3}
          style={{ width: "100%", background: "rgba(0,0,0,0.3)", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 8, padding: 12, color: TEXT, fontSize: 13, fontFamily: "inherit", resize: "vertical", boxSizing: "border-box" }}
        />
        <div style={{ display: "flex", gap: 12, marginTop: 10, flexWrap: "wrap", alignItems: "center" }}>
          <select value={pair} onChange={e => setPair(e.target.value)} style={{ background: "#0d1117", border: "1px solid rgba(255,255,255,0.12)", color: TEXT, padding: "6px 12px", borderRadius: 6, fontSize: 13 }}>
            {["EURUSD","GBPUSD","USDJPY","XAUUSD","BTCUSD"].map(p => <option key={p}>{p}</option>)}
          </select>
          <select value={timeframe} onChange={e => setTimeframe(e.target.value)} style={{ background: "#0d1117", border: "1px solid rgba(255,255,255,0.12)", color: TEXT, padding: "6px 12px", borderRadius: 6, fontSize: 13 }}>
            {["M1","M5","M15","M30","H1","H4","D1"].map(t => <option key={t}>{t}</option>)}
          </select>
          <button onClick={handleStartMission} disabled={loading} style={btnStyle("#58a6ff")}>
            {loading ? "Starting…" : "▶ Start Mission"}
          </button>
          <button onClick={handleJudgeDemo} disabled={demoLoading} style={btnStyle("#3fb950")}>
            {demoLoading ? "Running…" : "⚡ Run Judge Demo"}
          </button>
        </div>
        <p style={{ fontSize: 11, color: "#8b949e", marginTop: 8, marginBottom: 0 }}>
          Demo mode: no live trading. All backtests are mock/simulated under human oversight.
        </p>
      </div>

      {/* Active Mission */}
      {missionData && (
        <div style={cardStyle}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 10, marginBottom: 16 }}>
            <div>
              <h3 style={{ color: GOLD, fontSize: 14, fontWeight: 700, margin: "0 0 4px" }}>
                ACTIVE MISSION #{missionData.id}
              </h3>
              <p style={{ color: TEXT, fontSize: 13, margin: 0 }}>{missionData.user_goal}</p>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <span style={{ background: statusColor(missionData.status), color: "#000", borderRadius: 6, padding: "3px 10px", fontSize: 12, fontWeight: 700 }}>
                {(missionData.status || "unknown").toUpperCase()}
              </span>
              <button onClick={handlePause} style={{ ...btnStyle("#d29922"), padding: "4px 12px", fontSize: 11 }}>⏸ Pause</button>
              <button onClick={handleStop} style={{ ...btnStyle("#f85149"), padding: "4px 12px", fontSize: 11 }}>⏹ Stop</button>
            </div>
          </div>

          {/* Gemini Reasoning */}
          {missionData.gemini_reasoning && (
            <div style={{ background: "rgba(88,166,255,0.08)", border: "1px solid rgba(88,166,255,0.2)", borderRadius: 8, padding: 12, marginBottom: 16 }}>
              <div style={{ fontSize: 11, color: "#58a6ff", fontWeight: 700, marginBottom: 4 }}>GEMINI REASONING</div>
              <p style={{ color: "#cdd9e5", fontSize: 13, margin: 0 }}>{missionData.gemini_reasoning}</p>
            </div>
          )}

          {/* Human Approval Gate */}
          {waitingStep && (
            <div style={{ background: "rgba(210,153,34,0.1)", border: "1px solid #d29922", borderRadius: 8, padding: 14, marginBottom: 16 }}>
              <div style={{ fontSize: 12, color: "#d29922", fontWeight: 700, marginBottom: 6 }}>
                ⚠ HUMAN APPROVAL REQUIRED — Step {waitingStep.step_number}: {waitingStep.step_name}
              </div>
              <p style={{ color: TEXT, fontSize: 13, margin: "0 0 10px" }}>
                {waitingStep.input?.description || "This step requires your explicit approval before proceeding."}
              </p>
              <button onClick={() => handleApprove(waitingStep.id, true)} style={btnStyle("#3fb950")}>✓ Approve</button>
              <button onClick={() => handleApprove(waitingStep.id, false)} style={btnStyle("#f85149")}>✗ Reject</button>
            </div>
          )}

          {/* Steps Timeline */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 12, color: "#8b949e", fontWeight: 700, marginBottom: 10 }}>MISSION STEPS</div>
            <div style={{ display: "grid", gap: 6 }}>
              {steps.map(step => (
                <div key={step.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 12px", background: "rgba(0,0,0,0.2)", borderRadius: 6, borderLeft: `3px solid ${statusColor(step.status)}` }}>
                  <span style={{ color: "#8b949e", fontSize: 11, minWidth: 20 }}>{step.step_number}.</span>
                  <span style={{ flex: 1, fontSize: 13, color: TEXT }}>{step.step_name}</span>
                  <span style={{ fontSize: 11, color: "#8b949e" }}>{step.tool_name}</span>
                  <span style={{ fontSize: 11, color: statusColor(step.status), fontWeight: 700 }}>
                    {step.requires_approval && step.status === "pending" ? "🔒 " : ""}{(step.status || "").toUpperCase()}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Gemini Reasoning Trace */}
      {trace.length > 0 && (
        <div style={cardStyle}>
          <h3 style={{ color: GOLD, fontSize: 14, fontWeight: 700, marginTop: 0, marginBottom: 14 }}>
            GEMINI REASONING TRACE
          </h3>
          <div style={{ display: "grid", gap: 8 }}>
            {trace.map((entry, i) => (
              <div key={i} style={{ padding: "10px 14px", background: "rgba(167,139,250,0.06)", border: "1px solid rgba(167,139,250,0.15)", borderRadius: 8 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                  <span style={{ color: "#bc8cff", fontSize: 12, fontWeight: 700 }}>{entry.agent_name}</span>
                  <span style={{ color: "#8b949e", fontSize: 11 }}>{entry.created_at ? new Date(entry.created_at).toLocaleTimeString() : ""}</span>
                </div>
                <p style={{ color: TEXT, fontSize: 13, margin: "0 0 4px" }}>{entry.reasoning_summary}</p>
                <div style={{ display: "flex", gap: 12, fontSize: 11, color: "#8b949e" }}>
                  {entry.decision && <span>Decision: <span style={{ color: "#3fb950" }}>{entry.decision}</span></span>}
                  {entry.next_action && <span>→ {entry.next_action}</span>}
                  {entry.confidence && <span>Confidence: {Math.round(entry.confidence * 100)}%</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* MCP Status */}
      {mcpStatus && (
        <div style={cardStyle}>
          <h3 style={{ color: GOLD, fontSize: 14, fontWeight: 700, marginTop: 0, marginBottom: 12 }}>
            MCP PARTNER STATUS (MongoDB Memory)
          </h3>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
            {Object.entries(mcpStatus).filter(([k]) => k !== "active_source").map(([key, val]) => (
              <div key={key} style={{ padding: "8px 14px", background: "rgba(0,0,0,0.2)", borderRadius: 8, border: `1px solid ${val?.status === "connected" || val?.status === "active" ? "rgba(63,185,80,0.3)" : "rgba(255,255,255,0.08)"}` }}>
                <div style={{ fontSize: 11, color: "#8b949e", marginBottom: 2 }}>{key.replace(/_/g," ").toUpperCase()}</div>
                <div style={{ fontSize: 13, color: val?.status === "connected" || val?.status === "active" ? "#3fb950" : "#d29922", fontWeight: 700 }}>{val?.status}</div>
                <div style={{ fontSize: 11, color: "#8b949e", marginTop: 2 }}>{val?.detail}</div>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 10, fontSize: 12, color: "#58a6ff" }}>
            Active source: <strong>{mcpStatus.active_source}</strong>
          </div>
        </div>
      )}

      {/* Mission History */}
      {missions.length > 0 && (
        <div style={cardStyle}>
          <h3 style={{ color: GOLD, fontSize: 14, fontWeight: 700, marginTop: 0, marginBottom: 12 }}>
            MISSION HISTORY
          </h3>
          <div style={{ display: "grid", gap: 6 }}>
            {missions.map(m => (
              <div key={m.id}
                onClick={() => fetchMission(m.id)}
                style={{ padding: "10px 14px", background: "rgba(0,0,0,0.2)", borderRadius: 8, cursor: "pointer", border: `1px solid ${activeMission?.mission?.id === m.id ? "rgba(201,154,69,0.4)" : "transparent"}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <span style={{ color: "#8b949e", fontSize: 11 }}>#{m.id} </span>
                  <span style={{ color: TEXT, fontSize: 13 }}>{m.user_goal?.slice(0,60)}…</span>
                </div>
                <span style={{ fontSize: 11, color: statusColor(m.status), fontWeight: 700 }}>{(m.status||"").toUpperCase()}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function GenericPage(props) {
  switch (props.page) {
    case "Mission Control":
      return <MissionControlPage theme={null} GOLD={GOLD} TEXT={TEXT} SURFACE={SURFACE} />;
    case "Strategy Lab":
      return <StrategyLab {...props} />;
    case "Agent Control Room":
      return <AgentRoom agents={props.agents} />;
    case "Evolution Lab":
      return <EvolutionLab champion={props.champion} onEvolve={props.onEvolve} optimizeResult={props.optimizeResult} />;
    case "Portfolio Optimizer":
      return <PortfolioOptimizer portfolio={props.portfolio} />;
    case "Risk Center":
      return <RiskCenter risk={props.risk} backtests={props.backtests} />;
    case "Logs":
      return <LogsPage logs={props.logs} />;
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
  const [systemOverride, setSystemOverride] = useState("");
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
    ] = await Promise.all([
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

    setStats(statsRes.data);
    setHealth(healthRes.data);
    setStrategies(
      [...strategiesRes.data]
        .map((item) => normalizeStrategySummary(item))
        .sort((left, right) => (right.netProfit ?? Number.NEGATIVE_INFINITY) - (left.netProfit ?? Number.NEGATIVE_INFINITY)),
    );
    setAgents((agentsRes.data.all_agents || agentsRes.data.agents || []).map(normalizeAgent));
    setLogs(logsRes.data.logs || []);
    setBacktests(backtestsRes.data || []);
    setRisk(riskRes.data);
    setPortfolio(portfolioRes.data);
    setWinRateStats(winRateRes.data);
    setLatestBatch(batchRes.data);
  }, []);

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

  const systemState = systemOverride || autoSystemState;
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

  const handleEvolve = useCallback((strategyName) => runWithBusy(
    "Running evolution...",
    () => evolveStrategy(strategyName, 3).then((response) => response.data),
    (data) => data.improved ? `Evolved ${data.evolved?.name || strategyName}` : `No improvement for ${strategyName}`,
  ), [runWithBusy]);

  return (
    <div className="min-h-screen bg-[#050403] text-[#fff7e6]">
      <HoverSidebar page={page} setPage={(nextPage) => { setPage(nextPage); setSelectedStrategy(null); }} health={health} />
      {page === "Command Center" ? (
        <CommandCenter
          timeframe={timeframe}
          setTimeframe={setTimeframe}
          systemState={systemState}
          setSystemState={setSystemOverride}
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
        <div className="xl:pl-12">
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
              detailLoading={detailLoading}
              onOpenStrategy={openStrategy}
              onCloseStrategy={() => setSelectedStrategy(null)}
              onRunPipeline={handleRunPipeline}
              onBacktest={handleBacktest}
              onEvolve={handleEvolve}
              optimizeResult={optimizeResult}
            />
          </main>
        </div>
      )}
      <Toast message={toast} />
    </div>
  );
}
