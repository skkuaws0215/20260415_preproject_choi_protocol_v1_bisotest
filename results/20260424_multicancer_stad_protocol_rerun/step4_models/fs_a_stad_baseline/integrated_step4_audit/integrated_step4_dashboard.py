#!/usr/bin/env python3
"""Integrated Step4 audit dashboard (Streamlit)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def main() -> None:
    base = Path(__file__).resolve().parent
    coverage = load_csv(base / "integrated_result_coverage.csv")
    flattened = load_csv(base / "integrated_metrics_flattened.csv")
    missing = load_csv(base / "integrated_missing_results.csv")
    leakage = load_csv(base / "integrated_leakage_warnings.csv")
    overfit = load_csv(base / "integrated_overfit_warnings.csv")
    best_eval = load_csv(base / "integrated_modality_best_by_eval.csv")
    robust = load_csv(base / "integrated_robust_model_ranking.csv")

    st.set_page_config(page_title="Integrated Step4 Audit Dashboard", layout="wide")
    st.title("Integrated Step4 Audit Dashboard")
    st.caption("ML near-full / DL full / Graph partial-full")
    st.info("Graph component is partial for LUAD due to missing LUAD 2-model graph evaluations.")

    if not coverage.empty:
        c1, c2, c3 = st.columns(3)
        cov = {row["modality"]: row for _, row in coverage.iterrows()}
        c1.metric("ML", f"{int(cov.get('ML', {}).get('completed', 0))}/{int(cov.get('ML', {}).get('expected', 0))}")
        c2.metric("DL", f"{int(cov.get('DL', {}).get('completed', 0))}/{int(cov.get('DL', {}).get('expected', 0))}")
        c3.metric("Graph", f"{int(cov.get('Graph', {}).get('completed', 0))}/{int(cov.get('Graph', {}).get('expected', 0))}")

    st.subheader("Coverage")
    if not coverage.empty:
        st.dataframe(coverage, use_container_width=True)
        chart_df = coverage.set_index("modality")[["expected", "completed", "missing"]]
        st.bar_chart(chart_df)
    else:
        st.warning("integrated_result_coverage.csv not found")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Flattened Metrics", "Missing", "Leakage/Overfit", "Best by Eval", "Robust Ranking"]
    )

    with tab1:
        st.write(f"Rows: {len(flattened)}")
        if not flattened.empty:
            modality = st.multiselect("Modality", sorted(flattened["modality"].dropna().unique().tolist()))
            cancer = st.multiselect("Cancer", sorted(flattened["cancer"].dropna().unique().tolist()))
            eval_mode = st.multiselect("Eval Mode", sorted(flattened["eval_mode"].dropna().unique().tolist()))
            view = flattened.copy()
            if modality:
                view = view[view["modality"].isin(modality)]
            if cancer:
                view = view[view["cancer"].isin(cancer)]
            if eval_mode:
                view = view[view["eval_mode"].isin(eval_mode)]
            st.dataframe(view, use_container_width=True, height=500)
        else:
            st.warning("integrated_metrics_flattened.csv not found")

    with tab2:
        st.write(f"Rows: {len(missing)}")
        if not missing.empty:
            st.dataframe(missing, use_container_width=True, height=500)
            grp = missing.groupby(["modality", "missing_category"], dropna=False).size().reset_index(name="count")
            st.dataframe(grp, use_container_width=True)
        else:
            st.success("No missing rows file found or empty.")

    with tab3:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Leakage Warnings**")
            st.write(f"Rows: {len(leakage)}")
            st.dataframe(leakage, use_container_width=True, height=300)
        with c2:
            st.markdown("**Overfit Warnings**")
            st.write(f"Rows: {len(overfit)}")
            st.dataframe(overfit, use_container_width=True, height=300)
            if not overfit.empty and "overfit_level" in overfit.columns:
                ov = overfit.groupby("overfit_level").size().rename("count")
                st.bar_chart(ov)

    with tab4:
        st.write(f"Rows: {len(best_eval)}")
        st.dataframe(best_eval, use_container_width=True, height=500)

    with tab5:
        st.write(f"Rows: {len(robust)}")
        st.dataframe(robust, use_container_width=True, height=500)
        if not robust.empty:
            topn = robust.head(10).set_index("model_key")[["robust_score"]]
            st.bar_chart(topn)

    st.markdown("---")
    st.caption("Step5 should proceed only based on integrated audit outputs.")


if __name__ == "__main__":
    main()
