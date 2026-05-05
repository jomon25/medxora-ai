# CLAUDE.md — AI Project Guide for MedXora AI

> This file is written for AI assistants (Claude, Gemini, GPT, etc.) to quickly understand
> the full project, its architecture, and how to make changes correctly.
> Read this before touching any code.

---

## Project Identity

**MedXora AI** is an autonomous MetaTrader 5 (MT5) trading strategy engine.
It generates EMA+RSI Expert Advisor strategies, compiles and backtests them via MT5,
and evolves them using a genetic algorithm. A React dashboard visualises all results.

**Tech stack:** FastAPI (Python) + React (Vite) + SQLite + MQL5 + Google Gemini (optional)

**Entry points:**
- Backend: `backend/main.py` — run with `uvicorn main:app --reload` from `backend/`
- Frontend: `frontend/` — run with `npm run dev`
- Database: auto-created as `medxora.db` on first startup

---

## Critical File Map

### Backend

| File | Purpose | When to edit |
|------|---------|--------------|
| `backend/main.py` | ALL REST endpoints — one place | Adding/changing API routes |
| `backend/database/db.py` | SQLAlchemy engine + session | DB connection changes |
| `backend/database/tables.py` | ORM models (Strategy, BacktestResult) | Schema changes |
| `backend/agents/strategy_creator.py` | Generates strategy JSON | Strategy format changes |
| `backend/agents/risk_manager.py` | Validates parameters | Risk rule changes |
| `backend/agents/backtest_analyst.py` | Scores + grades results | Scoring formula changes |
| `backend/agents/evolution_agent.py` | Runs N-generation evolution | Evolution loop changes |
| `backend/services/mql5_generator.py` | Writes .mq5 EA code | MQL5 template changes |
| `backend/services/mt5_config_generator.py` | Compiles EA + runs MT5 | MT5 integration changes |
| `backend/services/report_parser.py` | Parses MT5 HTML reports | Metric extraction changes |
| `backend/services/evolution_engine.py` | Mutation + fitness scoring | Mutation rules changes |
| `backend/services/gemini_service.py` | Google Gemini AI calls | AI analysis changes |
| `backend/services/logger.py` | In-memory + file logging | Log format/sources changes |
| `backend/config.py` | Paths and env vars | New environment variables |

### Frontend

| File | Purpose | When to edit |
|------|---------|--------------|
| `frontend/src/api.js` | ALL Axios calls | New API endpoints |
| `frontend/src/MedXoraDashboard.jsx` | Root: shared state + page router | Nav items, shared data |
| `frontend/src/components/Layout.jsx` | Sidebar + Topbar | Navigation labels/icons |
| `frontend/src/components/Badge.jsx` | Status badge pill | Badge styling |
| `frontend/src/components/MetricCard.jsx` | KPI card | Card layout |
| `frontend/src/components/Panel.jsx` | Section card wrapper | Card styling |
| `frontend/src/components/PageHeader.jsx` | Page title + description | Header layout |
| `frontend/src/components/StrategyTable.jsx` | Strategy list table | Table columns |
| `frontend/src/components/SafeResponsiveChart.jsx` | ResizeObserver chart wrapper | Chart sizing |
| `frontend/src/pages/CommandCenter.jsx` | Main dashboard (default view) | Dashboard content |
| `frontend/src/pages/StrategiesPage.jsx` | Strategy library list | Strategy list UI |
| `frontend/src/pages/BacktestsPage.jsx` | Backtest history table | Backtest UI |
| `frontend/src/pages/AgentsPage.jsx` | AI agents control room | Agent cards |
| `frontend/src/pages/EvolutionPage.jsx` | Evolution lab | Evolution controls |
| `frontend/src/pages/LogsPage.jsx` | System log viewer | Log display |
| `frontend/src/pages/SettingsPage.jsx` | Config + roadmap | Settings fields |
| `frontend/src/pages/StrategyDetailPage.jsx` | Single strategy detail | Detail layout |
| `frontend/src/utils/formatters.js` | fmt, statusCls, mapApiStrategy, mapApiAgent | Data mapping |
| `frontend/src/utils/chartData.js` | Demo chart data + buildBandData | Chart data |
| `frontend/src/utils/pipelineHelpers.js` | Pipeline card builders | Pipeline display |
| `frontend/src/data/roadmap.js` | Static config: timeframes, phases, agents | Content changes |

---

## Import Conventions

### Backend Python imports

