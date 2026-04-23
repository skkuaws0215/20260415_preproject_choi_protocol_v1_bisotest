import streamlit as st
import json
from pathlib import Path


def render():
    """Step 9: LLM Explanations"""
    base_dir = Path(__file__).parent.parent.parent
    results_dir = base_dir / "results"

    st.header("📝 Step 9: LLM Drug Explanations")

    exp_path = results_dir / "colon_drug_explanations.json"
    if not exp_path.exists():
        st.warning("LLM explanations not found")
        return

    with open(exp_path) as f:
        explanations = json.load(f)

    st.info(f"Total: {len(explanations)} drug explanations (Ollama llama3.1)")

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
