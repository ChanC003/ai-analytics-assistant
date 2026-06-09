"""Market Dashboard tab — pre-built analytics charts (no LLM needed)."""

from __future__ import annotations

from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from src.app.theme import ACCENT, ACCENT_2, BAD, GOLD, NEUTRAL, OK, SERIES
from src.db import analytics as a

_CHART_BG = "transparent"
_AXIS = "#94a3b8"
_GRID = "#1f2630"


def _base(chart: alt.Chart, height: int = 300) -> alt.Chart:
    return (
        chart.properties(height=height, background=_CHART_BG)
        .configure_view(strokeWidth=0)
        .configure_axis(
            labelColor=_AXIS, titleColor=_AXIS, gridColor=_GRID,
            domainColor=_GRID, labelFontSize=11, titleFontSize=11,
        )
        .configure_legend(labelColor=_AXIS, titleColor=_AXIS)
    )


def _fmt_money(v) -> str:
    if v is None or pd.isna(v):
        return "—"
    v = float(v)
    for unit, div in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(v) >= div:
            return f"${v / div:.2f}{unit}"
    return f"${v:,.0f}"


# ─────────────────────────────── KPI strip ───────────────────────────────

def _kpi(col, label: str, value: str, sub: str = "", accent: str = ACCENT) -> None:
    col.markdown(
        f"<div class='kpi' style='--c:{accent}'>"
        f"<div class='label'>{label}</div>"
        f"<div class='value'>{value}</div>"
        f"<div class='sub'>{sub}</div></div>",
        unsafe_allow_html=True,
    )


def render_kpis() -> None:
    k = a.kpis()
    if not k:
        st.info("No data yet — the crawler is starting. Charts appear once data arrives.")
        return

    movers = a.movers_24h(limit=50)
    top_gainer = movers.sort_values("pct", ascending=False).iloc[0] if len(movers) else None
    last = k.get("last_crawl")
    last_txt = pd.to_datetime(last).strftime("%H:%M:%S UTC") if last else "—"

    c1, c2, c3, c4, c5 = st.columns(5)
    _kpi(c1, "Coins tracked", f"{int(k['coins'])}", "top market cap", ACCENT)
    _kpi(c2, "Total market cap", _fmt_money(k.get("total_mcap")),
         "latest snapshot", ACCENT_2)
    _kpi(c3, "24h volume", _fmt_money(k.get("total_volume")), "all tracked coins", GOLD)
    if top_gainer is not None:
        arrow = "▲" if top_gainer["pct"] >= 0 else "▼"
        cls = "up" if top_gainer["pct"] >= 0 else "down"
        _kpi(c4, "Top gainer 24h", top_gainer["symbol"].upper(),
             f"<span class='{cls}'>{arrow} {top_gainer['pct']:.2f}%</span>", OK)
    else:
        _kpi(c4, "Top gainer 24h", "—", "", OK)
    _kpi(c5, "Snapshots", f"{int(k['snapshots'])}", f"last @ {last_txt}", ACCENT)


# ─────────────────────────────── Charts ───────────────────────────────

def chart_market_cap() -> None:
    df = a.top_by_market_cap(limit=10)
    if df.empty:
        st.caption("No market-cap data yet.")
        return
    df = df.copy()
    df["mcap_b"] = df["market_cap"] / 1e9
    df["label"] = df["symbol"].str.upper()
    df["mcap_txt"] = df["mcap_b"].apply(
        lambda v: f"{v / 1000:.2f}T" if v >= 1000 else f"{v:.0f}B")
    base = alt.Chart(df).encode(y=alt.Y("label:N", sort="-x", title=None))
    bars = base.mark_bar(cornerRadius=4, color=ACCENT).encode(
        x=alt.X("mcap_b:Q", title="Market cap (USD bn)"),
        tooltip=[
            alt.Tooltip("name:N", title="Coin"),
            alt.Tooltip("market_cap:Q", title="Market cap", format=",.0f"),
            alt.Tooltip("price_usd:Q", title="Price", format=",.2f"),
            alt.Tooltip("price_change_pct_24h:Q", title="24h %", format=".2f"),
        ],
    )
    labels = base.mark_text(align="left", dx=4, color="#cbd5e1", fontSize=11).encode(
        x="mcap_b:Q", text="mcap_txt:N",
    )
    st.altair_chart(_base((bars + labels), 300), use_container_width=True)


