# MedXora AI

MedXora AI is a research-focused trading strategy workbench for generating, backtesting, evolving, reviewing, and exporting MetaTrader 5 strategies. It combines a FastAPI backend, a React dashboard, local SQLite storage, optional MT5 execution, optional MongoDB-backed memory, and Gemini-assisted mission workflows.

## Current Status

This repository is in active prototype/beta shape, but the core application is running.

Verified on May 7, 2026:

- Frontend lint passes: `npm run lint`
- Frontend production build passes: `npm run build`
- Backend Python modules compile successfully
- Backend app imports successfully
- Evolution/evaluation flow was updated to use long-running requests and retain post-evolution comparison data more reliably

## What The Project Does

MedXora AI currently supports these main workflows:

- Generate and save trading strategies
- Generate MQL5 code for saved strategies
- Run mock backtests and optional MT5-backed backtests
- Inspect strategy performance in the dashboard
- Evolve a strategy across generations
- Compare strategy metrics before and after evolution
- Run mission-style guided workflows from Mission Control
- Save and use AI integration settings for evaluation
- Store strategy history and validation records in SQLite
- Use MongoDB as an optional MCP-style memory layer with SQLite fallback

## Main Product Areas

### Frontend Pages

- `Command Center`: high-level KPIs, pipeline actions, activity views
- `Strategy Lab`: strategy browsing, detail inspection, backtest/evaluation entry points
- `Mission Control`: guided multi-step mission workflow with approvals
- `Dataset Engine`: raw MT5 tick conversion, OHLCV generation, demo dataset backtest
- `Evolution Lab`: strategy search, evolution, before/after evaluation comparison
- `Agent Control Room`: agent overview and graph-style visualization
- `Portfolio Optimizer`: portfolio summary and selected mixes
- `Risk Center`: drawdown and risk visibility
- `Logs`: backend logs plus AI integration settings
- `Settings`: mode, timeframe, service visibility

### Backend Capabilities

- Strategy generation and persistence
- MQL5 file generation
- Mock and MT5-backed backtesting
- Evolution engine with generation history
- Validation endpoints such as Monte Carlo and walk-forward
- Mission orchestration endpoints
- Strategy lineage retrieval
- Log collection
- Integration settings storage
- Dataset preparation utilities

## Architecture Overview

```text
React + Vite frontend
  -> axios API client
  -> FastAPI backend
  -> services + agents layer
  -> SQLite database
  -> optional MongoDB memory
  -> optional MT5 terminal workflow
  -> optional Gemini-assisted planning/evaluation flows
```

## Repository Layout

```text
medxora-ai/
|-- backend/
|   |-- agents/          # Strategy, evolution, risk, validation, intelligence agents
|   |-- services/        # API helpers, orchestration, storage, integrations, MT5 utilities
|   |-- database/        # SQLAlchemy setup and ORM tables
|   |-- main.py          # Main FastAPI application and routes
|   |-- config.py        # Environment/path configuration
|   `-- requirements.txt
|-- frontend/
|   |-- src/
|   |   |-- AgentGraphUI.jsx
|   |   |-- DatasetEnginePage.jsx
|   |   `-- api.js
|   |-- package.json
|   `-- README.md
|-- generated_strategies/
|-- backtest_reports/
|-- mt5_workspace/
|-- research/
`-- medxora.db
```

## Tech Stack

- Frontend: React, Vite, ESLint, Recharts
- Backend: FastAPI, SQLAlchemy, Pydantic, Uvicorn
- Data: SQLite, Pandas, PyArrow, NumPy
- AI integrations: Gemini support plus saved API-key/local-model evaluation flow
- Optional external systems: MetaTrader 5, MongoDB

## Local Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- npm

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --reload
```

Backend URLs:

- API: `http://127.0.0.1:8000`
- Docs: `http://127.0.0.1:8000/docs`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend URL:

- App: `http://localhost:5173`

## Environment Variables

From [backend/.env.example](backend/.env.example):

- `GEMINI_API_KEY`
- `MONGODB_URI`
- `MT5_PATH`
- `MT5_DATA_DIR`
- `MT5_TICK_DATA_PATH`
- `CORS_ALLOWED_ORIGINS`
- optional `DATABASE_URL`

## Useful Validation Commands

### Frontend

```bash
cd frontend
npm run lint
npm run build
```

### Backend

```bash
cd backend
python -m py_compile main.py
```

## Notable Current Improvements

Recent work in the current codebase includes:

- Evolution requests now use a long-running frontend API client
- Evolution results keep before/after comparison data more reliably
- Evolved result metrics are preserved even when the saved child strategy is still sparse
- Improved evaluation/integration logging flow
- Logs page now has a usable save action for integration settings
- Frontend lint issues were cleaned up and the build is passing again

## Known Limitations

These are the biggest current gaps based on the present codebase:

- There is no automated test suite in the project yet
- There is no CI workflow configured yet
- The frontend is still concentrated heavily in [frontend/src/AgentGraphUI.jsx](frontend/src/AgentGraphUI.jsx), which makes maintenance harder
- The backend route layer is still concentrated heavily in [backend/main.py](backend/main.py)
- Some workflows still rely on mock or seeded results rather than full real-trading validation
- Authentication, user accounts, and role-based access are not implemented
- Deployment is not productionized inside this repo yet
- Observability is mostly app-level logs rather than a full monitoring stack

## Remaining Work

### High Priority

- Split the large frontend dashboard into smaller page and component modules
- Split backend route definitions out of `main.py` into focused routers
- Add automated backend tests for strategy, backtest, mission, and evolution endpoints
- Add frontend component and flow tests for Strategy Lab, Mission Control, and Evolution Lab
- Add a CI pipeline that runs lint, build, and backend validation automatically
- Harden the evolution/evaluation flow with clearer loading, failure, and retry states

### Product Quality

- Add richer comparison metrics in Evolution Lab such as Sharpe delta, trade-count delta, and validation score deltas
- Improve Strategy Lab and Mission Control traceability between generated strategy, evaluations, validations, and exports
- Add clearer persistence around saved evaluation history so prior runs can be reviewed later
- Add better empty/error states across dashboard pages

### Trading And Data

- Strengthen real MT5 execution/backtest verification beyond mock/demo mode
- Expand dataset diagnostics and data-quality reporting
- Add more validation gates before champion/export decisions
- Track whether a metric comes from mock data, parsed MT5 reports, or derived evaluation output

### Platform And Ops

- Add deployment files and tested instructions for a production backend/frontend stack
- Add database migration support
- Add structured monitoring and alerting
- Add safer secrets handling for deployment environments

## Recommended Next Steps

If you want to move this project from prototype toward a stronger release, the best order is:

1. Add automated tests and CI
2. Break up the large frontend and backend files
3. Stabilize real MT5 and validation workflows
4. Improve persistence and auditability of evaluations
5. Add deployment and environment hardening

## License

MIT