The backend runs from the `backend/` directory. All imports are relative to that directory.

```python
# In main.py
from database.db     import get_db, init_db
from database.tables import Strategy, BacktestResult
from agents.strategy_creator import generate_strategy
from services.mql5_generator  import generate_mql5
from services.logger          import log_info, log_error
from config                   import GENERATED_STRATEGIES_DIR

# In services/ or agents/ (they add sys.path to reach backend root)
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATABASE_URL
from database.db import Base
```

### Frontend JS imports

```js
// In any page component
import { generateMql5Pipeline, runBacktest, listStrategies } from "../api";
import { useNavigate } from "react-router-dom";
```

---

## Strategy Data Flow (end-to-end)

```
1. GET /api/strategy/generate-mql5
       ↓
   agents/strategy_creator.py → generate_strategy()
       Returns: { name, symbol, timeframe, strategy_type, parameters: {...} }
       ↓
   services/mql5_generator.py → generate_mql5(strategy)
       Writes: generated_strategies/<name>.mq5
       ↓
   database/tables.py → Strategy row inserted in medxora.db

2. POST /api/backtest/<name>?mock=true
       ↓
   agents/backtest_analyst.py → analyze(name, use_mock=True)
       ↓
   services/report_parser.py → parse_mock_result(name)
       Returns: { net_profit, max_drawdown, win_rate, ... }
       ↓
   services/evolution_engine.py → score_result(metrics)
       Returns: composite float score
       ↓
   database/tables.py → BacktestResult row inserted

3. POST /api/strategy/<name>/evolve
       ↓
   agents/evolution_agent.py → run_evolution(base, generations=3)
       ↓
   services/evolution_engine.py → evolve_population() → mutate_strategy()
       Returns: list of 5 children
       ↓
   services/report_parser.py → parse_mock_result(child_name) for each child
       ↓
   select_best() → winner
       ↓
   services/mql5_generator.py → generate_mql5(winner)
   database/tables.py → Strategy row (generation+1, parent_id=parent.id)
```

---

## Database Schema

### strategies table
```
id           INTEGER PK
name         TEXT UNIQUE        — e.g. "EMA_RSI_AB12CD34"
symbol       TEXT               — e.g. "EURUSD"
timeframe    TEXT               — e.g. "M15"
type         TEXT               — always "trend_following"
fast_ema     INTEGER            — 5–30
slow_ema     INTEGER            — 40–100
rsi_period   INTEGER            — always 14
rsi_buy      REAL               — 52–60
rsi_sell     REAL               — 40–48
stop_loss    INTEGER            — points, e.g. 300
take_profit  INTEGER            — points, e.g. 600
risk_percent REAL               — e.g. 1.0
mql5_file    TEXT               — absolute path to .mq5 file
parent_id    INTEGER FK → id    — NULL for generation 0
generation   INTEGER            — 0 = original, 1 = first child, etc.
created_at   DATETIME
```

### backtest_results table
```
id               INTEGER PK
strategy_id      INTEGER FK → strategies.id
net_profit       REAL
gross_profit     REAL
gross_loss       REAL
max_drawdown     REAL        — percentage, e.g. 12.5
win_rate         REAL        — percentage, e.g. 58.3
total_trades     INTEGER
profit_factor    REAL        — e.g. 1.72
expected_payoff  REAL
sharpe_ratio     REAL
recovery_factor  REAL
monthly_profit   REAL
yearly_profit    REAL
report_file      TEXT        — path to .htm file (NULL for mock)
status           TEXT        — "completed" | "pending" | "error"
created_at       DATETIME
```

---

## API Endpoint Reference

### Phase 2 — Strategy Generator
```
GET  /api/strategy/generate          → strategy JSON (no save)
POST /api/strategy/risk-check        → { passed, issues, warnings }
```

### Phase 3 — MQL5 Generator
```
GET  /api/strategy/generate-mql5     → { status, strategy, file, strategy_id }
POST /api/strategy/generate-code     → { status, file, name }
GET  /api/strategy/download/{name}   → .mq5 file download
```

### Phase 5 — MT5 Config
```
GET  /api/backtest/create-config/{name}  → { status, config_path, parameters }
```

### Phase 6 — MT5 Runner
```
GET  /api/backtest/run/{name}            → { status, report_file } or error
```

### Phase 7 — Report Parser
```
GET  /api/backtest/parse/{name}          → { strategy, source, metrics: {...} }
```

