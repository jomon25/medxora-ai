# MedXora AI
### Gemini-Powered Multi-Agent Trading Strategy Research Engine

> A supervised AI agent that plans, generates, validates, evolves, stores, searches, and exports MetaTrader 5 trading strategies under human control.

**MedXora AI uses Gemini as the reasoning brain, FastAPI tools for execution, MCP for memory/search/observability, and a React dashboard for human oversight.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61dafb.svg)](https://react.dev)
[![Gemini](https://img.shields.io/badge/Gemini-1.5--flash-4285F4.svg)](https://ai.google.dev)

---

## One-Line Pitch

MedXora AI is a Gemini-powered multi-agent research engine that autonomously plans, generates, backtests, evolves, and exports MetaTrader 5 trading strategies — with full human oversight, MCP memory integration, and an explainable AI reasoning trace at every step.

---

## The Problem

Building a profitable algorithmic trading strategy requires:
- Generating hundreds of parameter combinations
- Validating risk on every candidate
- Backtesting across multiple timeframes
- Evolving survivors with genetic algorithms
- Comparing against historical memory
- Exporting only human-approved strategies

This multi-step research process normally takes days of manual work — and has no explainability or audit trail.

---

## The Solution: MedXora AI Mission Control

MedXora AI replaces that manual workflow with a **supervised AI agent**.

You describe a goal in plain English:

> "Create a low-risk EURUSD strategy on M15, backtest it, evolve for 3 generations, validate with Monte Carlo, and export the champion MQL5 EA."

Gemini converts it into a structured 14-step mission plan. The agent executes each step, pauses for human approval at critical gates, shows its reasoning trace in real-time, and exports only approved strategies.

**This is not a chatbot. It is an agent that plans, executes, observes, and decides.**

---

## Why This Is an Agent, Not a Chatbot

| Chatbot | MedXora AI Agent |
|---------|-----------------|
| Answers questions | Takes multi-step actions |
| Single-turn | Multi-turn mission with state |
| No tool calls | Calls 14+ specialised tools |
| No memory | MCP MongoDB/SQLite memory |
| No oversight | Human approval gates |
| No observability | Full Gemini reasoning trace |
| No external integrations | MongoDB MCP partner integration |

---

## Architecture

```
User (Browser)
     │
     ▼
React Dashboard (Vite + Tailwind)
     │  Mission Control / Agent Control Room / Evolution Lab
     │
     ▼
FastAPI Backend (Python)
     │
     ├─ Gemini Planner ──────── plan_mission()
     │                          critique_strategy()
     │                          explain_risk()
     │                          advise_evolution()
     │                          write_final_report()
     │                          route_tool()
     │
     ├─ MedXora Tools ──────── generate_strategy
     │                          risk_manager
     │                          mql5_generator
     │                          backtest_mock / MT5
     │                          evolution_agent (genetic)
     │                          monte_carlo_agent
     │                          ensemble_voting (16 agents)
     │                          mql5_export
     │
     ├─ MCP Partner ─────────── MongoDB (strategy memory)
     │                          Local SQLite (fallback)
     │
     └─ Database ────────────── SQLite via SQLAlchemy ORM
                                missions, steps, reasoning logs,
                                human approvals, MCP events,
                                strategy memory, validation reports
```

---

## Gemini Integration

Gemini (`gemini-1.5-flash`) is the **central reasoning brain**, not an optional add-on.

| Gemini Role | Function | When Used |
|-------------|----------|-----------|
| **Mission Planner** | Converts user goal → structured 14-step plan | Mission start |
| **Strategy Critic** | Quality score 0-100, verdict: approve/reject | After generation |
| **Risk Explainer** | Plain-English explanation of risk decisions | After risk validation |
| **Evolution Advisor** | Suggests mutation direction for next generation | Between generations |
| **Report Writer** | Generates final judge-friendly research report | On export |
| **Tool Router** | Decides which backend tool to call next | Between steps |

### Example Gemini Reasoning Trace

```
Goal: Create a low-risk EURUSD strategy.

Gemini Plan:
  1. Generate EMA+RSI strategy
  2. Validate risk parameters
  3. Run mock backtest
  4. Calculate fitness score
  5. Monte Carlo validation
  6. Evolve for 3 generations [APPROVAL REQUIRED]
  7. Search strategy memory (MCP)
  8. Select champion via ensemble voting [APPROVAL REQUIRED]
  9. Human approval gate [APPROVAL REQUIRED]
  10. Export MQL5 [APPROVAL REQUIRED]
  11. Generate Gemini report

Current Decision:
  Step 3 completed — Win rate 61.5%, Sharpe 1.64, Drawdown 8.2%
  Strategy passes risk threshold.

Next Action:
  Proceed to fitness scoring.
  Confidence: 92%
```

---

## Google Cloud Integration

- **Gemini API** — `gemini-1.5-flash` via `google-generativeai` SDK
- **Firebase Hosting** — Frontend deployment target (see Deployment section)
- **Cloud Run** — Backend containerised deployment target
- **Google Cloud Run** deployment guide included below

---

## MCP Partner Integration

MedXora AI integrates **MongoDB** as the partner MCP for strategy memory.

### What is stored in MongoDB:
```json
{
  "strategy_name": "EURUSD_EMA_RSI_Champion_01",
  "pair": "EURUSD",
  "timeframe": "M15",
  "sharpe": 1.64,
  "drawdown": 8.2,
  "win_rate": 61.5,
  "profit_factor": 1.87,
  "risk_status": "approved",
  "mql5_exported": true,
  "created_at": "2026-05-05T10:30:00Z"
}
```

### MCP Capabilities:
| Endpoint | Action |
|----------|--------|
| `POST /api/mcp/save-strategy-memory` | Store strategy in MongoDB |
| `POST /api/mcp/search-strategies` | Semantic search: min Sharpe, max drawdown, risk status |
| `POST /api/mcp/save-agent-log` | Log agent decisions |
| `POST /api/mcp/observe-mission` | Record mission observations |
| `GET /api/mcp/status` | MongoDB + fallback status |

**Fallback:** When `MONGODB_URI` is not set, all MCP operations fall back to local SQLite automatically — the app always works.

---

## Features

### Core Features
- **Gemini Mission Control** — Natural language goal → structured multi-step agent mission
- **16+ AI Agents** — Risk Manager, Monte Carlo, Overfitting Detector, Ensemble Voting, Sentiment, Market Regime, Correlation Guard, and more
- **Strategy Generation** — Randomised EMA+RSI parameter combinations
- **MQL5 Code Generation** — Ready-to-deploy Expert Advisor `.mq5` files
- **Mock Backtesting** — Instant seeded results (no MT5 required)
- **MT5 Backtesting** — Real MetaTrader 5 integration when installed
- **Genetic Evolution** — Multi-generation mutation with fitness scoring
- **Monte Carlo Validation** — 1000-simulation robustness testing
- **Walk-Forward Validation** — 5-window anti-overfitting test
- **Human Approval Gates** — Approve/reject before evolution, export, champion designation
- **MCP Memory** — MongoDB strategy memory with search
- **Strategy Lineage** — Full evolution tree per strategy
- **Gemini Reports** — AI-generated final research reports
- **One-Click Demo** — Judge demo runs a complete 14-step mission instantly

### Dashboard Pages
| Page | Purpose |
|------|---------|
| **Mission Control** | Gemini-planned multi-step missions with approval gates |
| **Command Center** | KPIs, live pipeline, batch analytics |
| **Strategy Lab** | Strategy list, generation, MQL5 download |
| **Evolution Lab** | Genetic evolution controls and lineage |
| **Agent Control Room** | All 16+ agents with animated graph |
| **Portfolio Optimizer** | Best strategy mix |
| **Risk Center** | Risk dashboard |
| **Logs** | System log viewer |
| **Settings** | MT5 config + environment |

---

## Human Safety Controls

MedXora AI operates under **full human oversight**. The agent never acts autonomously on critical steps.

### Approval required before:
| Action | Why |
|--------|-----|
| Start evolution | Genetic mutation changes strategy fundamentals |
| Export MQL5 | Files used in real trading must be human-verified |
| Mark strategy as champion | Formal designation requires human sign-off |
| Override risk veto | Safety-critical; human must consciously override |

### Safety statement:
> MedXora AI does not auto-trade in this demo. It creates and validates strategy **research outputs** under human approval. All backtests in demo mode are mock/simulated.

---

## Demo Mode

Click **"⚡ Run Judge Demo"** on the Mission Control page.

This automatically runs:
1. Start mission
2. Gemini creates 14-step plan
3. Generate EMA+RSI strategy
4. Risk validation
5. MQL5 generation
6. Mock backtest
7. Fitness scoring
8. Monte Carlo (1000 simulations)
9. Genetic evolution (3 generations)
10. MCP memory save + search
11. Ensemble voting (16 agents)
12. Champion selection
13. MQL5 export
14. Gemini final report

All steps use mock data. No MT5 installation required. Total runtime: ~3 seconds.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI Reasoning | Google Gemini 1.5 Flash |
| Backend API | Python 3.10+ · FastAPI · Uvicorn |
| Database | SQLite via SQLAlchemy ORM |
| MCP Memory | MongoDB Atlas (+ SQLite fallback) |
| AI Agents | 16+ custom Python agents |
| Trading Engine | MetaTrader 5 (optional, mock mode available) |
| Frontend | React 18 · Vite · Recharts · Tailwind CSS |
| Deployment | Google Cloud Run · Firebase Hosting |

---

## API Endpoints

### Mission Control
```
POST /api/mission/start                      Start a new Gemini-planned mission
GET  /api/mission/list                       List all missions
GET  /api/mission/{id}                       Mission detail + steps + reasoning trace
POST /api/mission/{id}/advance               Execute next pending step
POST /api/mission/{id}/approve-step          Human approve/reject a step
POST /api/mission/{id}/pause                 Pause mission
POST /api/mission/{id}/resume               Resume paused mission
POST /api/mission/{id}/stop                  Stop mission permanently
```

### Agent Reasoning
```
POST /api/agent/plan                         Gemini plan preview (no DB save)
GET  /api/agent/reasoning-trace/{id}         Full Gemini reasoning trace
GET  /api/agent/tool-calls/{id}              All tool calls for a mission
POST /api/agent/critique/{name}              Gemini strategy quality critique
POST /api/agent/route-tool                   Gemini tool routing decision
```

### Strategy (existing + new)
```
GET  /api/strategy/generate                  Generate strategy JSON preview
GET  /api/strategy/generate-mql5             Generate + save + write .mq5
POST /api/strategy/generate-code             Save strategy + write .mq5
POST /api/strategy/{name}/evolve             Run N-generation evolution
POST /api/strategy/{name}/ai-analyze         Gemini analysis
POST /api/strategy/{id}/export-mql5          Export with human approval + Gemini report
GET  /api/strategy/{id}/lineage              Full evolution tree
GET  /api/strategy/download/{name}           Download .mq5 file
```

### Validation
```
POST /api/validation/monte-carlo/{id}        Monte Carlo robustness test
POST /api/validation/walk-forward/{id}       Walk-forward anti-overfitting test
GET  /api/validation/report/{id}             All validation reports for strategy
```

### MCP (MongoDB)
```
POST /api/mcp/save-strategy-memory           Save to MongoDB memory
POST /api/mcp/search-strategies              Search by Sharpe, drawdown, risk status
POST /api/mcp/save-agent-log                 Save agent reasoning log
POST /api/mcp/observe-mission                Record mission observation
GET  /api/mcp/status                         MongoDB + fallback connection status
```

### Demo
```
POST /api/demo/run-judge-demo                One-click complete demo mission
GET  /api/demo/status                        Demo mode safety status
```

### Existing Core
```
GET  /api/dashboard/stats                    KPI statistics
GET  /api/health                             Service health check
GET  /api/agents                             All agents list
GET  /api/strategies                         All strategies
GET  /api/backtest/results                   Recent backtest results
POST /api/pipeline/final                     Full one-shot pipeline
GET  /api/logs                               System logs
```

---

## Database Schema (New Tables)

| Table | Purpose |
|-------|---------|
| `missions` | Mission records with Gemini plan and status |
| `mission_steps` | Individual step execution records |
| `agent_reasoning_logs` | Gemini reasoning at each step |
| `human_approvals` | Human approve/reject audit trail |
| `mcp_events` | All MCP interactions (save/search/log/observe) |
| `strategy_memory` | Strategy metrics stored in local+MongoDB memory |
| `validation_reports` | Monte Carlo + walk-forward validation results |
| `exported_mql5_files` | Export audit with Gemini report attached |

---

## Environment Variables

```bash
# Required for Gemini features
GEMINI_API_KEY=your_gemini_api_key_here

# Optional: MongoDB MCP (falls back to SQLite without this)
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/

# Optional: MT5 integration (mock mode works without MT5)
MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
MT5_DATA_DIR=
MT5_TICK_DATA_PATH=

# Frontend origin (default covers localhost dev)
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

---

## How to Run Locally

### Prerequisites
- Python 3.10+
- Node.js 18+
- Git

### Step 1 — Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/medxora-ai.git
cd medxora-ai
```

### Step 2 — Backend setup

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### Step 3 — Configure environment

```bash
# Copy and edit .env
# Add your GEMINI_API_KEY (required for full AI features)
# MONGODB_URI is optional — SQLite fallback is automatic
```

### Step 4 — Start backend

```bash
uvicorn main:app --reload
# API: http://127.0.0.1:8000
# Docs: http://127.0.0.1:8000/docs
```

### Step 5 — Frontend setup

```bash
cd ../frontend
npm install
npm run dev
# Dashboard: http://localhost:5173
```

### Step 6 — Run demo

Open `http://localhost:5173`, click **Mission Control** in the sidebar, then click **⚡ Run Judge Demo**.

---

## Google Cloud Deployment

### Backend — Cloud Run

```bash
# Build container
cd backend
docker build -t medxora-backend .

# Push to Artifact Registry
docker tag medxora-backend gcr.io/YOUR_PROJECT/medxora-backend
docker push gcr.io/YOUR_PROJECT/medxora-backend

# Deploy
gcloud run deploy medxora-backend \
  --image gcr.io/YOUR_PROJECT/medxora-backend \
  --platform managed \
  --region us-central1 \
  --set-env-vars GEMINI_API_KEY=your_key \
  --allow-unauthenticated
```

### Frontend — Firebase Hosting

```bash
cd frontend
npm run build

npm install -g firebase-tools
firebase login
firebase init hosting
firebase deploy
```

---

## Project Structure

```
medxora-ai/
├── backend/
│   ├── main.py                    # All FastAPI endpoints
│   ├── config.py                  # Environment + paths
│   ├── database/
│   │   ├── db.py                  # SQLAlchemy engine + session
│   │   └── tables.py              # All ORM models
│   ├── agents/                    # 16+ specialised AI agents
│   │   ├── strategy_creator.py
│   │   ├── risk_manager.py
│   │   ├── backtest_analyst.py
│   │   ├── evolution_agent.py
│   │   ├── monte_carlo_agent.py
│   │   ├── ensemble_voting_agent.py
│   │   └── ... (16+ total)
│   └── services/
│       ├── gemini_service.py      # Existing Gemini analysis
│       ├── gemini_planner.py      # NEW: Gemini reasoning brain
│       ├── mission_service.py     # NEW: Mission orchestration
│       ├── mcp_service.py         # NEW: MongoDB MCP integration
│       ├── mql5_generator.py
│       ├── evolution_engine.py
│       └── ... (20+ total)
├── frontend/
│   └── src/
│       ├── AgentGraphUI.jsx       # Main dashboard (all pages)
│       └── api.js                 # Axios API client
├── README.md
├── LICENSE                        # MIT
└── CLAUDE.md                      # AI assistant guide
```

---

## Screenshots

> *(Add screenshots of Mission Control, Gemini Reasoning Trace, Agent Control Room, Evolution Lab)*

---

## Demo Video

> *(Add 3-minute demo video link here)*

---

## Hosted Project

> *(Add hosted URL here — Firebase Hosting or Cloud Run)*

---

## Submission Details

- **Hackathon:** Google Cloud Rapid Agent Hackathon
- **Track:** Gemini + Google Cloud + MCP Partner Integration (MongoDB)
- **Prize Pool:** $60,000
- **Deadline:** June 11, 2026
- **License:** MIT

---

## Safety and Responsible Use

MedXora AI is a **research and validation tool**, not an automated trading bot.

- No positions are opened or closed automatically
- No broker connections are made during demos
- All strategy exports require explicit human approval
- Risk Manager and Monte Carlo agents provide hard-veto capability
- All AI decisions include confidence scores and reasoning traces
- Complete audit trail of every agent decision and human approval

**Use responsibly. Past backtest performance does not guarantee future results.**

---

## Contributing

Contributions are welcome. Please open an issue first to discuss what you'd like to change.

---

## License

[MIT License](LICENSE) — Copyright (c) 2026 MedXora AI
