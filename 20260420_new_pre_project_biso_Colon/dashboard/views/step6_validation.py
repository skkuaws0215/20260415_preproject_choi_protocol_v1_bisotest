import streamlit as st
import pandas as pd
import json
from pathlib import Path


def render():
    """Step 6: External Validation"""
    base_dir = Path(__file__).parent.parent.parent
    results_dir = base_dir / "results"

    st.header("✅ Step 6: External Validation (5 Sources)")

    comp_path = results_dir / "colon_comprehensive_drug_scores.csv"
    if not comp_path.exists():
        st.warning("Comprehensive validation results not found")
        return

    comp = pd.read_csv(comp_path)

    # 소스별 Hit Rate
    col1, col2, col3, col4, col5 = st.columns(5)
    for label, col_name, col_widget in [
        ("PRISM", "prism", col1), ("ClinicalTrials", "clinical_trials", col2),
        ("COSMIC", "cosmic", col3), ("CPTAC", "cptac", col4), ("GEO", "geo", col5),
    ]:
        if col_name in comp.columns:
            rate = comp[col_name].mean() * 100
            col_widget.metric(label, f"{rate:.1f}%")

    # 신뢰도 분포
    st.markdown("#### Confidence Distribution")
    if "confidence" in comp.columns:
        conf_counts = comp["confidence"].value_counts()
        st.bar_chart(conf_counts)

    # Very High 약물
    if "validation_count" in comp.columns:
        very_high = comp[comp["validation_count"] >= 5]
        if len(very_high) > 0:
            st.success(f"🏆 5/5 Very High: {', '.join(very_high['drug_name'].tolist())}")

    # 전체 테이블
    st.markdown("#### All Drug Validation Scores")
    display_cols = [c for c in ["rank", "drug_name", "prism", "clinical_trials", "cosmic", "cptac", "geo", "validation_count", "confidence"] if c in comp.columns]
    st.dataframe(comp[display_cols], use_container_width=True)
