"""Investing & Trading page — watchlist, price charts, alerts, and index education."""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
from datetime import datetime, timedelta
from api import request_json
from state import ensure_session

ensure_session()

st.title("Investing & Trading")

# ── Constants ──────────────────────────────────────────────────────────────────
SUGGESTED = {
    "Tech":     ["MSFT", "AAPL", "NVDA", "GOOGL", "META", "AMZN"],
    "Consumer": ["COST", "WMT", "TGT", "NKE"],
    "EV / AI":  ["TSLA", "PLTR", "AMD"],
    "Finance":  ["BRK-B", "JPM", "V", "MA"],
    "Index":    ["SPY", "QQQ", "VTI", "VOO"],
}

PERIODS = {"1W": "1w", "1M": "1mo", "3M": "3mo", "6M": "6mo", "1Y": "1y", "2Y": "2y", "5Y": "5y"}

# ── ETF Catalog (static metadata) ─────────────────────────────────────────────
ETF_CATALOG = {
    # S&P 500
    "SPY":  {"name": "SPDR S&P 500 ETF Trust",         "issuer": "State Street", "expense_ratio": 0.0945, "index": "S&P 500",               "inception": "1993-01-22", "category": "US Large Cap"},
    "VOO":  {"name": "Vanguard S&P 500 ETF",            "issuer": "Vanguard",     "expense_ratio": 0.03,   "index": "S&P 500",               "inception": "2010-09-07", "category": "US Large Cap"},
    "IVV":  {"name": "iShares Core S&P 500 ETF",        "issuer": "BlackRock",    "expense_ratio": 0.03,   "index": "S&P 500",               "inception": "2000-05-15", "category": "US Large Cap"},
    # NASDAQ
    "QQQ":  {"name": "Invesco QQQ Trust",               "issuer": "Invesco",      "expense_ratio": 0.20,   "index": "NASDAQ-100",            "inception": "1999-03-10", "category": "US Growth"},
    "QQQM": {"name": "Invesco NASDAQ 100 ETF",          "issuer": "Invesco",      "expense_ratio": 0.15,   "index": "NASDAQ-100",            "inception": "2020-10-13", "category": "US Growth"},
    # Total / Broad Market
    "VTI":  {"name": "Vanguard Total Stock Market ETF", "issuer": "Vanguard",     "expense_ratio": 0.03,   "index": "CRSP US Total Market",  "inception": "2001-05-24", "category": "US Total Market"},
    # Dow Jones
    "DIA":  {"name": "SPDR Dow Jones Industrial Avg ETF","issuer": "State Street","expense_ratio": 0.16,   "index": "Dow Jones IA",          "inception": "1998-01-14", "category": "US Large Cap"},
    # Small Cap
    "IWM":  {"name": "iShares Russell 2000 ETF",        "issuer": "BlackRock",    "expense_ratio": 0.19,   "index": "Russell 2000",          "inception": "2000-05-22", "category": "US Small Cap"},
    # Mid Cap
    "MDY":  {"name": "SPDR S&P MidCap 400 ETF",         "issuer": "State Street", "expense_ratio": 0.23,   "index": "S&P MidCap 400",        "inception": "1995-05-04", "category": "US Mid Cap"},
    # International Developed
    "VEA":  {"name": "Vanguard Developed Markets ETF",  "issuer": "Vanguard",     "expense_ratio": 0.05,   "index": "FTSE Developed ex-US",  "inception": "2007-07-02", "category": "Intl Developed"},
    # International Emerging
    "VWO":  {"name": "Vanguard Emerging Markets ETF",   "issuer": "Vanguard",     "expense_ratio": 0.08,   "index": "FTSE Emerging Markets", "inception": "2005-03-04", "category": "Intl Emerging"},
    "VXUS": {"name": "Vanguard Total Intl Stock ETF",   "issuer": "Vanguard",     "expense_ratio": 0.07,   "index": "FTSE Global ex-US",     "inception": "2011-01-26", "category": "Intl Total"},
    # Bonds
    "BND":  {"name": "Vanguard Total Bond Market ETF",  "issuer": "Vanguard",     "expense_ratio": 0.03,   "index": "Bloomberg US Aggregate","inception": "2007-04-03", "category": "US Bonds"},
    "AGG":  {"name": "iShares Core US Aggregate Bond",  "issuer": "BlackRock",    "expense_ratio": 0.03,   "index": "Bloomberg US Aggregate","inception": "2003-09-22", "category": "US Bonds"},
    # Commodities
    "GLD":  {"name": "SPDR Gold Shares",                "issuer": "State Street", "expense_ratio": 0.40,   "index": "Gold Spot Price",       "inception": "2004-11-18", "category": "Commodities"},
}

