#!/usr/bin/env python3
"""
Step 8: Knowledge Graph 인터랙티브 뷰어 생성

Neo4j 에서 추출한 그래프 데이터를 vis.js 기반 인터랙티브 HTML 로 변환.

입력:
  - results/knowledge_graph_data.json

출력:
  - results/knowledge_graph_viewer.html
"""

import json
from pathlib import Path


def generate_kg_viewer(data_path, output_path):
    """vis.js 기반 Knowledge Graph 뷰어 생성"""

    with open(data_path) as f:
        graph = json.load(f)

    nodes = graph["nodes"]
    edges = graph["edges"]

    # 노드 타입별 색상/모양
    type_config = {
        "disease": {"color": "#e74c3c", "shape": "diamond", "size": 40, "font_size": 18},
        "drug": {"color": "#3498db", "shape": "dot", "size": 20, "font_size": 12},
        "target": {"color": "#2ecc71", "shape": "triangle", "size": 18, "font_size": 11},
        "pathway": {"color": "#9b59b6", "shape": "square", "size": 15, "font_size": 10},
    }

    # 카테고리별 drug 색상
    drug_colors = {
        "FDA_APPROVED_CRC": "#e74c3c",
        "REPURPOSING_CANDIDATE": "#f39c12",
        "CLINICAL_TRIAL": "#1abc9c",
        "RESEARCH_PHASE": "#3498db",
    }

    # 관계 타입별 색상
    edge_colors = {
        "treats": "#e74c3c",
        "predicted_for": "#f39c12",
        "targets": "#2ecc71",
        "associated_with": "#95a5a6",
        "in_pathway": "#9b59b6",
    }

    # vis.js 노드 데이터 생성
    vis_nodes = []
    for n in nodes:
        ntype = n["type"]
        config = type_config.get(ntype, type_config["drug"])

        color = config["color"]
        if ntype == "drug" and n.get("category"):
            color = drug_colors.get(n["category"], config["color"])

        title_parts = [f"<b>{n['label']}</b>", f"Type: {ntype}"]
        if n.get("category"):
            title_parts.append(f"Category: {n['category']}")
        if n.get("safety_score"):
            title_parts.append(f"Safety: {n['safety_score']}")
        if n.get("uniprot"):
            title_parts.append(f"UniProt: {n['uniprot']}")
        if n.get("plddt"):
            title_parts.append(f"pLDDT: {n['plddt']}")
        if n.get("pocket"):
            title_parts.append(f"Pocket: {n['pocket']} res")

        vis_nodes.append({
            "id": n["id"],
            "label": n["label"],
            "shape": config["shape"],
            "size": config["size"],
            "color": {"background": color, "border": color, "highlight": {"background": "#f1c40f", "border": "#f39c12"}},
            "font": {"size": config["font_size"], "color": "#2c3e50"},
            "title": "<br>".join(title_parts),
            "group": ntype,
        })

    # vis.js 엣지 데이터 생성
    vis_edges = []
    for e in edges:
        etype = e["type"]
        color = edge_colors.get(etype, "#bdc3c7")

        title_parts = [f"Type: {etype}"]
        if e.get("rank"):
            title_parts.append(f"Rank: {e['rank']}")
        if e.get("confidence"):
            title_parts.append(f"Confidence: {e['confidence']}")

        vis_edges.append({
            "from": e["source"],
            "to": e["target"],
            "color": {"color": color, "highlight": "#f39c12"},
            "title": "<br>".join(title_parts),
            "arrows": "to",
            "width": 2 if etype in ["treats", "targets"] else 1,
            "dashes": etype == "predicted_for",
        })

    nodes_json = json.dumps(vis_nodes)
    edges_json = json.dumps(vis_edges)

    # 통계
    stats = {
        "nodes": len(nodes),
        "edges": len(edges),
        "diseases": len([n for n in nodes if n["type"] == "disease"]),
        "drugs": len([n for n in nodes if n["type"] == "drug"]),
        "targets": len([n for n in nodes if n["type"] == "target"]),
        "pathways": len([n for n in nodes if n["type"] == "pathway"]),
    }

    # 질병별 약물 분류
    disease_drugs = {}
    for e in edges:
        if e["type"] in ["treats", "predicted_for"]:
            disease_id = e["target"]
            drug_id = e["source"]
            disease_name = next((n["label"] for n in nodes if n["id"] == disease_id), "?")
            drug_name = next((n["label"] for n in nodes if n["id"] == drug_id), "?")
            if disease_name not in disease_drugs:
                disease_drugs[disease_name] = []
            disease_drugs[disease_name].append(drug_name)

    # 공유 약물
    all_drug_names = set()
    for drugs in disease_drugs.values():
        all_drug_names.update(drugs)
    shared = []
    for drug in all_drug_names:
        in_diseases = [d for d, drugs in disease_drugs.items() if drug in drugs]
        if len(in_diseases) > 1:
            shared.append({"drug": drug, "diseases": in_diseases})

    # 필터 옵션
    filter_options = ""
    for disease in disease_drugs:
        filter_options += f'<option value="{disease}">{disease}</option>\n'

    # 공유 약물 테이블
    shared_rows = ""
    for s in sorted(shared, key=lambda x: len(x["diseases"]), reverse=True):
        shared_rows += f'<tr><td>{s["drug"]}</td><td>{", ".join(s["diseases"])}</td><td>{len(s["diseases"])}</td></tr>\n'

    html = f"""<!DOCTYPE html>
<html>
<head>
<title>Knowledge Graph — Drug Repurposing Network</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.6/vis-network.min.js"></script>
<link href="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.6/vis-network.min.css" rel="stylesheet">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0a0a1a; color: #e0e0e0; }}

.header {{
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    padding: 20px 30px;
    border-bottom: 2px solid #e74c3c;
}}
.header h1 {{ color: #fff; font-size: 24px; }}
.header p {{ color: #95a5a6; font-size: 14px; margin-top: 5px; }}

.main-container {{ display: flex; height: calc(100vh - 80px); }}

.sidebar {{
    width: 320px;
    background: #1a1a2e;
    padding: 20px;
    overflow-y: auto;
    border-right: 1px solid #2c3e50;
}}

.graph-container {{
    flex: 1;
    position: relative;
}}

#network {{ width: 100%; height: 100%; }}

.control-section {{
    margin-bottom: 20px;
    padding: 15px;
    background: #16213e;
    border-radius: 8px;
    border: 1px solid #2c3e50;
}}
.control-section h3 {{
    color: #3498db;
    font-size: 14px;
    margin-bottom: 10px;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

.stat-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
}}
.stat-item {{
    background: #0a0a1a;
    padding: 10px;
    border-radius: 6px;
    text-align: center;
}}
.stat-value {{ font-size: 20px; font-weight: bold; }}
.stat-label {{ font-size: 11px; color: #7f8c8d; margin-top: 3px; }}

.legend-item {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 5px 0;
    font-size: 13px;
}}
.legend-dot {{
    width: 14px;
    height: 14px;
    border-radius: 50%;
    flex-shrink: 0;
}}
.legend-diamond {{
    width: 14px;
    height: 14px;
    transform: rotate(45deg);
    flex-shrink: 0;
}}
.legend-triangle {{
    width: 0;
    height: 0;
    border-left: 7px solid transparent;
    border-right: 7px solid transparent;
    border-bottom: 14px solid;
    flex-shrink: 0;
}}
.legend-line {{
    width: 20px;
    height: 3px;
    flex-shrink: 0;
}}

select, input {{
    width: 100%;
    padding: 8px;
    margin: 5px 0;
    background: #0a0a1a;
    color: #e0e0e0;
    border: 1px solid #2c3e50;
    border-radius: 4px;
    font-size: 13px;
}}
button {{
    padding: 8px 15px;
    margin: 3px;
    background: #3498db;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
}}
button:hover {{ background: #2980b9; }}
button.active {{ background: #e74c3c; }}

.node-detail {{
    padding: 15px;
    background: #16213e;
    border-radius: 8px;
    border: 1px solid #2c3e50;
    margin-top: 10px;
}}
.node-detail h4 {{ color: #f39c12; margin-bottom: 8px; }}
.node-detail p {{ font-size: 12px; margin: 3px 0; }}

table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 10px;
    font-size: 12px;
}}
th {{ background: #2c3e50; padding: 6px; text-align: left; }}
td {{ padding: 6px; border-bottom: 1px solid #2c3e50; }}

.edge-legend {{ margin-top: 10px; }}
.edge-legend-item {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 4px 0;
    font-size: 12px;
}}
</style>
</head>
<body>

<div class="header">
    <h1>🔬 Drug Repurposing Knowledge Graph</h1>
    <p>BRCA · Lung · Colorectal Cancer — Interactive Network Viewer</p>
</div>

<div class="main-container">
    <div class="sidebar">
        <!-- Stats -->
        <div class="control-section">
            <h3>📊 Graph Statistics</h3>
            <div class="stat-grid">
                <div class="stat-item">
                    <div class="stat-value" style="color:#e74c3c">{stats['diseases']}</div>
                    <div class="stat-label">Diseases</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" style="color:#3498db">{stats['drugs']}</div>
                    <div class="stat-label">Drugs</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" style="color:#2ecc71">{stats['targets']}</div>
                    <div class="stat-label">Targets</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" style="color:#fff">{stats['edges']}</div>
                    <div class="stat-label">Edges</div>
                </div>
            </div>
        </div>

        <!-- Controls -->
        <div class="control-section">
            <h3>🎛 Controls</h3>
            <label>Disease Filter</label>
            <select id="diseaseFilter" onchange="filterByDisease()">
                <option value="all">All Diseases</option>
                {filter_options}
            </select>
            <label>Search Node</label>
            <input id="searchInput" placeholder="Type drug/target name..." oninput="searchNode()">
            <div style="margin-top:10px">
                <button onclick="resetView()">Reset View</button>
                <button onclick="togglePhysics()">Toggle Physics</button>
            </div>
        </div>

        <!-- Legend: Nodes -->
        <div class="control-section">
            <h3>🔵 Node Types</h3>
            <div class="legend-item"><div class="legend-diamond" style="background:#e74c3c"></div> Disease</div>
            <div class="legend-item"><div class="legend-dot" style="background:#f39c12"></div> Drug (Repurposing)</div>
            <div class="legend-item"><div class="legend-dot" style="background:#e74c3c"></div> Drug (FDA Approved)</div>
            <div class="legend-item"><div class="legend-dot" style="background:#1abc9c"></div> Drug (Clinical Trial)</div>
            <div class="legend-item"><div class="legend-dot" style="background:#3498db"></div> Drug (Research)</div>
            <div class="legend-item"><div class="legend-triangle" style="border-bottom-color:#2ecc71"></div> Target</div>
            <div class="legend-item"><div class="legend-dot" style="background:#9b59b6"></div> Pathway</div>
        </div>

        <!-- Legend: Edges -->
        <div class="control-section">
            <h3>🔗 Edge Types</h3>
            <div class="edge-legend">
                <div class="edge-legend-item"><div class="legend-line" style="background:#e74c3c"></div> TREATS</div>
                <div class="edge-legend-item"><div class="legend-line" style="background:#f39c12;border-style:dashed"></div> PREDICTED_FOR</div>
                <div class="edge-legend-item"><div class="legend-line" style="background:#2ecc71"></div> TARGETS</div>
                <div class="edge-legend-item"><div class="legend-line" style="background:#95a5a6"></div> ASSOCIATED_WITH</div>
                <div class="edge-legend-item"><div class="legend-line" style="background:#9b59b6"></div> IN_PATHWAY</div>
            </div>
        </div>

        <!-- Shared Drugs -->
        <div class="control-section">
            <h3>🔄 Cross-Disease Drugs ({len(shared)})</h3>
            <table>
                <tr><th>Drug</th><th>Diseases</th><th>#</th></tr>
                {shared_rows}
            </table>
        </div>

        <!-- Node Detail -->
        <div id="nodeDetail" class="node-detail" style="display:none">
            <h4 id="detailTitle">Node Detail</h4>
            <div id="detailContent"></div>
        </div>
    </div>

    <div class="graph-container">
        <div id="network"></div>
    </div>
</div>

<script>
var nodesData = new vis.DataSet({nodes_json});
var edgesData = new vis.DataSet({edges_json});
var allNodes = {nodes_json};
var allEdges = {edges_json};

var container = document.getElementById("network");
var data = {{ nodes: nodesData, edges: edgesData }};
var options = {{
    physics: {{
        enabled: true,
        barnesHut: {{
            gravitationalConstant: -3000,
            centralGravity: 0.3,
            springLength: 120,
            springConstant: 0.04,
            damping: 0.09,
        }},
        stabilization: {{ iterations: 150 }},
    }},
    interaction: {{
        hover: true,
        tooltipDelay: 100,
        navigationButtons: true,
        keyboard: true,
    }},
    edges: {{
        smooth: {{ type: "continuous" }},
        font: {{ size: 10, color: "#7f8c8d" }},
    }},
}};

var network = new vis.Network(container, data, options);
var physicsEnabled = true;

// 노드 클릭 상세 정보
network.on("click", function(params) {{
    if (params.nodes.length > 0) {{
        var nodeId = params.nodes[0];
        var node = allNodes.find(n => n.id === nodeId);
        if (node) {{
            var detail = document.getElementById("nodeDetail");
            detail.style.display = "block";
            document.getElementById("detailTitle").textContent = node.label;

            var html = "<p><b>Type:</b> " + (node.type || node.group) + "</p>";
            if (node.category) html += "<p><b>Category:</b> " + node.category + "</p>";
            if (node.safety_score) html += "<p><b>Safety Score:</b> " + node.safety_score + "</p>";
            if (node.uniprot) html += "<p><b>UniProt:</b> " + node.uniprot + "</p>";
            if (node.plddt) html += "<p><b>pLDDT:</b> " + node.plddt + "</p>";
            if (node.pocket) html += "<p><b>Pocket:</b> " + node.pocket + " residues</p>";

            // 연결된 노드
            var connected = network.getConnectedNodes(nodeId);
            html += "<p><b>Connections:</b> " + connected.length + "</p>";

            document.getElementById("detailContent").innerHTML = html;
        }}
    }}
}});

function filterByDisease() {{
    var disease = document.getElementById("diseaseFilter").value;
    if (disease === "all") {{
        nodesData.clear();
        nodesData.add(allNodes.map(n => ({{...n}})));
        edgesData.clear();
        edgesData.add(allEdges.map(e => ({{...e}})));
        return;
    }}

    var diseaseId = "disease_" + disease;
    var visibleNodes = new Set([diseaseId]);
    var visibleEdges = [];

    allEdges.forEach(function(e) {{
        if (e.to === diseaseId || e.from === diseaseId) {{
            visibleNodes.add(e.from);
            visibleNodes.add(e.to);
            visibleEdges.push(e);
        }}
    }});

    // 2차 연결 (drug → target)
    allEdges.forEach(function(e) {{
        if (visibleNodes.has(e.from) && e.type === "targets") {{
            visibleNodes.add(e.to);
            visibleEdges.push(e);
        }}
    }});

    var filteredNodes = allNodes.filter(n => visibleNodes.has(n.id));
    nodesData.clear();
    nodesData.add(filteredNodes);
    edgesData.clear();
    edgesData.add(visibleEdges);
    network.fit();
}}

function searchNode() {{
    var query = document.getElementById("searchInput").value.toLowerCase();
    if (!query) {{
        allNodes.forEach(function(n) {{
            nodesData.update({{id: n.id, opacity: 1.0}});
        }});
        return;
    }}
    allNodes.forEach(function(n) {{
        var match = n.label.toLowerCase().includes(query);
        nodesData.update({{id: n.id, opacity: match ? 1.0 : 0.15}});
    }});
}}

function resetView() {{
    document.getElementById("diseaseFilter").value = "all";
    document.getElementById("searchInput").value = "";
    nodesData.clear();
    nodesData.add(allNodes.map(n => ({{...n}})));
    edgesData.clear();
    edgesData.add(allEdges.map(e => ({{...e}})));
    network.fit();
}}

function togglePhysics() {{
    physicsEnabled = !physicsEnabled;
    network.setOptions({{ physics: {{ enabled: physicsEnabled }} }});
}}
</script>
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)
    print(f"✅ {output_path} ({len(html)} chars)")


def main():
    base_dir = Path(__file__).parent.parent
    results_dir = base_dir / "results"

    print("=" * 80)
    print("Knowledge Graph Interactive Viewer Generation")
    print("=" * 80)

    data_path = results_dir / "knowledge_graph_data.json"
    output_path = results_dir / "knowledge_graph_viewer.html"

    if not data_path.exists():
        print(f"ERROR: {data_path} not found")
        return

    generate_kg_viewer(data_path, output_path)

    print(f"\n브라우저에서 열기: open {output_path}")
    print("\n✅ 완료!")


if __name__ == "__main__":
    main()