def chart_movers() -> None:
    df = a.movers_24h(limit=8)
    if df.empty:
        st.caption("No 24h change data yet.")
        return
    df = df.copy()
    df["label"] = df["symbol"].str.upper()
    df["pct_txt"] = df["pct"].apply(lambda v: f"{v:+.1f}%")
    base = alt.Chart(df).encode(y=alt.Y("label:N", sort="-x", title=None))
    bars = base.mark_bar(cornerRadius=4).encode(
        x=alt.X("pct:Q", title="24h change (%)"),
        color=alt.Color("direction:N",
                        scale=alt.Scale(domain=["gain", "loss"], range=[OK, BAD]),
                        legend=None),
        tooltip=[alt.Tooltip("name:N", title="Coin"),
                 alt.Tooltip("pct:Q", title="24h %", format=".2f")],
    )
    # Two text layers: positives labelled to the right, negatives to the left,
    # so the value always sits just past the bar's outer end.
    pos = base.transform_filter("datum.pct >= 0").mark_text(
        align="left", dx=4, fontSize=11, color="#cbd5e1").encode(x="pct:Q", text="pct_txt:N")
    neg = base.transform_filter("datum.pct < 0").mark_text(
        align="right", dx=-4, fontSize=11, color="#cbd5e1").encode(x="pct:Q", text="pct_txt:N")
    st.altair_chart(_base((bars + pos + neg), 300), use_container_width=True)


def chart_price_history() -> None:
    symbols = a.available_symbols(limit=20)
    if not symbols:
        st.caption("No coins available yet.")
        return

    c1, c2 = st.columns([3, 1.4])
    default = [s for s in ["BTC", "ETH", "SOL"] if s in symbols][:3] or symbols[:2]
    picked = c1.multiselect(
        "Coins to compare", options=symbols, default=default,
        help="Price over time across all crawl snapshots.",
    )
    # Mixing $62k BTC with $0.x coins on one linear axis flattens everything.
    # "% change" normalizes to each coin's first point (fair comparison);
    # "USD (log)" keeps real prices but log-scales so small coins are visible.
    mode = c2.radio(
        "View", ["% change", "USD (log)"], horizontal=True,
        help="% change = movement vs each coin's first snapshot. USD (log) = real price, log scale.",
    )

    df = a.price_history(picked)
    if df.empty or df["captured_at"].nunique() < 2:
        st.caption("Need at least 2 snapshots — let the crawler run a couple of minutes.")
        return
    df = df.copy()
    df["captured_at"] = pd.to_datetime(df["captured_at"])
    df["symbol"] = df["symbol"].str.upper()

    if mode == "% change":
        # Index each coin to 0% at its earliest snapshot.
        df = df.sort_values("captured_at")
        base = df.groupby("symbol")["price_usd"].transform("first")
        df["pct"] = (df["price_usd"] / base - 1) * 100
        y = alt.Y("pct:Q", title="Change since start (%)")
        val_tip = alt.Tooltip("pct:Q", title="Change", format="+.2f")
    else:
        y = alt.Y("price_usd:Q", title="Price (USD, log)",
                  scale=alt.Scale(type="log"))
        val_tip = alt.Tooltip("price_usd:Q", title="Price", format=",.4f")

    chart = (
        alt.Chart(df)
        .mark_line(point=True, strokeWidth=2)
        .encode(
            x=alt.X("captured_at:T", title="Time"),
            y=y,
            color=alt.Color("symbol:N", scale=alt.Scale(range=SERIES), title="Coin"),
            tooltip=[
                alt.Tooltip("symbol:N"),
                alt.Tooltip("captured_at:T", title="Time", format="%H:%M:%S"),
                val_tip,
            ],
        )
    )
    st.altair_chart(_base(chart, 360), use_container_width=True)


def chart_volume() -> None:
    df = a.volume_leaders(limit=10)
    if df.empty:
        st.caption("No volume data yet.")
        return
    df = df.copy()
    df["vol_b"] = df["total_volume"] / 1e9
    df["label"] = df["symbol"].str.upper()
    df["vol_txt"] = df["vol_b"].apply(lambda v: f"{v:.1f}")
    base = alt.Chart(df).encode(y=alt.Y("label:N", sort="-x", title=None))
    bars = base.mark_bar(cornerRadius=4, color=GOLD).encode(
        x=alt.X("vol_b:Q", title="24h volume (USD bn)"),
        tooltip=[alt.Tooltip("name:N", title="Coin"),
                 alt.Tooltip("total_volume:Q", title="Volume", format=",.0f")],
    )
    labels = base.mark_text(align="left", dx=4, color="#cbd5e1", fontSize=11).encode(
        x="vol_b:Q", text="vol_txt:N",
    )
    st.altair_chart(_base((bars + labels), 360), use_container_width=True)


