"""
World News Intelligence Dashboard
Streamlit multi-page app.

Run: streamlit run src/presentation/dashboard.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime, timedelta, timezone

from src.application.config import Settings
from src.container import Container
from src.domain.models import NewsCategory
from src.infrastructure.logging_config import setup_logging

# ── App config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="World News Intelligence",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Colour palette per category ─────────────────────────────────────────────

CATEGORY_COLORS: dict[str, str] = {
    NewsCategory.GEOPOLITICS.value: "#E74C3C",
    NewsCategory.ECONOMY.value:     "#2ECC71",
    NewsCategory.TECH_AI.value:     "#3498DB",
    NewsCategory.CLIMATE.value:     "#27AE60",
    NewsCategory.HEALTH.value:      "#9B59B6",
    NewsCategory.CANADA.value:      "#E67E22",
    NewsCategory.UNKNOWN.value:     "#95A5A6",
}

SENTIMENT_COLORS = {
    "positive": "#2ECC71",
    "neutral":  "#BDC3C7",
    "negative": "#E74C3C",
}


# ── Cached container (one per session) ──────────────────────────────────────

@st.cache_resource
def get_container() -> Container:
    setup_logging()
    settings = Settings.from_yaml(Path("config/settings.yaml"))
    return Container.from_settings(settings)


@st.cache_data(ttl=300)  # refresh every 5 min
def load_articles(
    category: str | None = None,
    since_days: int = 7,
    source: str | None = None,
    limit: int = 1000,
) -> pd.DataFrame:
    container = get_container()
    since = datetime.now(timezone.utc) - timedelta(days=since_days)
    cat = NewsCategory(category) if category else None
    articles = container.repository.get_all(
        category=cat, since=since, source=source or None, limit=limit
    )
    if not articles:
        return pd.DataFrame()

    rows = []
    for a in articles:
        rows.append({
            "hash":       a.content_hash,
            "title":      a.title,
            "url":        a.url,
            "source":     a.source_name,
            "published":  a.published_utc,
            "category":   a.category.value,
            "confidence": a.category_confidence,
            "sentiment":  a.sentiment.value,
            "sent_score": a.sentiment_score,
            "entities":   ", ".join(a.entities[:5]),
            "keywords":   ", ".join(a.keywords[:5]),
            "summary":    a.summary[:200] if a.summary else "",
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        import pytz
        montreal = pytz.timezone("America/Montreal")
        df["published"] = pd.to_datetime(df["published"], utc=True).dt.tz_convert(montreal)
        df["date"] = df["published"].dt.date
    return df


@st.cache_data(ttl=300)
def load_counts(since_days: int = 7) -> dict[str, int]:
    container = get_container()
    since = datetime.now(timezone.utc) - timedelta(days=since_days)
    return container.repository.count_by_category(since=since)


@st.cache_data(ttl=300)
def load_trend_data(days: int = 7) -> pd.DataFrame:
    container = get_container()
    rows = container.repository.trend_data(days=days)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["date", "category", "count"])
    df["date"] = pd.to_datetime(df["date"])
    return df


@st.cache_data(ttl=300)
def load_sentiment_summary() -> pd.DataFrame:
    container = get_container()
    rows = container.repository.category_sentiment_summary()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows, columns=["category", "avg_sentiment", "count"])


# ── Sidebar navigation ───────────────────────────────────────────────────────

def sidebar() -> str:
    st.sidebar.image("https://flagcdn.com/w40/ca.png", width=40)
    st.sidebar.title("🌍 News Intelligence")
    page = st.sidebar.radio(
        "Navigate",
        [
            "📊 Executive Overview",
            "🔍 Category Explorer",
            "📈 Market & Policy Watchlist",
            "🔬 Model Quality & Monitoring",
        ],
    )
    st.sidebar.markdown("---")
    st.sidebar.caption("Auto-refreshes every 5 min  \nPipeline runs every 30 min")

    if st.sidebar.button("🔄 Refresh Data Now"):
        st.cache_data.clear()
        st.rerun()

    return page


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 – Executive Overview
# ══════════════════════════════════════════════════════════════════════════════

def page_executive_overview() -> None:
    st.title("📊 Executive Overview")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    days = st.slider("Time window (days)", 1, 30, 7, key="ov_days")

    df = load_articles(since_days=days, limit=2000)
    counts = load_counts(since_days=days)
    trend_df = load_trend_data(days=days)

    if df.empty:
        st.warning("No articles found. Run the pipeline first: `make run-pipeline`")
        return

    total = len(df)
    sources = df["source"].nunique()

    # ── KPI row ─────────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📰 Total Articles", f"{total:,}")
    col2.metric("📡 Sources", sources)
    col3.metric("😟 Negative Sentiment",
                f"{(df['sentiment'] == 'negative').mean():.0%}")
    col4.metric("📅 Days Covered", days)

    st.divider()

    # ── Articles by category (bar) ───────────────────────────────────────────
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Articles by Category")
        if counts:
            cat_df = pd.DataFrame(
                [(k, v) for k, v in counts.items()],
                columns=["Category", "Count"],
            ).sort_values("Count", ascending=True)
            fig = px.bar(
                cat_df, x="Count", y="Category", orientation="h",
                color="Category",
                color_discrete_map=CATEGORY_COLORS,
            )
            fig.update_layout(showlegend=False, height=350, margin=dict(l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("Sentiment Distribution")
        sent_df = df["sentiment"].value_counts().reset_index()
        sent_df.columns = ["Sentiment", "Count"]
        fig2 = px.pie(
            sent_df, values="Count", names="Sentiment",
            color="Sentiment",
            color_discrete_map=SENTIMENT_COLORS,
            hole=0.4,
        )
        fig2.update_layout(height=350, margin=dict(l=10, r=10))
        st.plotly_chart(fig2, use_container_width=True)

    # ── Trend lines ──────────────────────────────────────────────────────────
    st.subheader("Category Trend (articles/day)")
    if not trend_df.empty:
        fig3 = px.line(
            trend_df, x="date", y="count", color="category",
            color_discrete_map=CATEGORY_COLORS,
        )
        fig3.update_layout(height=300, margin=dict(l=10, r=10, t=10))
        st.plotly_chart(fig3, use_container_width=True)

    # ── Top sources ──────────────────────────────────────────────────────────
    col_src, col_top = st.columns(2)

    with col_src:
        st.subheader("Top Sources")
        src_df = df["source"].value_counts().head(10).reset_index()
        src_df.columns = ["Source", "Articles"]
        st.dataframe(src_df, hide_index=True, use_container_width=True)

    with col_top:
        st.subheader("Latest Headlines")
        top = df.nlargest(10, "published")[["title", "source", "category", "sentiment"]]
        for _, row in top.iterrows():
            colour = CATEGORY_COLORS.get(row["category"], "#95A5A6")
            st.markdown(
                f"<span style='color:{colour}'>●</span> **{row['title'][:100]}** "
                f"<small>({row['source']})</small>",
                unsafe_allow_html=True,
            )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 – Category Explorer
# ══════════════════════════════════════════════════════════════════════════════

def page_category_explorer() -> None:
    st.title("🔍 Category Explorer")

    col1, col2, col3, col4 = st.columns(4)
    all_categories = [c.value for c in NewsCategory if c != NewsCategory.UNKNOWN]

    with col1:
        selected_cat = st.selectbox("Category", ["All"] + all_categories)
    with col2:
        days = st.slider("Days back", 1, 30, 7, key="exp_days")
    with col3:
        container = get_container()
        sources = ["All"] + container.repository.distinct_sources()
        selected_src = st.selectbox("Source", sources)
    with col4:
        sentiment_filter = st.selectbox("Sentiment", ["All", "positive", "neutral", "negative"])

    cat_arg = selected_cat if selected_cat != "All" else None
    src_arg = selected_src if selected_src != "All" else None
    df = load_articles(category=cat_arg, since_days=days, source=src_arg, limit=500)

    if df.empty:
        st.info("No articles match the selected filters.")
        return

    if sentiment_filter != "All":
        df = df[df["sentiment"] == sentiment_filter]

    st.caption(f"Showing **{len(df)}** articles")

    # ── Sentiment by category ────────────────────────────────────────────────
    if cat_arg is None:
        sent_cat = df.groupby(["category", "sentiment"]).size().reset_index(name="count")
        fig = px.bar(
            sent_cat, x="category", y="count", color="sentiment",
            color_discrete_map=SENTIMENT_COLORS, barmode="stack",
        )
        fig.update_layout(height=280, margin=dict(l=10, r=10, t=10))
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Article table ────────────────────────────────────────────────────────
    display_cols = ["published", "title", "source", "category", "sentiment", "entities", "url"]
    available = [c for c in display_cols if c in df.columns]
    display_df = df[available].copy()
    display_df["title"] = display_df.apply(
        lambda r: f'<a href="{r["url"]}" target="_blank">{r["title"][:90]}</a>', axis=1
    )

    st.dataframe(
        display_df.drop(columns=["url"]),
        use_container_width=True,
        hide_index=True,
    )

    # ── Entity word cloud (top entities as tags) ─────────────────────────────
    st.subheader("Top Extracted Entities")
    all_entities = " ".join(df["entities"].dropna().tolist()).split(", ")
    entity_freq: dict[str, int] = {}
    for e in all_entities:
        e = e.strip()
        if e:
            entity_freq[e] = entity_freq.get(e, 0) + 1

    top_entities = sorted(entity_freq, key=lambda x: -entity_freq[x])[:30]
    if top_entities:
        tags_html = " ".join(
            f'<span style="background:#2C3E50;color:white;padding:3px 8px;'
            f'border-radius:12px;margin:2px;display:inline-block;font-size:0.8rem">'
            f'{e} ({entity_freq[e]})</span>'
            for e in top_entities
        )
        st.markdown(tags_html, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 – Market & Policy Watchlist
# ══════════════════════════════════════════════════════════════════════════════

_WATCHLIST_KEYWORDS: dict[str, list[str]] = {
    "🏦 Bank of Canada": ["bank of canada", "boc", "interest rate canada", "overnight rate"],
    "💵 US Federal Reserve": ["federal reserve", "fed rate", "fomc", "jerome powell"],
    "📊 Inflation": ["inflation", "cpi", "consumer price", "price index"],
    "🏠 Housing": ["housing market", "real estate", "mortgage rate", "home prices"],
    "🌐 Tariffs & Trade": ["tariff", "trade war", "trade deal", "wto", "import duty"],
    "🤖 AI Regulation": ["ai regulation", "ai act", "artificial intelligence law", "ai policy"],
    "🛢️ Oil Price": ["oil price", "crude oil", "opec", "brent", "wti"],
    "🇨🇦 Immigration (CA)": ["canada immigration", "ircc", "permanent resident", "express entry"],
}


def page_watchlist() -> None:
    st.title("📈 Market & Policy Watchlist")
    st.caption("Keyword-signal alerts – articles matching key policy/market topics")

    days = st.slider("Days back", 1, 14, 7, key="wl_days")
    df = load_articles(since_days=days, limit=2000)

    if df.empty:
        st.info("No data available.")
        return

    for signal_name, keywords in _WATCHLIST_KEYWORDS.items():
        pattern = "|".join(keywords)
        mask = (
            df["title"].str.lower().str.contains(pattern, regex=True, na=False)
            | df["summary"].str.lower().str.contains(pattern, regex=True, na=False)
        )
        matches = df[mask].copy()

        with st.expander(f"{signal_name}  ·  **{len(matches)} articles**", expanded=len(matches) > 0):
            if matches.empty:
                st.caption("No matching articles in the selected window.")
                continue

            # Sentiment distribution for this signal
            sent_counts = matches["sentiment"].value_counts()
            cols = st.columns(3)
            for i, s in enumerate(["positive", "neutral", "negative"]):
                cols[i].metric(
                    s.capitalize(),
                    sent_counts.get(s, 0),
                    delta=None,
                )

            for _, row in matches.nlargest(5, "published").iterrows():
                colour = SENTIMENT_COLORS.get(row["sentiment"], "#BDC3C7")
                st.markdown(
                    f"<span style='color:{colour}'>●</span> "
                    f"[{row['title'][:100]}]({row['url']})  "
                    f"<small>— {row['source']} · {row['published'].strftime('%b %d %H:%M')}</small>",
                    unsafe_allow_html=True,
                )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 – Model Quality & Monitoring
# ══════════════════════════════════════════════════════════════════════════════

def page_monitoring() -> None:
    st.title("🔬 Model Quality & Monitoring")

    df_all = load_articles(since_days=30, limit=5000)
    sent_summary = load_sentiment_summary()

    if df_all.empty:
        st.info("Not enough data for monitoring. Run the pipeline a few times first.")
        return

    # ── Model coverage ───────────────────────────────────────────────────────
    st.subheader("Classification Coverage")
    enriched_pct = (df_all["confidence"] > 0).mean()
    unknown_pct = (df_all["category"] == NewsCategory.UNKNOWN.value).mean()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Articles (30d)", f"{len(df_all):,}")
    col2.metric("Classified", f"{enriched_pct:.1%}")
    col3.metric("UNKNOWN category", f"{unknown_pct:.1%}")
    col4.metric("Avg Confidence", f"{df_all['confidence'].mean():.2f}")

    st.divider()

    # ── Confidence distribution ──────────────────────────────────────────────
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Confidence Score Distribution")
        fig = px.histogram(
            df_all[df_all["confidence"] > 0],
            x="confidence", nbins=20,
            color_discrete_sequence=["#3498DB"],
        )
        fig.update_layout(height=280, margin=dict(l=10, r=10, t=10))
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("Avg Sentiment by Category")
        if not sent_summary.empty:
            fig2 = px.bar(
                sent_summary,
                x="category",
                y="avg_sentiment",
                color="avg_sentiment",
                color_continuous_scale="RdYlGn",
                range_color=[-1, 1],
            )
            fig2.add_hline(y=0, line_dash="dot", line_color="grey")
            fig2.update_layout(height=280, margin=dict(l=10, r=10, t=10),
                                xaxis_tickangle=-25)
            st.plotly_chart(fig2, use_container_width=True)

    # ── Distribution drift check (daily category share) ─────────────────────
    st.subheader("Category Share – Daily Distribution Drift")
    st.caption(
        "Large swings may indicate drift in news coverage or classifier degradation."
    )
    trend_df = load_trend_data(days=14)
    if not trend_df.empty:
        pivot = trend_df.pivot_table(
            index="date", columns="category", values="count", fill_value=0
        )
        pivot_pct = pivot.div(pivot.sum(axis=1), axis=0)
        fig3 = px.area(
            pivot_pct.reset_index().melt(id_vars="date", var_name="category", value_name="share"),
            x="date", y="share", color="category",
            color_discrete_map=CATEGORY_COLORS,
        )
        fig3.update_layout(height=300, margin=dict(l=10, r=10, t=10))
        st.plotly_chart(fig3, use_container_width=True)

    # ── Retraining CTA ───────────────────────────────────────────────────────
    st.divider()
    st.subheader("Model Retraining")
    st.markdown(
        """
        The ML classifier is retrained using **weak labels** from the keyword baseline.
        Retrain when:
        - UNKNOWN% > 20%
        - Average confidence < 0.5
        - Category distribution looks unexpected

        Run: `make train-model`
        """
    )
    if st.button("🚀 Trigger Retraining Now"):
        with st.spinner("Training in progress..."):
            container = get_container()
            container.trainer.run()
        st.success("Model retrained and saved.")
        st.cache_data.clear()


# ══════════════════════════════════════════════════════════════════════════════
# Main routing
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    page = sidebar()

    if page == "📊 Executive Overview":
        page_executive_overview()
    elif page == "🔍 Category Explorer":
        page_category_explorer()
    elif page == "📈 Market & Policy Watchlist":
        page_watchlist()
    elif page == "🔬 Model Quality & Monitoring":
        page_monitoring()


if __name__ == "__main__":
    main()
