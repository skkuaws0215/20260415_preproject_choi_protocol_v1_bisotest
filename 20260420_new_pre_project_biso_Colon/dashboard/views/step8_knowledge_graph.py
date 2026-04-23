import streamlit as st
import json
from pathlib import Path


def render():
    """Step 8: Knowledge Graph"""
    base_dir = Path(__file__).parent.parent.parent
    results_dir = base_dir / "results"

    st.header("🕸️ Step 8: Knowledge Graph")

    # Neo4j 요약
    neo4j_path = results_dir / "colon_neo4j_load_summary.json"
    if neo4j_path.exists():
        with open(neo4j_path) as f:
            neo4j = json.load(f)

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Nodes", neo4j.get("total_nodes", "?"))
        col2.metric("Diseases", 3)
        col3.metric("Cross-Disease Drugs", len(neo4j.get("enhancements", {}).get("cross_disease_shared_drugs", [])))

        # 질병별 연결
        final_state = neo4j.get("final_state", {})
        if final_state:
            st.markdown("#### Disease Connections")
            for disease, rels in final_state.items():
                st.write(f"**{disease}**: {', '.join(f'{k} {v}' for k, v in rels.items())}")

        # 공유 약물
        shared = neo4j.get("enhancements", {}).get("cross_disease_shared_drugs", [])
        if shared:
            st.success(f"🔄 Cross-Disease Drugs: {', '.join(shared)}")

    # KG 뷰어 임베드
    viewer_path = results_dir / "knowledge_graph_viewer.html"
    if viewer_path.exists():
        st.markdown("#### 🕸️ Interactive Network")
        with open(viewer_path, "r") as f:
            html_content = f.read()
        st.components.v1.html(html_content, height=750, scrolling=False)
    else:
        st.warning("Knowledge graph viewer not found")