# ── Major indices reference data ──────────────────────────────────────────────
INDICES = [
    {
        "icon": "🇺🇸", "name": "S&P 500",
        "what": "500 largest US companies by market cap",
        "holdings": "~500", "weighting": "Market-cap",
        "etfs": "SPY · VOO · IVV", "expense": "0.03–0.09%",
        "note": "Covers ~80% of total US market cap. The most widely tracked equity index in the world.",
    },
    {
        "icon": "💻", "name": "NASDAQ-100",
        "what": "100 largest non-financial NASDAQ-listed stocks",
        "holdings": "100", "weighting": "Market-cap (modified)",
        "etfs": "QQQ · QQQM", "expense": "0.15–0.20%",
        "note": "Tech-heavy — Apple, Microsoft, NVIDIA, Google ~40%. Higher growth potential but more volatile than S&P 500.",
    },
    {
        "icon": "🏛️", "name": "Dow Jones Industrial Average",
        "what": "30 iconic US blue-chip companies",
        "holdings": "30", "weighting": "Price-weighted",
        "etfs": "DIA", "expense": "0.16%",
        "note": "Oldest US index (1896). Price-weighted means higher-priced stocks have disproportionate influence — a quirk not seen in modern indices.",
    },
    {
        "icon": "📈", "name": "Russell 2000",
        "what": "2,000 smallest US stocks in the Russell 3000",
        "holdings": "~2,000", "weighting": "Market-cap",
        "etfs": "IWM", "expense": "0.19%",
        "note": "The small-cap benchmark. Higher growth potential and volatility; more domestically focused than large-caps.",
    },
    {
        "icon": "🌐", "name": "US Total Market",
        "what": "All ~3,700+ publicly traded US stocks",
        "holdings": "~3,700", "weighting": "Market-cap",
        "etfs": "VTI", "expense": "0.03%",
        "note": "Broadest US equity exposure. Includes large, mid, small, and micro-cap. VTI at 0.03% is one of the cheapest funds in existence.",
    },
    {
        "icon": "🌍", "name": "MSCI EAFE",
        "what": "Developed markets outside US & Canada",
        "holdings": "~900", "weighting": "Market-cap",
        "etfs": "VEA · EFA", "expense": "0.05–0.07%",
        "note": "Europe, Australasia, Far East. Core building block for international diversification in developed economies.",
    },
    {
        "icon": "🌏", "name": "MSCI Emerging Markets",
        "what": "Stocks in ~25 emerging-market countries",
        "holdings": "~1,400", "weighting": "Market-cap",
        "etfs": "VWO · EEM", "expense": "0.08–0.20%",
        "note": "China, India, Taiwan, Brazil dominate. Higher long-run growth potential with more political and currency risk.",
    },
    {
        "icon": "🏦", "name": "Bloomberg US Aggregate",
        "what": "US investment-grade bonds — govt + corporate",
        "holdings": "~10,000", "weighting": "Market-value",
        "etfs": "BND · AGG", "expense": "0.03%",
        "note": "The main US bond benchmark. Inversely correlated with interest rates. Used for portfolio stability and income.",
    },
]

