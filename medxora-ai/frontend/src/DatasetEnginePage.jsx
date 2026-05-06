import { useEffect, useMemo, useState } from "react";

import {
  convertMT5EURUSD,
  generateEURUSDOHLCV,
  getDatasetStatus,
  runEURUSDBacktest,
} from "./api";

const DEFAULT_FORM = {
  symbol: "EURUSD",
  timeframe: "M1",
  fast_ema: 20,
  slow_ema: 50,
  start_date: "2020-01-02",
  end_date: "2020-02-01",
  initial_balance: 10000,
};

function fmt(value) {
  if (value == null || value === "") return "--";
  return value;
}

function formatNumber(value) {
  if (value == null || value === "") return "--";
  const num = Number(value);
  if (Number.isNaN(num)) return value;
  return num.toLocaleString();
}

function formatCurrency(value) {
  if (value == null || value === "") return "--";
  const num = Number(value);
  if (Number.isNaN(num)) return value;
  return `$${num.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function MetricCard({ label, value, tone = "default" }) {
  const toneClass =
    tone === "good"
      ? "text-emerald-400"
      : tone === "warn"
        ? "text-[#f5b342]"
        : "text-[#fff7e6]";

  return (
    <div className="rounded-3xl border border-[#f5b342]/12 bg-[#f5b342]/8 p-4">
      <div className="text-[11px] font-black uppercase tracking-[.18em] text-[#fff7e6]/42">{label}</div>
      <div className={`mt-2 break-words text-xl font-black ${toneClass}`}>{value}</div>
    </div>
  );
}

function ActionButton({ children, onClick, disabled, primary = false }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={
        primary
          ? "rounded-2xl bg-[#f5b342] px-5 py-3 text-sm font-black text-black transition hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
          : "rounded-2xl border border-[#f5b342]/20 bg-[#f5b342]/8 px-5 py-3 text-sm font-black text-[#fff7e6] transition hover:bg-[#f5b342]/12 disabled:cursor-not-allowed disabled:opacity-50"
      }
    >
      {children}
    </button>
  );
}

function StatusBadge({ status }) {
  const normalized = String(status || "missing").toLowerCase();
  const className =
    normalized === "ready"
      ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-400"
      : normalized === "missing"
        ? "border-red-500/25 bg-red-500/10 text-red-400"
        : "border-[#f5b342]/25 bg-[#f5b342]/10 text-[#f5b342]";
  return <span className={`rounded-full border px-3 py-1 text-[11px] font-black uppercase tracking-[.18em] ${className}`}>{status}</span>;
}

export default function DatasetEnginePage({ refreshDashboard }) {
  const [status, setStatus] = useState(null);
  const [actionLabel, setActionLabel] = useState("");
  const [message, setMessage] = useState("Dataset Engine prepares the real EURUSD tick history that the rest of the app uses for backtests.");
  const [form] = useState(DEFAULT_FORM);
  const [backtest, setBacktest] = useState(null);

  const ohlcvFiles = useMemo(() => status?.ohlcv?.files || [], [status?.ohlcv?.files]);
  const parquetReady = status?.parquet?.status === "ready";
  const hasSelectedTimeframe = ohlcvFiles.some((file) => file.timeframe === form.timeframe && file.status === "ready");
  const totalTimeframes = ohlcvFiles.length || 7;

  const generatedCount = ohlcvFiles.filter((file) => file.status === "ready").length;

  const nextStep = useMemo(() => {
    if (status?.raw_file?.status !== "ready") {
      return "Add the EURUSD MT5 tick export into the outer DATA folder first.";
    }
    if (!parquetReady) {
      return "Convert the raw tick file into the fast Parquet dataset.";
    }
    if (generatedCount < totalTimeframes) {
      return "Generate the timeframe files so backtests can use ready-made candles.";
    }
    if (!backtest) {
      return "Run the demo backtest to confirm the dataset pipeline is working end to end.";
    }
    return "The data pipeline is ready. You can use these saved files for testing and strategy work.";
  }, [backtest, generatedCount, parquetReady, status?.raw_file?.status, totalTimeframes]);

  const readinessSummary = useMemo(() => {
    if (status?.raw_file?.status !== "ready") return "Waiting for source data";
    if (!parquetReady) return "Raw file found";
    if (generatedCount < totalTimeframes) return "Building timeframes";
    if (!backtest) return "Ready for a test backtest";
    return "Ready for strategy backtesting";
  }, [backtest, generatedCount, parquetReady, status?.raw_file?.status, totalTimeframes]);

  async function refreshStatus() {
    const response = await getDatasetStatus();
    setStatus(response.data);
    setBacktest(response.data?.latest_backtest || null);
  }

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      refreshStatus().catch((error) => setMessage(error.message));
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, []);

  async function runAction(label, runner, successMessage) {
    setActionLabel(label);
    setMessage(label);
    try {
      const response = await runner();
      setStatus(response.data?.status || null);
      setBacktest(response.data?.result || response.data?.status?.latest_backtest || null);
      setMessage(successMessage);
      await refreshDashboard?.();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setActionLabel("");
    }
  }

  return (
    <div className="space-y-5">
      <div className="rounded-[30px] border border-[#f5b342]/20 bg-[#11100e]/90 p-6 shadow-[0_24px_90px_rgba(0,0,0,.42)] backdrop-blur-2xl">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-xs font-black uppercase tracking-[.22em] text-[#f5b342]">MedXora AI</div>
            <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Dataset Engine</h1>
            <p className="mt-2 max-w-4xl text-sm text-[#fff7e6]/52 sm:text-base">
              This page turns your raw EURUSD MT5 tick file into clean backtest-ready data. It imports the tick history, builds saved timeframe files from M1 to D1, and lets you run a quick test backtest to confirm the data is usable.
            </p>
          </div>
          <ActionButton onClick={() => refreshStatus().catch((error) => setMessage(error.message))}>
            Refresh Status
          </ActionButton>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <MetricCard label="Raw Tick File" value={status?.raw_file?.status || "missing"} tone={status?.raw_file?.status === "ready" ? "good" : "warn"} />
        <MetricCard label="Compressed Dataset" value={status?.parquet?.status || "missing"} tone={parquetReady ? "good" : "warn"} />
        <MetricCard label="Ready Timeframes" value={`${generatedCount}/${totalTimeframes}`} tone={generatedCount ? "good" : "warn"} />
        <MetricCard label="Pipeline State" value={readinessSummary} tone={generatedCount === totalTimeframes ? "good" : "warn"} />
        <MetricCard label="Latest Equity" value={backtest ? formatCurrency(backtest.final_equity) : "--"} tone={backtest ? "good" : "default"} />
      </div>

      <div className="rounded-[30px] border border-[#f5b342]/18 bg-[#11100e]/90 p-5 shadow-[0_24px_90px_rgba(0,0,0,.42)]">
        <div className="text-[11px] font-black uppercase tracking-[.2em] text-[#f5b342]">What Is Happening Now</div>
        <div className="mt-2 text-lg font-black text-[#fff7e6]">{message}</div>
        <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-4">
          <div className="text-[11px] font-black uppercase tracking-[.18em] text-[#fff7e6]/42">Recommended Next Step</div>
          <div className="mt-2 text-sm leading-6 text-[#fff7e6]/72">{nextStep}</div>
        </div>
        {actionLabel ? (
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-black/35">
            <div className="h-full w-1/2 animate-pulse rounded-full bg-[#f5b342]" />
          </div>
        ) : null}
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.2fr_.8fr]">
        <div className="space-y-6">
          <div className="rounded-[30px] border border-[#f5b342]/16 bg-[#11100e]/90 p-6">
            <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-2xl font-black">Pipeline Actions</h2>
                <p className="mt-1 text-sm text-[#fff7e6]/45">Run these in order. The first two steps can take several minutes on a full multi-year tick dataset.</p>
              </div>
            </div>
            <div className="grid gap-4 lg:grid-cols-3">
              <div className="rounded-3xl border border-[#f5b342]/12 bg-[#f5b342]/8 p-5">
                <div className="text-sm font-black text-[#f5b342]">01</div>
                <h3 className="mt-2 text-lg font-black">Import Raw Tick File</h3>
                <p className="mt-2 min-h-[72px] text-sm text-[#fff7e6]/55">
                  Reads the EURUSD MT5 export from the outer `DATA` folder, checks the columns, and creates the saved compressed dataset the app works from.
                </p>
                <div className="mt-5">
                  <ActionButton
                    primary
                    disabled={Boolean(actionLabel)}
                    onClick={() => runAction(
                      "Converting MT5 tick CSV to Parquet. Keep the backend window open until it finishes.",
                      () => convertMT5EURUSD(),
                      "CSV converted to Parquet successfully.",
                    )}
                  >
                    Import And Compress Data
                  </ActionButton>
                </div>
              </div>

              <div className="rounded-3xl border border-[#f5b342]/12 bg-[#f5b342]/8 p-5">
                <div className="text-sm font-black text-[#f5b342]">02</div>
                <h3 className="mt-2 text-lg font-black">Build Timeframe Files</h3>
                <p className="mt-2 min-h-[72px] text-sm text-[#fff7e6]/55">
                  Creates saved candle files for M1, M5, M15, M30, H1, H4, and D1 without loading the whole dataset into memory at once.
                </p>
                <div className="mt-5">
                  <ActionButton
                    primary
                    disabled={!parquetReady || Boolean(actionLabel)}
                    onClick={() => runAction(
                      "Generating OHLCV files from the Parquet dataset.",
                      () => generateEURUSDOHLCV(),
                      "OHLCV timeframes generated successfully.",
                    )}
                  >
                    Build Saved Timeframes
                  </ActionButton>
                </div>
              </div>

              <div className="rounded-3xl border border-[#f5b342]/12 bg-[#f5b342]/8 p-5">
                <div className="text-sm font-black text-[#f5b342]">03</div>
                <h3 className="mt-2 text-lg font-black">Run Data Check Backtest</h3>
                <p className="mt-2 min-h-[72px] text-sm text-[#fff7e6]/55">
                  Uses one saved timeframe file and runs a simple EMA crossover test so you can confirm the data pipeline is behaving correctly.
                </p>
                <div className="mt-5">
                  <ActionButton
                    primary
                    disabled={!hasSelectedTimeframe || Boolean(actionLabel)}
                    onClick={() => runAction(
                      "Running the demo EMA backtest.",
                      () => runEURUSDBacktest(form),
                      "Backtest completed.",
                    )}
                  >
                    Run Data Check
                  </ActionButton>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="rounded-[30px] border border-[#f5b342]/16 bg-[#11100e]/90 p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-2xl font-black">Source Dataset</h2>
              <StatusBadge status={status?.raw_file?.status || "missing"} />
            </div>
            <div className="space-y-4 text-sm">
              <div>
                <div className="text-[#fff7e6]/42">Source Path</div>
                <div className="mt-1 break-all text-[#fff7e6]">{fmt(status?.raw_file?.path)}</div>
              </div>
              <div>
                <div className="text-[#fff7e6]/42">Detected Range</div>
                <div className="mt-1 text-[#fff7e6]">
                  {fmt(status?.raw_file?.first_tick)} to {fmt(status?.raw_file?.last_tick)}
                </div>
              </div>
              <div>
                <div className="text-[#fff7e6]/42">Parquet Output</div>
                <div className="mt-1 break-all text-[#fff7e6]">{fmt(status?.parquet?.path)}</div>
              </div>
              <div>
                <div className="text-[#fff7e6]/42">Rows Converted</div>
                <div className="mt-1 text-[#fff7e6]">{formatNumber(status?.parquet?.metadata?.rows)}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-[30px] border border-[#f5b342]/16 bg-[#11100e]/90 p-6">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-2xl font-black">Generated Timeframes</h2>
            <p className="mt-1 text-sm text-[#fff7e6]/45">
              These are the saved candle datasets created from the EURUSD tick history.
            </p>
          </div>
          <StatusBadge status={status?.ohlcv?.status || "missing"} />
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {ohlcvFiles.map((item) => (
            <div key={item.timeframe} className="rounded-xl border border-[#f5b342]/10 bg-[#f5b342]/8 px-5 py-4">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="text-base font-black text-[#fff7e6]">{item.timeframe}</div>
                  <div className="mt-2 text-sm leading-6 text-[#fff7e6]/60">
                    Rows: {formatNumber(item.rows)}
                  </div>
                  <div className="text-sm leading-6 text-[#fff7e6]/60">
                    Avg spread: {fmt(item.avg_spread)}
                  </div>
                </div>
                <StatusBadge status={item.status} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
