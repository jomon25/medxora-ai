"""
report_parser.py
Extracts performance metrics from MT5 HTML/XML backtest reports.

Primary:  BeautifulSoup (html.parser) — richer extraction including trade list.
Fallback: stdlib html.parser — always available, extracts core metrics.
"""

import os
import re
from html.parser import HTMLParser


# ── BeautifulSoup extraction ───────────────────────────────────────────────────

def _parse_with_bs4(html: str) -> dict:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    result = {}

    # MT5 reports store metrics in <td> pairs: label | value
    cells = [td.get_text(" ", strip=True) for td in soup.find_all("td")]

    lookup = {
        "total net profit":   "net_profit",
        "net profit":         "net_profit",
        "gross profit":       "gross_profit",
        "gross loss":         "gross_loss",
        "maximal drawdown":   "max_drawdown",
        "drawdown":           "max_drawdown",
        "profit trades":      "win_trades",       # raw count — converted below
        "total trades":       "total_trades",
        "profit factor":      "profit_factor",
        "expected payoff":    "expected_payoff",
        "sharpe ratio":       "sharpe_ratio",
        "recovery factor":    "recovery_factor",
    }

    for i, cell in enumerate(cells):
        lower = cell.lower()
        for keyword, field in lookup.items():
            if keyword in lower and field not in result and i + 1 < len(cells):
                val = _extract_number(cells[i + 1])
                if val is not None:
                    result[field] = val

    # Win rate — profit trades / total trades × 100
    if "win_trades" in result and result.get("total_trades", 0) > 0:
        result["win_rate"] = round(result.pop("win_trades") / result["total_trades"] * 100, 2)
    elif "win_trades" in result:
        result.pop("win_trades")

    # Derived monthly / yearly
    if "net_profit" in result:
        result["yearly_profit"]  = round(result["net_profit"] / 4, 2)
        result["monthly_profit"] = round(result["yearly_profit"] / 12, 2)

    # Trade list (each row in a <table> with class "trades" or similar)
    trades = []
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if not any(h in headers for h in ("profit", "deal", "symbol")):
            continue
        for tr in table.find_all("tr")[1:]:
            tds = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(tds) >= 4:
                trades.append(tds)
        if trades:
            break
    if trades:
        result["trade_list"] = trades[:200]   # cap at 200 rows

    return result


# ── Stdlib fallback extraction ─────────────────────────────────────────────────

class _StdlibParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.data: list[str] = []
        self._buf: list[str] = []

    def handle_data(self, data):
        t = data.strip()
        if t:
            self._buf.append(t)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._buf:
            self.data.append(" ".join(self._buf))
            self._buf = []


def _parse_with_stdlib(html: str) -> dict:
    parser = _StdlibParser()
    parser.feed(html)
    cells = parser.data
    result = {}

    lookup = {
        "net profit":       "net_profit",
        "total net profit": "net_profit",
        "gross profit":     "gross_profit",
        "gross loss":       "gross_loss",
        "drawdown":         "max_drawdown",
        "maximal drawdown": "max_drawdown",
        "profit trades":    "win_trades",
        "total trades":     "total_trades",
        "profit factor":    "profit_factor",
        "sharpe ratio":     "sharpe_ratio",
        "recovery factor":  "recovery_factor",
    }

    for i, cell in enumerate(cells):
        lower = cell.lower()
        for keyword, field in lookup.items():
            if keyword in lower and field not in result and i + 1 < len(cells):
                val = _extract_number(cells[i + 1])
                if val is not None:
                    result[field] = val

    if "win_trades" in result and result.get("total_trades", 0) > 0:
        result["win_rate"] = round(result.pop("win_trades") / result["total_trades"] * 100, 2)
    elif "win_trades" in result:
        result.pop("win_trades")

    if "net_profit" in result:
        result["yearly_profit"]  = round(result["net_profit"] / 4, 2)
        result["monthly_profit"] = round(result["yearly_profit"] / 12, 2)

    return result


# ── Number extractor ───────────────────────────────────────────────────────────

def _extract_number(text: str):
    text = text.replace("%", "").replace(",", "").strip()
    m = re.search(r"-?\d+\.?\d*", text)
    if m:
        try:
            return float(m.group())
        except ValueError:
            return None
    return None


# ── Public API ─────────────────────────────────────────────────────────────────

def parse_report(report_path: str) -> dict:
    """
    Parse an MT5 HTML/XML report file and return a dict of performance metrics.
    Uses BeautifulSoup when available (richer extraction), falls back to stdlib.

    Keys returned:
      net_profit, gross_profit, gross_loss, max_drawdown, win_rate,
      total_trades, profit_factor, expected_payoff, sharpe_ratio,
      recovery_factor, monthly_profit, yearly_profit, trade_list (optional)
    """
    if not report_path or not os.path.exists(report_path):
        return {}

    with open(report_path, "r", encoding="utf-8", errors="ignore") as f:
        html = f.read()

    try:
        return _parse_with_bs4(html)
    except ImportError:
        return _parse_with_stdlib(html)


def parse_mock_result(strategy_name: str) -> dict:
    """
    Return deterministic plausible mock metrics when MT5 is not available.
    Seeded from the strategy name so the same name always gives the same result.
    """
    import random
    rng = random.Random(hash(strategy_name) & 0xFFFFFF)
    net     = round(rng.uniform(500, 8000), 2)
    trades  = rng.randint(80, 400)
    wins    = rng.randint(int(trades * 0.45), int(trades * 0.70))
    pf      = round(rng.uniform(1.1, 2.5), 2)
    dd      = round(rng.uniform(3, 25), 2)
    sharpe  = round(rng.uniform(0.5, 2.0), 2)
    recov   = round(rng.uniform(1.0, 5.0), 2)
    return {
        "net_profit":      net,
        "gross_profit":    round(net * pf, 2),
        "gross_loss":      round(net * (pf - 1), 2),
        "max_drawdown":    dd,
        "win_rate":        round(wins / trades * 100, 2),
        "total_trades":    trades,
        "profit_factor":   pf,
        "expected_payoff": round(net / trades, 2),
        "sharpe_ratio":    sharpe,
        "recovery_factor": recov,
        "monthly_profit":  round(net / 48, 2),
        "yearly_profit":   round(net / 4, 2),
    }
