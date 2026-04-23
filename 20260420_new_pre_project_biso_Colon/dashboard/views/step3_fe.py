"""
Step 3 Feature Engineering 뷰 — FE + FS 결과 시각화.
"""

import json
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from pathlib import Path


BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data"
FE_DIR = BASE_DIR / "fe_qc" / "20260420_colon_fe_v2"


def render_step3_fe():
    """Tab 3 메인 렌더"""

    # ─── Section 1: FE 개요 ───
    st.subheader("📊 Feature Engineering 개요")

    col1, col2, col3, col4 = st.columns(4)

    # X shape 로드
    x_path = DATA_DIR / "X_numeric.npy"
    if x_path.exists():
        X = np.load(x_path)
        with col1:
            st.metric("Samples", f"{X.shape[0]:,}")
        with col2:
            st.metric("Features (Phase 2A)", f"{X.shape[1]:,}")

    # features_slim
    slim_path = FE_DIR / "features_slim.parquet"
    if slim_path.exists():
        df_slim = pd.read_parquet(slim_path, columns=[])  # 메타만
        with col3:
            st.metric("FS 후 컬럼 수", f"{len(df_slim.columns) if hasattr(df_slim, 'columns') else 'N/A'}")

    with col4:
        st.metric("FE 버전", "v2 (20260420)")

    # ─── Section 2: Feature Categories ───
    st.subheader("🧬 Feature Categories")

    cat_path = FE_DIR / "feature_categories.json"
    if cat_path.exists():
        with open(cat_path) as f:
            categories = json.load(f)

        cat_df = pd.DataFrame([
            {"Category": k.replace("_cols", "").replace("_", " ").title(), "Count": len(v)}
            for k, v in categories.items()
        ]).sort_values("Count", ascending=False)

        col1, col2 = st.columns([1, 2])

        with col1:
            st.dataframe(cat_df, use_container_width=True, hide_index=True)
            st.metric("Total (before FS)", f"{cat_df['Count'].sum():,}")

        with col2:
            fig = px.bar(
                cat_df[cat_df["Count"] > 0],
                x="Category",
                y="Count",
                color="Category",
                title="Feature Count by Category",
            )
            fig.update_layout(showlegend=False, height=350)
            st.plotly_chart(fig, use_container_width=True)

    # ─── Section 3: Feature Selection 과정 ───
    st.subheader("✂️ Feature Selection")

    log_path = FE_DIR / "feature_selection_log.json"
    if log_path.exists():
        with open(log_path) as f:
            fs_log = json.load(f)

        # 초기 → 최종 비교
        if isinstance(fs_log, dict):
            col1, col2, col3 = st.columns(3)

            initial = fs_log.get("initial_shape", {})
            final = fs_log.get("final_counts", {})
            thresholds = fs_log.get("thresholds", {})

            if isinstance(initial, dict):
                total_before = sum(initial.values()) if initial else 0
            elif isinstance(initial, (list, tuple)) and len(initial) >= 2:
                total_before = initial[1]
            else:
                total_before = 0

            total_after = sum(final.values()) if isinstance(final, dict) else 0
            removed = total_before - total_after

            with col1:
                st.metric("Before FS", f"{total_before:,}")
            with col2:
                st.metric("After FS", f"{total_after:,}")
            with col3:
                pct = (removed / total_before * 100) if total_before > 0 else 0
                st.metric("Removed", f"{removed:,}", f"-{pct:.1f}%")

            # Thresholds
            if thresholds:
                st.caption(f"Variance threshold: {thresholds.get('variance', 'N/A')} | "
                           f"Correlation threshold: {thresholds.get('correlation', 'N/A')}")

            # Steps 상세
            steps = fs_log.get("steps", [])
            if steps:
                with st.expander(f"FS 단계별 상세 ({len(steps)} steps)", expanded=False):
                    for i, step in enumerate(steps, 1):
                        if isinstance(step, dict):
                            st.markdown(f"**Step {i}**: {step.get('description', step.get('category', 'unknown'))}")
                            st.text(f"  Before: {step.get('before', '?')} → After: {step.get('after', '?')} "
                                    f"(removed: {step.get('removed', '?')})")

            # 전체 로그
            with st.expander("전체 FS 로그 (JSON)", expanded=False):
                st.json(fs_log)

    # ─── Section 4: Phase 별 입력 비교 ───
    st.subheader("📊 Phase 별 입력 크기")

    phase_data = []
    for name, label in [
        ("X_numeric.npy", "Phase 2A (numeric)"),
        ("X_numeric_smiles.npy", "Phase 2B (+SMILES)"),
        ("X_numeric_context_smiles.npy", "Phase 2C (+context+SMILES)"),
    ]:
        fpath = DATA_DIR / name
        if fpath.exists():
            arr = np.load(fpath)
            phase_data.append({
                "Phase": label,
                "Samples": arr.shape[0],
                "Features": arr.shape[1],
                "Size (MB)": f"{fpath.stat().st_size / 1024 / 1024:.1f}",
            })

    if phase_data:
        df_phase = pd.DataFrame(phase_data)
        st.dataframe(df_phase, use_container_width=True, hide_index=True)

        # Feature 증가 시각화
        fig = px.bar(
            df_phase,
            x="Phase",
            y="Features",
            text="Features",
            title="Features by Phase",
            color_discrete_sequence=["#7B68EE"],
        )
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)