### Phase 8/9 — Database + Strategy APIs
```
GET  /api/strategies                     → [ { id, name, ..., net_profit, win_rate } ]
GET  /api/strategies/{id}               → full detail + mql5_code + backtest_results[]
GET  /api/strategies/{id}/code          → { strategy, mql5_file, code }
GET  /api/strategies/{id}/backtest      → { strategy, total_runs, results[] }
POST /api/backtest/{name}?mock=true     → { status, strategy, analysis }
GET  /api/backtest/results              → recent BacktestResult rows with strategy_name
```

### Phase 10 — Dashboard
```
GET  /api/dashboard/stats  → { total_strategies, total_backtests, best_net_profit, ... }
```

### Phase 12 — Evolution
```
POST /api/strategy/{name}/evolve?generations=3
     → { original, evolved, best_score, generations[], improved }
```

### Phase 13 — Agents
```
GET  /api/agents  → [ { id, name, role, status, description, capabilities, runs, endpoint } ]
```

### Phase 14 — Gemini AI
```
POST /api/strategy/{name}/ai-analyze  → { strategy, analysis, suggestion }
```

### Phase 15 — Logs
```
GET  /api/logs?limit=100&level=ERROR  → { total, logs: [ { timestamp, level, source, message } ] }
```

---

## Key Rules and Constraints

### Strategy parameters
- `fast_ema` must always be < `slow_ema`
- `stop_loss` max: 800 points
- `take_profit` min: 200 points
- `take_profit / stop_loss` ratio must be >= 1.5
- `risk_percent` max: 2.0
- `rsi_buy` sensible range: 50–68
- `rsi_sell` sensible range: 32–50

### Fitness score formula
```python
score = (net_profit * 0.3) + (profit_factor * 200) + (win_rate * 3) + (sharpe * 100) - (drawdown * 5)
```

### Mock data seeding
`parse_mock_result(strategy_name)` uses `random.Random(hash(strategy_name) & 0xFFFFFF)` —
the same strategy name always produces the same mock results.

### Directory layout (auto-created by config.py)
```
generated_strategies/   ← .mq5 and .ex5 files
backtest_reports/       ← MT5 HTML reports (.htm)
mt5_workspace/          ← .ini config files
```

### MT5 integration notes
- MT5 must be installed at the path set in `MT5_PATH` (default: `C:\Program Files\MetaTrader 5\terminal64.exe`)
- EA must be compiled to .ex5 before backtesting (Phase 4 manual step OR auto-compile in mt5_config_generator.py)
- `_find_mt5_data_dir()` checks: explicit env var → portable mode → AppData scan
- MT5 is launched with `/compile:<path>` to compile, then `/config:<ini>` to backtest
- Report poll timeout: 60 seconds; backtest timeout: 600 seconds

---

## Frontend Architecture

Navigation is tab-based (state inside `MedXoraDashboard.jsx`), not URL-based.

| Nav Item | Page File | What it shows |
|----------|-----------|--------------|
| Command Center | `pages/CommandCenter.jsx` | KPIs, pipeline, batch analytics, charts |
| Strategies | `pages/StrategiesPage.jsx` | Full strategy list + Generate button |
| Backtests | `pages/BacktestsPage.jsx` | All backtest runs table |
| AI Agents | `pages/AgentsPage.jsx` | Agent cards + workflow diagram |
| Evolution Lab | `pages/EvolutionPage.jsx` | Mutation controls + result panel |
| MQL5 Code | (same as Strategies) | Strategy list → click to see MQL5 code |
| Logs | `pages/LogsPage.jsx` | Log entries with level filter |
| Settings | `pages/SettingsPage.jsx` | MT5 config + roadmap |
| (Strategy Detail) | `pages/StrategyDetailPage.jsx` | Opened by clicking any strategy row |

### Shared components (`src/components/`)

| Component | Purpose |
|-----------|---------|
| `Layout.jsx` | `Sidebar` + `Topbar` — imported as named exports |
| `Badge.jsx` | Status pill using `statusCls()` |
| `MetricCard.jsx` | KPI card with title/value/sub |
| `Panel.jsx` | Section card wrapper with header |
| `PageHeader.jsx` | Page title + description row |
| `StrategyTable.jsx` | Reusable strategy list table |
| `SafeResponsiveChart.jsx` | ResizeObserver wrapper for Recharts |
| `ChartTooltip.jsx` | Styled tooltip for all charts |
| `Spinner.jsx` | Loading spinner |

