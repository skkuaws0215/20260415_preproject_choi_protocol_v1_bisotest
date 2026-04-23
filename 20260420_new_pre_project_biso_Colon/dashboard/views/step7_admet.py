import streamlit as st
import pandas as pd
import json
from pathlib import Path


def render():
    """Step 7: ADMET + AlphaFold + COAD/READ"""
    base_dir = Path(__file__).parent.parent.parent
    results_dir = base_dir / "results"

    st.header("💊 Step 7: ADMET Gate + AlphaFold + COAD/READ")

    tab1, tab2, tab3 = st.tabs(["ADMET & Top 15", "AlphaFold 3D", "COAD vs READ"])

    # ─── ADMET ───
    with tab1:
        st.subheader("ADMET Gate (Choi Protocol — 22 Assays)")

        admet_path = results_dir / "colon_admet_summary.json"
        if admet_path.exists():
            with open(admet_path) as f:
                admet = json.load(f)

            col1, col2, col3, col4 = st.columns(4)
            vc = admet.get("verdict_counts", {})
            col1.metric("PASS", vc.get("PASS", 0))
            col2.metric("WARNING", vc.get("WARNING", 0))
            col3.metric("FAIL", vc.get("FAIL", 0))
            col4.metric("Avg Safety", f"{admet.get('avg_safety_score', 0):.2f}")

        st.markdown("---")
        st.subheader("🏆 Final Top 15")

        top15_path = results_dir / "colon_final_top15.csv"
        if top15_path.exists():
            top15 = pd.read_csv(top15_path)
            name_col = "drug_name" if "drug_name" in top15.columns else "DRUG_NAME"
            cat_col = "usage_category" if "usage_category" in top15.columns else "category"

            if cat_col in top15.columns:
                cat_counts = top15[cat_col].value_counts()
                for cat, cnt in cat_counts.items():
                    icon = {"FDA_APPROVED_CRC": "✅", "REPURPOSING_CANDIDATE": "🎯", "CLINICAL_TRIAL": "🔬", "RESEARCH_PHASE": "📝"}.get(cat, "")
                    st.write(f"{icon} **{cat}**: {cnt}")

            display_cols = [c for c in ["recommendation_rank", name_col, cat_col, "target", "safety_score", "verdict"] if c in top15.columns]
            st.dataframe(top15[display_cols], use_container_width=True)

    # ─── AlphaFold ───
    with tab2:
        st.subheader("AlphaFold Structure Validation")

        af_path = results_dir / "alphafold_validation" / "alphafold_validation_results.json"
        if af_path.exists():
            with open(af_path) as f:
                af = json.load(f)

            summary = af.get("summary", {})
            col1, col2, col3 = st.columns(3)
            col1.metric("Structures", af.get("structures_downloaded", 0))
            col2.metric("Avg pLDDT", summary.get("avg_plddt", 0))
            col3.metric("Pockets", summary.get("targets_with_pocket", 0))

            structures = af.get("structures", [])
            if structures:
                rows = []
                for s in structures:
                    plddt = s.get("plddt", {})
                    pocket = s.get("pocket", {})
                    rows.append({
                        "Gene": s["gene"], "UniProt": s["uniprot_id"],
                        "Drug(s)": ", ".join(s.get("drugs", [])[:2]),
                        "pLDDT": plddt.get("mean", 0) if plddt else 0,
                        "Pocket": pocket.get("n_residues", 0) if pocket else 0,
                        "Volume": pocket.get("volume", 0) if pocket else 0,
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True)

            viewer_path = results_dir / "alphafold_validation" / "alphafold_3d_viewer.html"
            if viewer_path.exists():
                st.markdown("#### 🔬 3D Protein Viewer")
                with open(viewer_path, "r") as f:
                    html_content = f.read()
                st.components.v1.html(html_content, height=700, scrolling=True)

    # ─── COAD/READ ───
    with tab3:
        st.subheader("COAD vs READ Differential Analysis")

        cr_path = results_dir / "colon_coad_read_analysis.json"
        if cr_path.exists():
            with open(cr_path) as f:
                cr = json.load(f)

            samples = cr.get("tcga_samples", {})
            col1, col2 = st.columns(2)
            col1.metric("COAD Samples", samples.get("coad", 0))
            col2.metric("READ Samples", samples.get("read", 0))

            summary = cr.get("summary", {})
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("COAD preferred", summary.get("coad_preferred", 0))
            col2.metric("READ preferred", summary.get("read_preferred", 0))
            col3.metric("Both", summary.get("both", 0))
            col4.metric("Unknown", summary.get("unknown", 0))

            recs = cr.get("drug_recommendations", [])
            if recs:
                st.dataframe(pd.DataFrame(recs), use_container_width=True)
