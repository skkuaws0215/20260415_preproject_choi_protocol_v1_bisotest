"""
Step 5 Ensemble 뷰 — OOF-based weighted average 결과 시각화.
"""

import json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path


ENSEMBLE_DIR = Path(__file__).parent.parent.parent / "results" / "ensemble_20260422"


def load_ensemble_results():
    """ensemble_results.json 로드"""
    json_path = ENSEMBLE_DIR / "ensemble_results.json"
    if not json_path.exists():
        return None
    with open(json_path) as f:
        return json.load(f)


def render_step5_ensemble():
    """Tab 5 메인 렌더 함수"""
    data = load_ensemble_results()

    if data is None:
        st.warning("앙상블 결과가 없습니다. `scripts/run_ensemble.py` 를 실행해주세요.")
        return

    # ─── Section 1: Summary ───
    st.subheader("📊 Ensemble Summary")

    ranking = data["final_ranking"]
    best = ranking[0]
    single_best = data["tier3_single_best"]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🏆 Best Ensemble", f"{best['score']:.4f}", f"#{best['rank']} {best['name']}")
    with col2:
        st.metric("Best Single", f"{single_best['score']:.4f}", single_best['model'].split('_')[-1])
    with col3:
        gain = best['score'] - single_best['score']
        st.metric("Ensemble Gain", f"+{gain:.4f}", f"+{gain/single_best['score']*100:.1f}%")
    with col4:
        st.metric("Total Combinations", str(len(ranking)), f"{data['n_oof_files']} OOF files")

    # ─── Section 2: Final Ranking ───
    st.subheader("🏅 Final Ranking")

    df_ranking = pd.DataFrame(ranking)
    df_ranking["score"] = df_ranking["score"].apply(lambda x: f"{x:.4f}")

    # 메달 아이콘
    def format_rank(r):
        if r == 1:
            return "🥇"
        elif r == 2:
            return "🥈"
        elif r == 3:
            return "🥉"
        return str(r)

    df_ranking["#"] = df_ranking["rank"].apply(format_rank)
    df_ranking = df_ranking[["#", "name", "score"]]
    df_ranking.columns = ["#", "Combination", "Spearman"]

    st.dataframe(
        df_ranking,
        use_container_width=True,
        hide_index=True,
        height=min(len(df_ranking) * 38 + 38, 500),
    )

    # ─── Section 3: Ranking Bar Chart ───
    st.subheader("📊 Ensemble Comparison")

    df_chart = pd.DataFrame(ranking)
    df_chart["tier"] = df_chart["name"].apply(
        lambda x: "Tier1" if x.startswith("Tier1_") else
                  "Tier1B" if x.startswith("Tier1B") else
                  "Tier2" if x.startswith("Tier2") else "Single"
    )

    fig = px.bar(
        df_chart,
        x="name",
        y="score",
        color="tier",
        color_discrete_map={
            "Tier1": "#2196F3",
            "Tier1B": "#4CAF50",
            "Tier2": "#FF9800",
            "Single": "#9E9E9E",
        },
        title="Ensemble Spearman by Combination",
        labels={"name": "Combination", "score": "Spearman", "tier": "Tier"},
    )
    fig.update_layout(
        xaxis_tickangle=-45,
        height=400,
        showlegend=True,
    )
    # 단일 best 기준선
    fig.add_hline(
        y=single_best["score"],
        line_dash="dash",
        line_color="red",
        annotation_text=f"Single Best: {single_best['score']:.4f}",
    )
    st.plotly_chart(fig, use_container_width=True)

    # ─── Section 4: Tier 1 상세 (Cross-Category) ───
    st.subheader("🔬 Tier 1: Cross-Category Detail")

    tier1 = data.get("tier1_cross_category", [])
    if tier1:
        for r in tier1:
            with st.expander(f"{r['phase']} {r['variant']} — Ensemble: {r['ensemble_spearman']:.4f}"):
                cols = st.columns(3)
                labels = ["ML", "DL", "Graph"]
                for i, (model, weight, score) in enumerate(
                    zip(r["models"], r["weights"], r["individual_scores"])
                ):
                    with cols[i]:
                        model_short = model.split("_")[-1]
                        st.metric(
                            f"{labels[i]}: {model_short}",
                            f"{score:.4f}",
                            f"w={weight:.2f}",
                        )

    # ─── Section 5: Tier 1B (Mixed Variant) ───
    tier1b = data.get("tier1b_mixed_variant", [])
    if tier1b:
        st.subheader("🔀 Tier 1B: Mixed Variant Detail")
        for r in tier1b:
            with st.expander(f"{r['phase']} mixed — Ensemble: {r['ensemble_spearman']:.4f}"):
                cols = st.columns(3)
                labels = ["ML(base)", "DL(base)", "Graph(fsimp)"]
                for i, (model, weight, score) in enumerate(
                    zip(r["models"], r["weights"], r["individual_scores"])
                ):
                    with cols[i]:
                        model_short = model.split("_")[-1]
                        st.metric(
                            f"{labels[i]}: {model_short}",
                            f"{score:.4f}",
                            f"w={weight:.2f}",
                        )

    # ─── Section 6: Progress Summary ───
    st.subheader("📈 Pipeline Progress")

    st.markdown(f"""
    | Step | Status | Best Score |
    |------|--------|-----------|
    | Step 4 Baseline | ✅ 완료 | CatBoost 2B = 0.4881 |
    | Step 4.5 FS | ✅ 완료 | GraphSAGE FSimp 2B = {single_best['score']:.4f} |
    | Step 5 Ensemble | ✅ 완료 | **{best['name']} = {best['score']:.4f}** |
    | Step 6 Validation | ⬜ 대기 | - |
    """)