### Utility modules (`src/utils/`)

| File | Exports |
|------|---------|
| `formatters.js` | `fmt`, `statusCls`, `avg`, `mapApiStrategy`, `mapApiAgent` |
| `chartData.js` | `DEMO_EQUITY`, `DEMO_MONTHLY`, `buildBandData`, `buildProfitHistogram` |
| `pipelineHelpers.js` | `PIPELINE_STEP_DEFS`, `buildPipelineCards`, `formatPipelineStatus`, `formatServiceLabel` |

### CSS variables (dark theme)
```css
--bg: #0d1117          /* page background */
--surface: #161b22     /* card background */
--surface2: #1c2128    /* hover / inner surface */
--border: #30363d
--text: #e6edf3
--muted: #8b949e
--accent: #58a6ff      /* blue — primary actions */
--green: #3fb950       /* profit, success */
--red: #f85149         /* loss, error */
--yellow: #d29922      /* warning, win rate */
--purple: #bc8cff      /* evolution, generation */
```

### Button classes
```css
.btn-primary   /* blue fill */
.btn-green     /* green fill */
.btn-purple    /* purple fill */
.btn-red       /* red fill */
.btn-ghost     /* transparent */
```

---

## How to Add a New Feature

### New backend endpoint
1. Add the handler function to `backend/main.py`
2. Use `log_info` / `log_error` from `services.logger` inside it
3. Add the corresponding Axios call to `frontend/src/api.js`

### New frontend page
1. Create `frontend/src/pages/NewPage.jsx`
2. Add the route to `frontend/src/App.jsx`: `<Route path="/new-page" element={<NewPage />} />`
3. Add the nav link to `frontend/src/components/Layout.jsx`

### New database column
1. Add the column to the correct class in `backend/database/tables.py`
2. Delete `medxora.db` and restart the backend (SQLite recreates the file)
   — OR — write an Alembic migration if data must be preserved

### New agent
1. Create `backend/agents/<agent_name>.py` with the agent logic
2. Import and call it from the relevant endpoint in `main.py`
3. Add it to the `GET /api/agents` response list
4. Add it to the Agents.jsx `ROLE_ICONS` and `ROLE_COLORS` maps

---

## Common Pitfalls

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Import "fastapi" could not be resolved` (IDE warning) | Pylance can't see the venv | Select the venv interpreter in VSCode: `Ctrl+Shift+P → Python: Select Interpreter` |
| `Strategy not found` (404) | Strategy name not in DB | Call `/api/strategy/generate-mql5` first to save it |
| `.ex5 not produced` | MT5 compile failed | Open .mq5 in MetaEditor (F4), compile manually, fix errors |
| MT5 report not found | Wrong symbol, no history, or MT5 crashed | Check MT5 has tick data for the date range and symbol |
| `No improvement found` in evolution | Seeded mock gives same scores | Expected behaviour — try more generations or real backtesting |
| Database migration error | Column added after DB created | Delete `medxora.db` and restart backend |
| CORS error in browser | Backend not running | Start backend with `uvicorn main:app --reload` |

---

## Running Everything

```bash
# Terminal 1 — Backend
cd "c:\Users\jomon\Desktop\MedXora AI\medxora-ai\backend"
venv\Scripts\activate
uvicorn main:app --reload

# Terminal 2 — Frontend
cd "c:\Users\jomon\Desktop\MedXora AI\medxora-ai\frontend"
npm run dev
```

URLs:
- API: http://127.0.0.1:8000
- Swagger docs: http://127.0.0.1:8000/docs
- Dashboard: http://localhost:5173

---

## Phase Completion Status

| Phase | Title | Status |
|-------|-------|--------|
| 2 | Strategy Generator | Done |
| 3 | MQL5 Code Generator | Done |
| 4 | Manual MT5 Compile | Manual step |
| 5 | MT5 Config Generator | Done |
| 6 | MT5 Auto Backtest Runner | Done |
| 7 | Backtest Report Parser | Done |
| 8 | Database (SQLite) | Done |
| 9 | Strategy Detail API | Done |
| 10 | Frontend Dashboard | Done |
| 11 | Strategy Detail Page | Done |
| 12 | Evolution Engine | Done |
| 13 | AI Agents | Done |
| 14 | Gemini Integration | Done |
| 15 | Logs and Error Monitor | Done |
| 16 | Final Demo Flow | Ready to test |