# ── Person selector ────────────────────────────────────────────────────────────
DATA_RAW_DIR = Path(__file__).parent.parent.parent / "data" / "raw"

def get_people():
    if not DATA_RAW_DIR.exists():
        return ["Huimin"]
    return sorted(d.name for d in DATA_RAW_DIR.iterdir()
                  if d.is_dir() and not d.name.startswith("."))

people = get_people()
person = st.selectbox("Person", people, index=0)

# ── Watchlist state ────────────────────────────────────────────────────────────
def _load_from_api(person: str) -> list[str]:
    try:
        return request_json("GET", f"/api/stocks/watchlist/{person}")["tickers"]
    except Exception:
        return []

def _save_to_api(person: str, tickers: list[str]):
    try:
        request_json("PUT", f"/api/stocks/watchlist/{person}", {"tickers": tickers})
    except Exception as e:
        st.error(f"Failed to save watchlist: {e}")

if ("watchlist" not in st.session_state
        or st.session_state.get("watchlist_person") != person):
    st.session_state.watchlist = _load_from_api(person)
    st.session_state.watchlist_person = person

def add_ticker(ticker: str):
    t = ticker.strip().upper()
    if t and t not in st.session_state.watchlist:
        st.session_state.watchlist = st.session_state.watchlist + [t]
        _save_to_api(person, st.session_state.watchlist)

def remove_ticker(ticker: str):
    st.session_state.watchlist = [t for t in st.session_state.watchlist if t != ticker]
    _save_to_api(person, st.session_state.watchlist)

# ── Market data helpers ────────────────────────────────────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def fetch_quotes(tickers_key: str):
    try:
        return request_json("GET", f"/api/stocks/quotes?tickers={tickers_key}")
    except Exception:
        return []

@st.cache_data(ttl=300, show_spinner=False)
def fetch_history(ticker: str, period: str):
    try:
        return request_json("GET", f"/api/stocks/history/{ticker}?period={period}")["data"]
    except Exception:
        return []

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_long_history(ticker: str):
    """Fetch max history for CAGR calculation — cached 1 hour."""
    try:
        return request_json("GET", f"/api/stocks/history/{ticker}?period=max")["data"]
    except Exception:
        return []

# ── Alert helpers ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=30, show_spinner=False)
def fetch_alerts(person: str):
    try:
        return request_json("GET", f"/api/alerts/{person}")["alerts"]
    except Exception:
        return []

def _create_alert(person: str, body: dict) -> bool:
    try:
        request_json("POST", f"/api/alerts/{person}", body)
        fetch_alerts.clear()
        return True
    except Exception as e:
        st.error(f"Failed to create alert: {e}")
        return False

def _toggle_alert(person: str, alert_id: str, enabled: bool):
    try:
        request_json("PUT", f"/api/alerts/{person}/{alert_id}", {"enabled": enabled})
        fetch_alerts.clear()
    except Exception as e:
        st.error(f"Failed to update alert: {e}")

def _delete_alert(person: str, alert_id: str):
    try:
        request_json("DELETE", f"/api/alerts/{person}/{alert_id}")
        fetch_alerts.clear()
    except Exception as e:
        st.error(f"Failed to delete alert: {e}")

# ── CAGR computation ───────────────────────────────────────────────────────────
def compute_cagr(history: list[dict], years: int) -> float | None:
    """Annualized return over the last `years` years. Returns None if insufficient data."""
    if not history:
        return None
    cutoff = datetime.now() - timedelta(days=int(365.25 * years))
    start_price = None
    for row in history:
        if datetime.strptime(row["date"], "%Y-%m-%d") >= cutoff:
            start_price = row["close"]
            break
    if start_price is None or start_price <= 0:
        return None
    end_price = history[-1]["close"]
    return (end_price / start_price) ** (1.0 / years) - 1