def chart_sentiment() -> None:
    df = a.sentiment_split()
    if df.empty:
        st.caption("No sentiment data yet.")
        return
    color_map = {"Gainers": OK, "Losers": BAD, "Flat": NEUTRAL}
    counts = {r["bucket"]: int(r["n"]) for _, r in df.iterrows()}
    total = sum(counts.values()) or 1
    df = df.copy()
    # Rich legend label: "Gainers · 13 (27%)" right inside the donut legend,
    # so the figures sit with the chart instead of floating far below it.
    df["legend"] = df["bucket"].map(
        lambda b: f"{b} · {counts.get(b, 0)} ({counts.get(b, 0) / total * 100:.0f}%)")
    legend_domain = [f"{b} · {counts.get(b, 0)} ({counts.get(b, 0) / total * 100:.0f}%)"
                     for b in color_map]
    legend_range = list(color_map.values())

    donut = (
        alt.Chart(df)
        .mark_arc(innerRadius=72, outerRadius=102, cornerRadius=2,
                  stroke="#08080c", strokeWidth=3, opacity=0.95)
        .encode(
            theta=alt.Theta("n:Q", stack=True),
            color=alt.Color(
                "legend:N",
                scale=alt.Scale(domain=legend_domain, range=legend_range),
                legend=alt.Legend(title=None, orient="bottom", direction="horizontal",
                                  symbolType="circle", labelFontSize=12, columns=3),
            ),
            order=alt.Order("n:Q", sort="descending"),
            tooltip=[alt.Tooltip("bucket:N", title="Group"),
                     alt.Tooltip("n:Q", title="Coins")],
        )
    )
    center = (
        alt.Chart(pd.DataFrame({"t": [str(int(total))]}))
        .mark_text(color="#f8fafc", fontSize=36, fontWeight="bold", dy=-6)
        .encode(text="t:N")
    )
    sub = (
        alt.Chart(pd.DataFrame({"l": ["coins"]}))
        .mark_text(color="#7c8696", fontSize=12, dy=22)
        .encode(text="l:N")
    )
    layered = (donut + center + sub).properties(height=360, background=_CHART_BG)
    st.altair_chart(
        layered.configure_view(strokeWidth=0)
        .configure_legend(labelColor=_AXIS, titleColor=_AXIS),
        use_container_width=True,
    )


def _section(title: str, tag: str) -> None:
    st.markdown(
        f"<div class='sec'><span class='tag'>{tag}</span> {title}</div>",
        unsafe_allow_html=True,
    )


def _render_live_bar() -> None:
    """Live controls — toggle auto-refresh + manual refresh + last-updated stamp."""
    c1, c2, c3 = st.columns([1.1, 1.2, 3])
    live = c1.toggle("🟢 Live", value=True, key="dash_live",
                     help="Auto-refresh the dashboard as new data is crawled.")
    interval = c2.selectbox("Refresh", [10, 15, 30, 60], index=1,
                            format_func=lambda s: f"every {s}s",
                            label_visibility="collapsed", disabled=not live)
    if live:
        st_autorefresh(interval=interval * 1000, key="dash_refresh")
    c3.markdown(
        f"<div style='text-align:right;color:#7c8696;font-size:12px;padding-top:6px'>"
        f"{'🔴 streaming' if live else '⏸ paused'} · "
        f"refreshed {datetime.now():%H:%M:%S}</div>",
        unsafe_allow_html=True,
    )


def render_dashboard() -> None:
    _render_live_bar()
    render_kpis()
    st.write("")

    left, right = st.columns(2)
    with left:
        _section("Top 10 by market cap", "Ranking")
        chart_market_cap()
    with right:
        _section("Biggest 24h movers", "Momentum")
        chart_movers()

    st.write("")
    _section("Price trend over time", "Time series")
    chart_price_history()

    st.write("")
    left2, right2 = st.columns(2)
    with left2:
        _section("Top 10 by 24h volume", "Liquidity")
        chart_volume()
    with right2:
        _section("Gainers vs losers split", "Sentiment")
        chart_sentiment()
