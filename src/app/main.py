"""Streamlit UI — a crypto market dashboard + an AI analyst you can ask in plain English.

Run from the project root:  streamlit run app.py
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st
from sqlalchemy import text
from streamlit_autorefresh import st_autorefresh

from src.app.dashboard import render_dashboard
from src.app.theme import ACCENT, CSS, SERIES
from src.config import PROVIDER_REGISTRY, default_provider_key, env_api_key
from src.crawler.runner import crawl_once
from src.db.connection import owner_engine
from src.db.introspect import schema_context
from src.llm.base import LLMError
from src.llm.factory import get_provider
from src.pipeline import answer, explain_sql
from src.safety.guard import UnsafeSQLError

st.set_page_config(
    page_title="Crypto AI Analyst",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(CSS, unsafe_allow_html=True)


# ─────────────────────────── Sidebar ───────────────────────────

def crawl_status() -> dict:
    try:
        with owner_engine().connect() as conn:
            ticks = conn.execute(text("SELECT COUNT(*) FROM price_ticks")).scalar_one()
            coins = conn.execute(text("SELECT COUNT(*) FROM coins")).scalar_one()
            last = conn.execute(text("SELECT MAX(captured_at) FROM price_ticks")).scalar_one()
            snaps = conn.execute(
                text("SELECT COUNT(DISTINCT captured_at) FROM price_ticks")
            ).scalar_one()
        return {"ticks": ticks, "coins": coins, "last": last, "snapshots": snaps}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def render_sidebar() -> tuple[str, str, str]:
    st.sidebar.markdown("### 📡 Live data")
    if st.sidebar.button("🔄 Crawl now", use_container_width=True):
        with st.spinner("Crawling CoinGecko…"):
            res = crawl_once()
        if res.error:
            st.sidebar.error(f"Crawl failed: {res.error}")
        else:
            st.sidebar.success(f"+{res.ticks} ticks @ {res.at:%H:%M:%S}")
            schema_context.cache_clear()

    status = crawl_status()
    if "error" in status:
        st.sidebar.caption("⚠️ DB not ready — start Docker, then Crawl now.")
    else:
        last = status["last"]
        last_txt = last.strftime("%H:%M:%S UTC") if last else "never"
        st.sidebar.caption(
            f"🟢 **{status['coins']}** coins · **{status['snapshots']}** snapshots · "
            f"**{status['ticks']:,}** ticks\n\nLast crawl: **{last_txt}**"
        )
    st.sidebar.divider()

    st.sidebar.markdown("### ⚙️ AI model")
    keys = list(PROVIDER_REGISTRY.keys())
    provider_key = st.sidebar.selectbox(
        "Provider", options=keys, index=keys.index(default_provider_key()),
        format_func=lambda k: PROVIDER_REGISTRY[k].label,
    )
    spec = PROVIDER_REGISTRY[provider_key]
    model = st.sidebar.selectbox("Model", options=spec.models, index=0)

    api_key = ""
    if spec.kind in ("openai_compatible", "anthropic"):
        env_present = bool(env_api_key(provider_key))
        api_key = st.sidebar.text_input(
            "API key", type="password",
            placeholder="from .env" if env_present else "paste your key",
            help="Blank = use the key from your .env file.",
        )
        if not api_key and not env_present:
            st.sidebar.warning(f"No {spec.env_key} in .env — paste one above.")
    else:
        st.sidebar.caption("Local provider — no key needed.")
    if spec.notes:
        st.sidebar.caption(f"ℹ️ {spec.notes}")

    st.sidebar.divider()
    st.sidebar.caption(
        "**Pipeline**\n\nCoinGecko → Kafka → MinIO + Postgres → this app.\n\n"
        "Read-only · SQL safety-guarded."
    )
    return provider_key, model, api_key


# ─────────────────────────── Ask-AI result rendering ───────────────────────────

def _time_col(df: pd.DataFrame) -> str | None:
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            return c
        if c.lower() in ("captured_at", "ath_date", "ts", "time", "timestamp"):
            return c
    return None


def _series_col(df: pd.DataFrame, exclude: set[str]) -> str | None:
    for c in df.columns:
        if c in exclude:
            continue
        if df[c].dtype == object and df[c].nunique() <= 8:
            return c
    return None


def pick_chart(df: pd.DataFrame) -> alt.Chart | None:
    if df.empty or df.shape[1] < 2:
        return None
    numeric_cols = df.select_dtypes("number").columns.tolist()
    if not numeric_cols:
        return None

    tcol = _time_col(df)
    if tcol is not None:
        value_col = next((c for c in numeric_cols if c != tcol), None)
        if value_col is not None:
            df = df.copy()
            df[tcol] = pd.to_datetime(df[tcol], errors="coerce")
            series_col = _series_col(df, exclude={tcol, value_col})
            enc = dict(
                x=alt.X(f"{tcol}:T", title="time"),
                y=alt.Y(f"{value_col}:Q", title=value_col, scale=alt.Scale(zero=False)),
                tooltip=list(df.columns),
            )
            if series_col:
                enc["color"] = alt.Color(f"{series_col}:N", scale=alt.Scale(range=SERIES))
                return alt.Chart(df).mark_line(point=True, strokeWidth=2).encode(**enc)
            return alt.Chart(df).mark_line(point=True, strokeWidth=2, color=ACCENT).encode(**enc)

    label_col = df.columns[0]
    value_col = next((c for c in numeric_cols if c != label_col), None)
    if value_col is None:
        return None
    if df.shape[0] <= 25:
        return (
            alt.Chart(df.head(25)).mark_bar(cornerRadius=4, color=ACCENT).encode(
                x=alt.X(f"{label_col}:N", sort="-y", title=label_col),
                y=alt.Y(f"{value_col}:Q", title=value_col),
                tooltip=list(df.columns),
            )
        )
    return (
        alt.Chart(df).mark_line(point=True, color=ACCENT).encode(
            x=alt.X(f"{label_col}:N", title=label_col),
            y=alt.Y(f"{value_col}:Q", title=value_col),
            tooltip=list(df.columns),
        )
    )


def _style_chart(chart: alt.Chart) -> alt.Chart:
    return (
        chart.properties(height=320, background="transparent")
        .configure_view(strokeWidth=0)
        .configure_axis(labelColor="#94a3b8", titleColor="#94a3b8",
                        gridColor="#1f2630", domainColor="#1f2630")
        .configure_legend(labelColor="#94a3b8", titleColor="#94a3b8")
    )


def render_result(res, idx: int, provider_args: tuple[str, str, str]) -> None:
    if not res.df.empty:
        chart = pick_chart(res.df)
        if chart is not None:
            st.altair_chart(_style_chart(chart), use_container_width=True)
        st.dataframe(res.df, use_container_width=True, hide_index=True)
        c1, c2 = st.columns([1, 1])
        c1.download_button(
            "⬇ Download CSV", res.df.to_csv(index=False).encode("utf-8-sig"),
            "result.csv", "text/csv", key=f"csv-{idx}", use_container_width=True,
        )
        explain_clicked = c2.button("💡 Explain SQL", key=f"explain-{idx}",
                                    use_container_width=True)
    else:
        st.info("Query ran successfully but returned no rows.")
        explain_clicked = st.button("💡 Explain SQL", key=f"explain-{idx}")

    if explain_clicked:
        pk, model, api_key = provider_args
        try:
            with st.spinner("Explaining…"):
                res.explanation = explain_sql(get_provider(pk, model, api_key),
                                              res.question, res.sql)
        except LLMError as exc:
            res.explanation = f"(Could not explain: {exc})"
    if res.explanation:
        st.info(res.explanation)

    with st.expander("View generated SQL"):
        st.code(res.sql, language="sql")
    st.caption(f"{res.row_count} row(s)")


# ─────────────────────────── Ask-AI tab ───────────────────────────

EXAMPLES = [
    "Top 10 coins by current price",
    "Which 5 coins gained the most in the last 24 hours?",
    "Price history of bitcoin over time",
    "Which coins have the highest market cap right now?",
    "Average 24h price change across all coins in the latest snapshot",
]


def render_ask_tab(provider_key: str, model: str, api_key: str) -> None:
    st.markdown(
        "<div class='sec'><span class='tag'>Natural language</span> "
        "Ask anything about the crypto data</div>",
        unsafe_allow_html=True,
    )
    st.caption("Type a question — the AI writes SQL, runs it read-only, and charts the answer.")

    if "history" not in st.session_state:
        st.session_state.history = []

    with st.form("ask", clear_on_submit=False):
        question = st.text_input(
            "Your question", label_visibility="collapsed",
            placeholder="e.g. Which 5 coins gained the most in the last 24 hours?",
        )
        col1, col2 = st.columns([1, 3])
        submitted = col1.form_submit_button("Ask AI ✨", type="primary",
                                            use_container_width=True)
        example = col2.selectbox("Examples", [""] + EXAMPLES,
                                 label_visibility="collapsed")

    if example and not submitted:
        question, submitted = example, True

    if submitted and question.strip():
        try:
            provider = get_provider(provider_key, model, api_key)
        except LLMError as exc:
            st.error(f"Provider setup failed: {exc}")
            return
        with st.spinner(f"Asking {PROVIDER_REGISTRY[provider_key].label}…"):
            try:
                res = answer(provider, question.strip())
                st.session_state.history.insert(0, res)
            except UnsafeSQLError as exc:
                st.error(f"🛑 Safety guard blocked the query: {exc}")
            except LLMError as exc:
                st.error(f"LLM error: {exc}")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Query failed: {exc}")

    if not st.session_state.history:
        st.caption("💡 Tip: pick an example above to get started.")
    for idx, res in enumerate(st.session_state.history):
        with st.container(border=True):
            st.markdown(f"**🔎 {res.question}**")
            render_result(res, idx, (provider_key, model, api_key))


# ─────────────────────────────── Main ───────────────────────────────

def render_hero(status: dict) -> None:
    live = "error" not in status
    live_pill = (
        "<span class='pill live'>● LIVE</span>" if live
        else "<span class='pill'>○ offline</span>"
    )
    st.markdown(
        f"""
        <div class='hero'>
          <h1>📈 Crypto AI Analyst</h1>
          <p>Live crypto market data, streamed from CoinGecko through Kafka into a
             data lake + warehouse — explore it visually or just ask in plain English.</p>
          <div class='pill-row'>
            {live_pill}
            <span class='pill'>Kafka → MinIO → Postgres</span>
            <span class='pill'>Multi-LLM · NL→SQL</span>
            <span class='pill'>Read-only &amp; safe</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    provider_key, model, api_key = render_sidebar()
    render_hero(crawl_status())

    tab_dash, tab_ask = st.tabs(["📊  Market Dashboard", "💬  Ask the AI"])
    with tab_dash:
        render_dashboard()
    with tab_ask:
        render_ask_tab(provider_key, model, api_key)


if __name__ == "__main__":
    main()