def normalized_series(history: list[dict], years: int | None) -> tuple[list, list]:
    """Return (dates, values) normalized to 100 at the start of the period."""
    if not history:
        return [], []
    if years is not None:
        cutoff = datetime.now() - timedelta(days=int(365.25 * years))
        data = [r for r in history if datetime.strptime(r["date"], "%Y-%m-%d") >= cutoff]
    else:
        data = history
    if not data:
        return [], []
    base = data[0]["close"]
    if base <= 0:
        return [], []
    return [r["date"] for r in data], [r["close"] / base * 100 for r in data]

# ── Alert warning banners (shown above tabs) ───────────────────────────────────
alerts = fetch_alerts(person)
recent_cutoff = datetime.utcnow() - timedelta(hours=24)
recently_triggered = [
    a for a in alerts
    if a.get("last_triggered")
    and datetime.fromisoformat(a["last_triggered"]) >= recent_cutoff
]
for a in recently_triggered:
    pct = a.get("last_change_pct", 0) or 0
    arrow = "▲" if pct > 0 else "▼"
    color = "green" if pct > 0 else "red"
    st.warning(
        f"**Alert** — **{a['ticker']}** moved "
        f"<span style='color:{color}'>{arrow} {abs(pct):.2f}%</span> "
        f"over {a['time_range']}",
        icon="⚡",
    )

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_trade, tab_edu = st.tabs(["📈 Watchlist & Alerts", "📚 Index Education"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Watchlist & Alerts
# ══════════════════════════════════════════════════════════════════════════════
with tab_trade:
    watchlist = st.session_state.watchlist

    col_watch, col_add = st.columns([3, 2])

    with col_add:
        st.subheader("Add Stocks")
        for category, tickers in SUGGESTED.items():
            not_in_list = [t for t in tickers if t not in watchlist]
            if not_in_list:
                with st.expander(category):
                    cols = st.columns(3)
                    for i, ticker in enumerate(not_in_list):
                        if cols[i % 3].button(f"+ {ticker}", key=f"add_{ticker}"):
                            add_ticker(ticker)
                            st.rerun()

        with st.form("add_custom", clear_on_submit=True):
            custom = st.text_input("Custom ticker", placeholder="e.g. NFLX")
            if st.form_submit_button("Add") and custom.strip():
                add_ticker(custom)
                st.rerun()

    with col_watch:
        st.subheader("My Watchlist")
        if not watchlist:
            st.info("No stocks yet — add some from the suggestions →")
        else:
            tickers_key = ",".join(watchlist)
            with st.spinner("Loading quotes…"):
                quotes_list = fetch_quotes(tickers_key)
            quotes = {q["ticker"]: q for q in quotes_list if "ticker" in q}

            cols_per_row = 3
            for row_start in range(0, len(watchlist), cols_per_row):
                row_tickers = watchlist[row_start: row_start + cols_per_row]
                cols = st.columns(cols_per_row)
                for col, ticker in zip(cols, row_tickers):
                    q = quotes.get(ticker, {})
                    price  = q.get("price")
                    change = q.get("change")
                    pct    = q.get("pct_change")
                    name   = q.get("name", ticker)

                    with col:
                        with st.container(border=True):
                            top_l, top_r = st.columns([3, 1])
                            top_l.markdown(f"**{ticker}**")
                            if top_r.button("✕", key=f"rm_{ticker}", help=f"Remove {ticker}"):
                                remove_ticker(ticker)
                                st.rerun()

                            st.caption(name[:30] if name else "")
                            if price:
                                color = "green" if (change or 0) >= 0 else "red"
                                arrow = "▲" if (change or 0) >= 0 else "▼"
                                st.markdown(f"**${price:,.2f}**")
                                st.markdown(
                                    f"<span style='color:{color};font-size:0.85em'>"
                                    f"{arrow} {abs(change or 0):.2f} ({abs(pct or 0):.2f}%)</span>",
                                    unsafe_allow_html=True,
                                )
                            else:
                                st.markdown("**—**")
                                st.caption("unavailable")

    # ── Price chart ─────────────────────────────────────────────────────────────
    if watchlist:
        st.divider()
        st.subheader("Price Chart")

        col_t, col_p = st.columns([2, 4])
        with col_t:
            selected = st.selectbox("Stock", watchlist, key="chart_ticker")
        with col_p:
            period_label = st.radio(
                "Period", list(PERIODS.keys()), index=4, horizontal=True, key="chart_period"
            )
        period = PERIODS[period_label]

        with st.spinner(f"Loading {selected} {period_label} history…"):
            history = fetch_history(selected, period)

        if history:
            q = quotes.get(selected, {}) if watchlist else {}

            s1, s2, s3, s4, s5, s6 = st.columns(6)
            price   = q.get("price")
            pct     = q.get("pct_change")
            d_high  = q.get("day_high")
            d_low   = q.get("day_low")
            w52_h   = q.get("week52_high")
            w52_l   = q.get("week52_low")
            mktcap  = q.get("market_cap")
            pe      = q.get("pe_ratio")
            div_yld = q.get("dividend_yield")

            s1.metric("Price", f"${price:,.2f}" if price else "—",
                      delta=f"{pct:+.2f}%" if pct is not None else None)
            s2.metric("Day Range",
                      f"{d_low:.2f} – {d_high:.2f}" if d_low and d_high else "—")
            s3.metric("52W Range",
                      f"{w52_l:.0f} – {w52_h:.0f}" if w52_l and w52_h else "—")
            s4.metric("Mkt Cap",
                      f"${mktcap/1e12:.2f}T" if mktcap and mktcap >= 1e12
                      else f"${mktcap/1e9:.1f}B" if mktcap else "—")
            s5.metric("P/E", f"{pe:.1f}" if pe else "—")
            s6.metric("Div Yield", f"{div_yld*100:.2f}%" if div_yld else "—")

            dates  = [r["date"]   for r in history]
            opens  = [r["open"]   for r in history]
            highs  = [r["high"]   for r in history]
            lows   = [r["low"]    for r in history]
            closes = [r["close"]  for r in history]
            vols   = [r["volume"] for r in history]

            fig = make_subplots(
                rows=2, cols=1, shared_xaxes=True,
                row_heights=[0.75, 0.25], vertical_spacing=0.03,
            )
            fig.add_trace(go.Candlestick(
                x=dates, open=opens, high=highs, low=lows, close=closes,
                name=selected,
                increasing_line_color="#26a69a",
                decreasing_line_color="#ef5350",
            ), row=1, col=1)

            bar_colors = ["#26a69a" if closes[i] >= opens[i] else "#ef5350"
                          for i in range(len(closes))]
            fig.add_trace(go.Bar(
                x=dates, y=vols, name="Volume",
                marker_color=bar_colors, showlegend=False,
            ), row=2, col=1)

            fig.update_layout(
                title=f"{selected} — {period_label}",
                xaxis_rangeslider_visible=False,
                height=520,
                margin=dict(l=0, r=0, t=40, b=0),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#ccc"),
            )
            fig.update_xaxes(showgrid=False)
            fig.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,0.15)")
            st.plotly_chart(fig, use_container_width=True)

            sector  = q.get("sector")
            fwd_pe  = q.get("forward_pe")
            if sector or fwd_pe:
                with st.expander("More info"):
                    if q.get("name"):
                        st.write(f"**{q['name']}**")
                    if sector:
                        st.write(f"Sector: {sector}")
                    if fwd_pe:
                        st.write(f"Forward P/E: {fwd_pe:.1f}")
        else:
            st.warning(f"No price history found for **{selected}**. The ticker may be invalid.")

    # ── Price Alerts ─────────────────────────────────────────────────────────────
    st.divider()

    alert_header = "⚡ Price Alerts"
    if recently_triggered:
        alert_header += f"  ({len(recently_triggered)} triggered)"

    with st.expander(alert_header, expanded=bool(recently_triggered)):

        if alerts:
            st.subheader("Configured Alerts")
            for a in alerts:
                last_pct = a.get("last_change_pct")
                last_ts  = a.get("last_triggered")
                was_triggered = (
                    last_ts and
                    datetime.fromisoformat(last_ts) >= recent_cutoff
                )
                with st.container(border=True):
                    c1, c2, c3, c4, c5 = st.columns([1, 2, 3, 1, 1])
                    c1.markdown(f"**{a['ticker']}**")
                    dir_label = {"up": "▲ up", "down": "▼ down", "both": "▲▼"}.get(a["direction"], a["direction"])
                    c2.caption(f"{dir_label} ≥ {a['threshold_pct']}% / {a['time_range']}")
                    c3.caption(a["email"])

                    new_enabled = c4.toggle("On", value=a["enabled"], key=f"tog_{a['id']}", label_visibility="collapsed")
                    if new_enabled != a["enabled"]:
                        _toggle_alert(person, a["id"], new_enabled)
                        st.rerun()

                    if c5.button("✕", key=f"del_a_{a['id']}", help="Delete alert"):
                        _delete_alert(person, a["id"])
                        st.rerun()

                    if was_triggered and last_pct is not None:
                        ts_str = datetime.fromisoformat(last_ts).strftime("%b %d %H:%M UTC")
                        arrow  = "▲" if last_pct > 0 else "▼"
                        color  = "green" if last_pct > 0 else "red"
                        st.markdown(
                            f"<small>Last triggered: <span style='color:{color}'>"
                            f"{arrow} {abs(last_pct):.2f}%</span> · {ts_str}</small>",
                            unsafe_allow_html=True,
                        )

            st.divider()

        st.subheader("Add New Alert")
        with st.form("add_alert_form", clear_on_submit=True):
            fa1, fa2 = st.columns(2)

            if watchlist:
                alert_ticker = fa1.selectbox("Stock", watchlist, key="alert_tkr")
            else:
                alert_ticker = fa1.text_input("Stock ticker", placeholder="e.g. AAPL")

            alert_email = fa2.text_input("Notify email", placeholder="you@example.com")

            fb1, fb2, fb3 = st.columns(3)
            alert_dir   = fb1.selectbox("Direction", ["both", "up", "down"],
                                        format_func=lambda x: {"both": "▲▼ Either", "up": "▲ Gain", "down": "▼ Drop"}[x])
            alert_pct   = fb2.number_input("Threshold %", min_value=0.1, max_value=100.0,
                                           value=5.0, step=0.5)
            alert_range = fb3.selectbox("Over period",
                                        ["1d", "5d", "1mo", "3mo"],
                                        format_func=lambda x: {"1d": "1 day", "5d": "5 days",
                                                                "1mo": "1 month", "3mo": "3 months"}[x])

            submitted = st.form_submit_button("Add Alert", use_container_width=True)
            if submitted:
                if not alert_email.strip():
                    st.error("Email is required.")
                elif not alert_ticker:
                    st.error("Select a stock first.")
                else:
                    if _create_alert(person, {
                        "ticker": str(alert_ticker).strip().upper(),
                        "direction": alert_dir,
                        "threshold_pct": float(alert_pct),
                        "time_range": alert_range,
                        "email": alert_email.strip(),
                    }):
                        st.success(f"Alert added for {alert_ticker}.")
                        st.rerun()

        st.caption(
            "Alerts are checked every 2 hours during market hours (9:30–16:00 ET, Mon–Fri). "
            "Configure SMTP credentials in `.env` to enable email delivery."
        )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Index Education
# ══════════════════════════════════════════════════════════════════════════════
with tab_edu:
    st.header("📚 Index & ETF Education")
    st.caption("Learn the foundations of index investing — what the major benchmarks track, how to choose an ETF, and how different funds have performed over time.")

    # ── Introduction ──────────────────────────────────────────────────────────
    with st.expander("What is a Stock Index?", expanded=False):
        st.markdown("""
A **stock index** is a list of securities that follow a set of rules — which stocks qualify, how many, and how much weight each one gets. An index itself is not investable; you invest by buying an **ETF or mutual fund** that tracks it.

**Why indices matter:**
- They give you a single number to describe "how the market did"
- They provide a benchmark to compare active managers against
- Through ETFs, they let you own hundreds or thousands of stocks cheaply and instantly

**Weighting methods:**

| Method | How it works | Example |
|---|---|---|
| **Market-cap weighted** | Larger companies get more weight | S&P 500, NASDAQ-100, Russell 2000 |
| **Price-weighted** | Higher stock prices get more weight | Dow Jones (a $500 stock matters 5× more than a $100 stock) |
| **Equal-weighted** | Every stock counts the same | RSP (equal-weight S&P 500) |

**ETFs vs Mutual Funds:**
- Both can track the same index, but ETFs trade on exchanges like stocks (any time during market hours), while mutual funds price once per day at close.
- Vanguard's mutual fund versions (VFIAX, FXAIX) often have expense ratios identical to their ETF counterparts.

**Why expense ratios matter (compounding):**

A seemingly small 0.20% difference compounds significantly. On a $100,000 portfolio growing at 8%/year for 30 years:
- 0.03% expense ratio → **~$976,000**
- 0.50% expense ratio → **~$843,000**
- The extra 0.47%/year costs over **$133,000** over 30 years.
        """)

    # ── Major Indices Overview ────────────────────────────────────────────────
    st.subheader("Major US & Global Indices")
    st.caption("The benchmarks every investor should know.")

    for i in range(0, len(INDICES), 2):
        cols = st.columns(2)
        for j, col in enumerate(cols):
            if i + j >= len(INDICES):
                break
            idx = INDICES[i + j]
            with col:
                with st.container(border=True):
                    st.markdown(f"**{idx['icon']} {idx['name']}**")
                    st.caption(idx["what"])
                    m1, m2 = st.columns(2)
                    m1.markdown(f"**Holdings:** {idx['holdings']}")
                    m2.markdown(f"**Weighting:** {idx['weighting']}")
                    st.markdown(f"**ETFs:** `{idx['etfs']}` &nbsp;·&nbsp; **Expense:** {idx['expense']}")
                    st.info(idx["note"], icon="💡")

    # ── ETF & Fund Explorer ───────────────────────────────────────────────────
    st.divider()
    st.subheader("ETF & Fund Explorer")
    st.caption("All funds listed below. Returns shown are annualized CAGR. N/A = ETF did not exist for that full period.")

    # ── Static metadata table (all ETFs) ──────────────────────────────────────
    all_rows = []
    for t, info in ETF_CATALOG.items():
        all_rows.append({
            "Ticker":        t,
            "Name":          info["name"],
            "Category":      info["category"],
            "Index Tracked": info["index"],
            "Issuer":        info["issuer"],
            "Exp. Ratio":    f"{info['expense_ratio']}%",
            "Inception":     info["inception"],
        })
    st.dataframe(all_rows, use_container_width=True, hide_index=True)

    # ── Historical returns ─────────────────────────────────────────────────────
    st.divider()
    st.markdown("**Historical Returns (Annualized CAGR)**")

    if not st.session_state.get("edu_loaded"):
        st.button(
            "📈 Load Historical Returns & Chart",
            use_container_width=True,
            on_click=lambda: st.session_state.update(edu_loaded=True),
        )
    else:
        all_tickers = list(ETF_CATALOG.keys())
        with st.spinner("Fetching historical data for all funds…"):
            histories = {t: fetch_long_history(t) for t in all_tickers}

        def fmt(v):
            return f"{v*100:+.1f}%" if v is not None else "N/A"

        return_rows = []
        for t in all_tickers:
            hist = histories[t]
            info = ETF_CATALOG[t]
            return_rows.append({
                "Ticker":     t,
                "Category":   info["category"],
                "Exp. Ratio": f"{info['expense_ratio']}%",
                "1Y CAGR":    fmt(compute_cagr(hist, 1)),
                "5Y CAGR":    fmt(compute_cagr(hist, 5)),
                "10Y CAGR":   fmt(compute_cagr(hist, 10)),
                "20Y CAGR":   fmt(compute_cagr(hist, 20)),
            })
        st.dataframe(return_rows, use_container_width=True, hide_index=True)
        st.caption("Past performance does not guarantee future results. Data via Yahoo Finance.")

        # ── Normalized performance chart ───────────────────────────────────────
        st.divider()
        col_period, col_pick = st.columns([2, 5])
        chart_period_label = col_period.radio(
            "Chart Period",
            ["1Y", "5Y", "10Y", "Max"],
            index=1,
            horizontal=True,
            key="edu_chart_period",
        )
        selected_for_chart = col_pick.multiselect(
            "Funds to plot",
            options=all_tickers,
            default=["SPY", "QQQ", "VTI", "IWM"],
            format_func=lambda t: t,
            key="edu_chart_tickers",
        )
        period_years = {"1Y": 1, "5Y": 5, "10Y": 10, "Max": None}[chart_period_label]

        COLORS = [
            "#4c9be8", "#f4a261", "#2ec4b6", "#e71d36",
            "#9b5de5", "#f7b731", "#26a69a", "#ef5350",
            "#ff79c6", "#50fa7b", "#bd93f9", "#ffb86c",
        ]

        fig = go.Figure()
        for i, t in enumerate(selected_for_chart):
            dates, values = normalized_series(histories[t], period_years)
            if dates:
                fig.add_trace(go.Scatter(
                    x=dates, y=values,
                    mode="lines",
                    name=t,
                    line=dict(color=COLORS[i % len(COLORS)], width=2),
                    hovertemplate=f"<b>{t}</b><br>%{{x}}<br>%{{y:.1f}} (base 100)<extra></extra>",
                ))

        title_suffix = f"last {chart_period_label}" if period_years else "all available history"
        fig.update_layout(
            title=f"Normalized Performance — {title_suffix} (base = 100 at start)",
            height=460,
            margin=dict(l=0, r=0, t=40, b=0),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#ccc"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode="x unified",
        )
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,0.15)")
        st.plotly_chart(fig, use_container_width=True)

        # ── Key takeaways ──────────────────────────────────────────────────────
        with st.expander("Tips for Choosing an Index ETF"):
            st.markdown("""
**For most long-term investors, a simple 2-3 fund portfolio is hard to beat:**

1. **US Total Market** (VTI) — all US stocks, max diversification, 0.03% expense
2. **International Total** (VXUS) — all non-US stocks, 0.07% expense
3. **US Bond Market** (BND) — stability and income, 0.03% expense

A typical "lazy portfolio" allocation might be: 60% VTI · 30% VXUS · 10% BND — then rebalance annually.

**When to consider QQQ (NASDAQ-100):**
- You want higher tech exposure and accept higher volatility
- Its 10Y+ returns have been exceptional but it's more concentrated (top 10 stocks ≈ 50% of weight)

**SPY vs VOO vs IVV — which S&P 500 ETF?**
- All three track the same index. VOO and IVV have lower expense ratios (0.03%) vs SPY (0.09%)
- SPY has the highest liquidity and options volume — preferred by short-term traders
- For long-term buy-and-hold: VOO or IVV wins on cost

**Small-cap premium:**
- IWM (Russell 2000) historically outperforms large-caps over very long periods — but with more volatility and longer drawdown periods. Only appropriate if you have a 10+ year horizon.
            """)
