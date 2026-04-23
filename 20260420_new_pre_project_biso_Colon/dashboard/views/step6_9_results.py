import streamlit as st
import pandas as pd
import json
from pathlib import Path


def render():
    """Step 6-9 통합 결과 뷰"""
    base_dir = Path(__file__).parent.parent.parent
    results_dir = base_dir / "results"

    st.header("✅ Step 6-9: Validation, ADMET, AlphaFold & LLM Results")

    # ─── Tab 구성 ───
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 External Validation",
        "💊 ADMET & Top 15",
        "🔬 AlphaFold",
        "🧬 COAD vs READ",
        "📝 LLM Explanations",
    ])

    # ═══ Tab 1: External Validation ═══
    with tab1:
        st.subheader("Step 6: External Validation (5 Sources)")

        comp_path = results_dir / "colon_comprehensive_drug_scores.csv"
        if comp_path.exists():
            comp = pd.read_csv(comp_path)

            # 소스별 Hit Rate
            col1, col2, col3, col4, col5 = st.columns(5)
            sources = [
                ("PRISM", "prism", col1),
                ("ClinicalTrials", "clinical_trials", col2),
                ("COSMIC", "cosmic", col3),
                ("CPTAC", "cptac", col4),
                ("GEO", "geo", col5),
            ]
            for label, col_name, col_widget in sources:
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
                    st.success(f"🏆 5/5 Very High Confidence: {', '.join(very_high['drug_name'].tolist())}")

            # 전체 테이블
            st.markdown("#### All Drug Validation Scores")
            display_cols = ["rank", "drug_name", "prism", "clinical_trials", "cosmic", "cptac", "geo", "validation_count", "confidence"]
            display_cols = [c for c in display_cols if c in comp.columns]
            st.dataframe(comp[display_cols], use_container_width=True)
        else:
            st.warning("Comprehensive validation results not found")

    # ═══ Tab 2: ADMET & Top 15 ═══
    with tab2:
        st.subheader("Step 7: ADMET Gate (Choi Protocol — 22 Assays)")

        # ADMET 요약
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

            st.info(f"Method: {admet.get('method', '22 ADMET assays + Tanimoto matching')}")

        # Top 15
        st.markdown("---")
        st.subheader("🏆 Final Top 15 Drug Candidates")

        top15_path = results_dir / "colon_final_top15.csv"
        if top15_path.exists():
            top15 = pd.read_csv(top15_path)
            name_col = "drug_name" if "drug_name" in top15.columns else "DRUG_NAME"

            # 카테고리 분포
            cat_col = "usage_category" if "usage_category" in top15.columns else "category"
            if cat_col in top15.columns:
                st.markdown("#### Category Distribution")
                cat_counts = top15[cat_col].value_counts()
                for cat, cnt in cat_counts.items():
                    icon = {"FDA_APPROVED_CRC": "✅", "REPURPOSING_CANDIDATE": "🎯",
                            "CLINICAL_TRIAL": "🔬", "RESEARCH_PHASE": "📝"}.get(cat, "")
                    st.write(f"{icon} **{cat}**: {cnt}")

            # Top 15 테이블
            display_cols = ["recommendation_rank", name_col, cat_col, "target", "safety_score", "verdict"]
            display_cols = [c for c in display_cols if c in top15.columns]
            st.dataframe(top15[display_cols], use_container_width=True)
        else:
            st.warning("Top 15 results not found")

    # ═══ Tab 3: AlphaFold ═══
    with tab3:
        st.subheader("Step 7.5: AlphaFold Structure Validation")

        af_path = results_dir / "alphafold_validation" / "alphafold_validation_results.json"
        if af_path.exists():
            with open(af_path) as f:
                af = json.load(f)

            summary = af.get("summary", {})
            col1, col2, col3 = st.columns(3)
            col1.metric("Structures", af.get("structures_downloaded", 0))
            col2.metric("Avg pLDDT", summary.get("avg_plddt", 0))
            col3.metric("Pockets Detected", summary.get("targets_with_pocket", 0))

            # 구조 테이블
            structures = af.get("structures", [])
            if structures:
                rows = []
                for s in structures:
                    plddt = s.get("plddt", {})
                    pocket = s.get("pocket", {})
                    rows.append({
                        "Gene": s["gene"],
                        "UniProt": s["uniprot_id"],
                        "Drug(s)": ", ".join(s.get("drugs", [])[:2]),
                        "pLDDT": plddt.get("mean", 0) if plddt else 0,
                        "Pocket Size": pocket.get("n_residues", 0) if pocket else 0,
                        "Pocket Volume": pocket.get("volume", 0) if pocket else 0,
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True)

            # 3D 뷰어 임베드
            viewer_path = results_dir / "alphafold_validation" / "alphafold_3d_viewer.html"
            if viewer_path.exists():
                st.markdown("#### 🔬 Interactive 3D Protein Viewer")
                with open(viewer_path, "r") as f:
                    html_content = f.read()
                st.components.v1.html(html_content, height=700, scrolling=True)
        else:
            st.warning("AlphaFold validation results not found")

    # ═══ Tab 4: COAD vs READ ═══
    with tab4:
        st.subheader("Step 7.6: COAD vs READ Differential Analysis")

        cr_path = results_dir / "colon_coad_read_analysis.json"
        if cr_path.exists():
            with open(cr_path) as f:
                cr = json.load(f)

            # 샘플 수
            samples = cr.get("tcga_samples", {})
            col1, col2 = st.columns(2)
            col1.metric("COAD Samples", samples.get("coad", 0))
            col2.metric("READ Samples", samples.get("read", 0))

            # 추천 분포
            summary = cr.get("summary", {})
            st.markdown("#### Drug Recommendations")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("🔵 COAD preferred", summary.get("coad_preferred", 0))
            col2.metric("🔴 READ preferred", summary.get("read_preferred", 0))
            col3.metric("🟢 Both", summary.get("both", 0))
            col4.metric("⚪ Unknown", summary.get("unknown", 0))

            # 유전자별 발현 차이
            expr_results = cr.get("expression_results", [])
            if expr_results:
                st.markdown("#### Target Gene Expression (COAD vs READ)")
                expr_df = pd.DataFrame(expr_results)
                display_cols = ["gene", "coad_mean", "read_mean", "p_value", "cohens_d", "direction"]
                display_cols = [c for c in display_cols if c in expr_df.columns]
                st.dataframe(expr_df[display_cols], use_container_width=True)

            # 약물별 추천
            recs = cr.get("drug_recommendations", [])
            if recs:
                st.markdown("#### Per-Drug Recommendations")
                rec_df = pd.DataFrame(recs)
                st.dataframe(rec_df, use_container_width=True)
        else:
            st.warning("COAD vs READ analysis not found")

    # ═══ Tab 5: LLM Explanations ═══
    with tab5:
        st.subheader("Step 9: LLM Drug Explanations")

        exp_path = results_dir / "colon_drug_explanations.json"
        if exp_path.exists():
            with open(exp_path) as f:
                explanations = json.load(f)

            st.info(f"Total: {len(explanations)} drug explanations (Ollama llama3.1)")

            # 약물 선택
            drug_names = [e["drug_name"] for e in explanations]
            selected = st.selectbox("Select Drug", drug_names)

            for exp in explanations:
                if exp["drug_name"] == selected:
                    cat_icon = {"FDA_APPROVED_CRC": "✅", "REPURPOSING_CANDIDATE": "🎯",
                                "CLINICAL_TRIAL": "🔬", "RESEARCH_PHASE": "📝"}.get(exp["category"], "")

                    col1, col2, col3 = st.columns(3)
                    col1.metric("Category", f"{cat_icon} {exp['category']}")
                    col2.metric("Safety Score", exp["safety_score"])
                    col3.metric("Validation", f"{exp['validation_count']}/5")

                    st.markdown(f"**Target**: {exp['target']}")
                    st.markdown(f"**COAD/READ**: {exp.get('coad_read', 'N/A')}")

                    st.markdown("---")
                    st.markdown("### Explanation")
                    st.markdown(exp["explanation"])
                    break
        else:
            st.warning("LLM explanations not found")
