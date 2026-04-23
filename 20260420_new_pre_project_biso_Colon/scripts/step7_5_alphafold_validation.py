#!/usr/bin/env python3
"""
Step 7.5: AlphaFold 구조 기반 검증

Top 15 약물의 타겟 단백질에 대해:
1. UniProt ID 매핑 (UniProt API)
2. AlphaFold DB 에서 PDB 구조 다운로드
3. pLDDT (구조 신뢰도) 분석
4. RDKit 로 약물 3D 구조 생성
5. 3D 뷰어 HTML 생성 (3Dmol.js)
6. 결과 저장

입력:
  - results/colon_final_top15.csv

출력:
  - results/alphafold_validation/
  - results/alphafold_validation/alphafold_validation_results.json
  - results/alphafold_validation/alphafold_3d_viewer.html
  - results/alphafold_validation/*.pdb (타겟 구조)
"""

import json
import urllib.parse
import urllib.request
import time
from pathlib import Path

import numpy as np
import pandas as pd
from Bio.PDB import PDBParser, NeighborSearch
from scipy.spatial import ConvexHull

try:
    from rdkit import Chem
    from rdkit.Chem import AllChem, Descriptors

    HAS_RDKIT = True
except ImportError:
    HAS_RDKIT = False


# --- UniProt 매핑 (수동, 주요 타겟) ---

GENE_TO_UNIPROT = {
    "TOP1": "P11387",
    "TOP2A": "P11388",
    "TOP2B": "Q02880",
    "MTOR": "P42345",
    "MTORC1": "P42345",
    "MEK1": "Q02750",
    "MEK2": "P36507",
    "HDAC1": "Q13547",
    "HDAC2": "Q92769",
    "HDAC3": "O15379",
    "HDAC6": "Q9UBN7",
    "HSP90": "P07900",
    "HSP90AA1": "P07900",
    "HSP90AB1": "P08238",
    "PI3K": "P42336",
    "PI3Kbeta": "O00329",
    "PIK3CB": "O00329",
    "FLT3": "P36888",
    "JAK2": "O60674",
    "NTRK1": "P04629",
    "NTRK2": "Q16620",
    "NTRK3": "Q16288",
    "TUBB": "P07437",
    "TUBB1": "Q9H4B7",
    "BCL2": "P10415",
    "BCL2L1": "Q07817",
    "MCL1": "Q07820",
    "ACTB": "P60709",
    "BRAF": "P15056",
    "RAF1": "P04049",
    "EGFR": "P00533",
    "ERBB2": "P04626",
    "VEGFR": "P17948",
    "KDR": "P35968",
    "FGFR": "P11362",
    "CDK4": "P11802",
    "CDK6": "Q00534",
    "PARP1": "P09874",
    "DNA": None,
    "RNA": None,
}


def load_top15(results_dir):
    """Top 15 약물 + 타겟 로드"""
    path = results_dir / "colon_final_top15.csv"
    df = pd.read_csv(path)
    print(f"  Top 15 loaded: {len(df)} drugs")
    return df


def extract_targets(top15):
    """약물별 타겟 추출"""
    drug_targets = {}

    name_col = "drug_name" if "drug_name" in top15.columns else "DRUG_NAME"
    target_col = "target" if "target" in top15.columns else "TARGET"

    for _, row in top15.iterrows():
        drug = row[name_col]
        target_str = str(row.get(target_col, ""))

        if not target_str or target_str == "nan":
            continue

        genes = []
        for t in target_str.replace(";", ",").replace("/", ",").split(","):
            t = t.strip()
            if t and len(t) >= 2:
                genes.append(t)

        drug_targets[drug] = genes

    all_genes = set()
    for genes in drug_targets.values():
        all_genes.update(genes)

    print(f"  Drugs with targets: {len(drug_targets)}")
    print(f"  Unique target genes: {len(all_genes)}")
    return drug_targets, sorted(all_genes)


def resolve_uniprot(gene_name):
    """유전자명 → UniProt ID (수동 매핑 우선, 없으면 API)"""
    # 수동 매핑
    if gene_name in GENE_TO_UNIPROT:
        uid = GENE_TO_UNIPROT[gene_name]
        return uid  # None 가능 (DNA, RNA 등)

    # UniProt API 검색
    try:
        query = urllib.parse.quote(f"gene_exact:{gene_name} AND organism_id:9606")
        url = f"https://rest.uniprot.org/uniprotkb/search?query={query}&format=json&size=1"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0 (Research)")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        results = data.get("results", [])
        if results:
            return results[0]["primaryAccession"]
    except Exception as e:
        print(f"    UniProt API error for {gene_name}: {e}")

    return None


def fetch_alphafold_info(uniprot_id):
    """AlphaFold DB 에서 구조 정보 조회"""
    url = f"https://alphafold.ebi.ac.uk/api/prediction/{uniprot_id}"
    try:
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/json")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        if isinstance(data, list) and len(data) > 0:
            return data[0]
    except Exception as e:
        print(f"    AlphaFold API error for {uniprot_id}: {e}")
    return None


def download_pdb(pdb_url, output_path):
    """PDB 파일 다운로드"""
    try:
        req = urllib.request.Request(pdb_url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            with open(output_path, "wb") as f:
                f.write(resp.read())
        return True
    except Exception as e:
        print(f"    Download error: {e}")
        return False


def parse_plddt_from_pdb(pdb_path):
    """PDB 파일에서 pLDDT 값 추출 (B-factor 컬럼)"""
    plddt_values = []
    try:
        with open(pdb_path) as f:
            for line in f:
                if line.startswith("ATOM") and len(line) >= 66:
                    try:
                        bfactor = float(line[60:66].strip())
                        plddt_values.append(bfactor)
                    except ValueError:
                        pass
    except Exception:
        pass

    if plddt_values:
        return {
            "mean": round(np.mean(plddt_values), 2),
            "median": round(np.median(plddt_values), 2),
            "min": round(np.min(plddt_values), 2),
            "max": round(np.max(plddt_values), 2),
            "n_residues": len(set(range(len(plddt_values)))),
            "pct_confident": round(np.sum(np.array(plddt_values) >= 70) / len(plddt_values) * 100, 1),
            "pct_very_confident": round(np.sum(np.array(plddt_values) >= 90) / len(plddt_values) * 100, 1),
        }
    return None


def detect_binding_pockets(pdb_path, min_pocket_size=10, probe_radius=3.0):
    """
    BioPython 기반 binding pocket 탐지.

    방법: 단백질 표면 잔기 중 소수성 잔기가 밀집된 영역 = 잠재적 결합 포켓
    fpocket 의 간소화 버전.

    1. 전체 원자 좌표 로드
    2. 표면 노출 잔기 추정 (이웃 원자 수 적은 잔기)
    3. 소수성 + 포켓 형성 잔기 클러스터링
    4. 가장 큰 클러스터 = 주요 포켓
    """
    parser = PDBParser(QUIET=True)
    try:
        structure = parser.get_structure("protein", pdb_path)
    except Exception as e:
        print(f"    PDB parse error: {e}")
        return None

    model = structure[0]

    # 전체 CA 원자
    ca_atoms = []
    all_atoms = []
    residue_info = {}

    for chain in model:
        for residue in chain:
            if residue.id[0] != " ":  # hetero atoms 제외
                continue
            resname = residue.get_resname()
            resid = residue.get_id()[1]
            chain_id = chain.get_id()

            if residue.has_id("CA"):
                ca = residue["CA"]
                ca_atoms.append(ca)
                residue_info[ca.get_serial_number()] = {
                    "resname": resname,
                    "resid": resid,
                    "chain": chain_id,
                    "coord": ca.get_coord().tolist(),
                }

            for atom in residue:
                all_atoms.append(atom)

    if len(ca_atoms) < 20:
        return None

    # 소수성 잔기 (포켓 형성에 중요)
    HYDROPHOBIC = {"ALA", "VAL", "LEU", "ILE", "MET", "PHE", "TRP", "PRO", "TYR"}
    POLAR_POCKET = {"SER", "THR", "ASN", "GLN", "HIS", "CYS"}
    POCKET_RESIDUES = HYDROPHOBIC | POLAR_POCKET

    # NeighborSearch 로 각 CA 의 이웃 수 계산
    ns = NeighborSearch(all_atoms)

    surface_residues = []
    for ca in ca_atoms:
        serial = ca.get_serial_number()
        if serial not in residue_info:
            continue

        info = residue_info[serial]

        # 이웃 원자 수 (10Å 이내)
        neighbors = ns.search(ca.get_coord(), 10.0, "A")
        n_neighbors = len(neighbors)

        # 표면 잔기 = 이웃 적음 (< 중앙값)
        # 포켓 잔기 = 적당한 이웃 (너무 많지도 적지도 않음)
        info["n_neighbors"] = n_neighbors
        info["is_hydrophobic"] = info["resname"] in HYDROPHOBIC
        info["is_pocket_type"] = info["resname"] in POCKET_RESIDUES

        surface_residues.append(info)

    if not surface_residues:
        return None

    # 이웃 수 기준 중앙값
    neighbor_counts = [r["n_neighbors"] for r in surface_residues]
    median_neighbors = np.median(neighbor_counts)

    # 포켓 후보: 소수성/극성 잔기 중 이웃이 중간 범위 (표면 근처 오목한 부분)
    pocket_candidates = []
    for r in surface_residues:
        if r["is_pocket_type"] and r["n_neighbors"] < median_neighbors * 1.2:
            pocket_candidates.append(r)

    if len(pocket_candidates) < min_pocket_size:
        # 기준 완화
        pocket_candidates = [r for r in surface_residues if r["n_neighbors"] < median_neighbors * 1.3]

    if not pocket_candidates:
        return None

    coords = np.array([r["coord"] for r in pocket_candidates])

    # 간단한 그리디 클러스터링
    used = set()
    clusters = []

    for i in range(len(pocket_candidates)):
        if i in used:
            continue
        cluster = [i]
        used.add(i)

        for j in range(i + 1, len(pocket_candidates)):
            if j in used:
                continue
            dist = np.linalg.norm(coords[i] - coords[j])
            if dist < 8.0:
                # 클러스터 내 모든 멤버와 거리 체크
                close_to_cluster = False
                for k in cluster:
                    if np.linalg.norm(coords[k] - coords[j]) < 8.0:
                        close_to_cluster = True
                        break
                if close_to_cluster:
                    cluster.append(j)
                    used.add(j)

        if len(cluster) >= min_pocket_size // 2:
            clusters.append(cluster)

    if not clusters:
        return None

    # 가장 큰 클러스터 = 주요 포켓
    clusters.sort(key=len, reverse=True)
    main_pocket_indices = clusters[0]

    pocket_residues = [pocket_candidates[i] for i in main_pocket_indices]

    # 포켓 신뢰도 (pLDDT 기반 — PDB B-factor 에서)
    # pocket 잔기의 평균 이웃 수로 대략적 confidence
    pocket_confidence = 1.0 - (np.mean([r["n_neighbors"] for r in pocket_residues]) / max(neighbor_counts))
    pocket_confidence = max(0, min(1, pocket_confidence))

    # 포켓 볼륨 추정 (ConvexHull)
    pocket_coords = np.array([r["coord"] for r in pocket_residues])
    try:
        if len(pocket_coords) >= 4:
            hull = ConvexHull(pocket_coords)
            volume = hull.volume
        else:
            volume = 0
    except Exception:
        volume = 0

    return {
        "n_residues": len(pocket_residues),
        "residues": [f"{r['resname']}:{r['chain']}{r['resid']}" for r in pocket_residues],
        "confidence": round(pocket_confidence, 3),
        "volume": round(volume, 1),
        "center": np.mean(pocket_coords, axis=0).tolist(),
        "hydrophobic_ratio": round(sum(1 for r in pocket_residues if r["is_hydrophobic"]) / len(pocket_residues), 2),
    }


def generate_3d_viewer_html(structures, output_path):
    """3Dmol.js 기반 3D 뷰어 — binding site 포함"""

    structure_data = []
    for s in structures:
        pdb_path = s.get("pdb_path")
        if pdb_path and Path(pdb_path).exists():
            with open(pdb_path) as f:
                pdb_content = f.read()

            pocket = s.get("pocket", {})
            pocket_residues = pocket.get("residues", []) if pocket else []

            # 포켓 잔기를 JS 에서 사용할 형식으로 변환
            # "LEU:A90" → {resi: 90, chain: "A"}
            pocket_js = []
            for res_str in pocket_residues:
                parts = res_str.split(":")
                if len(parts) == 2:
                    chain_resid = parts[1]
                    chain = chain_resid[0]
                    resid = chain_resid[1:]
                    if resid.isdigit():
                        pocket_js.append({"resi": int(resid), "chain": chain})

            structure_data.append(
                {
                    "gene": s["gene"],
                    "uniprot": s["uniprot_id"],
                    "drug": s.get("drugs", [""])[0] if s.get("drugs") else "",
                    "plddt_mean": s.get("plddt", {}).get("mean", 0) if s.get("plddt") else 0,
                    "pocket_size": pocket.get("n_residues", 0) if pocket else 0,
                    "pocket_conf": pocket.get("confidence", 0) if pocket else 0,
                    "pocket_volume": pocket.get("volume", 0) if pocket else 0,
                    "pocket_residues": pocket_js,
                    "pocket_residues_str": pocket_residues,
                    "pdb": pdb_content,
                }
            )

    if not structure_data:
        print("  No structures to visualize")
        return

    options_html = ""
    for i, sd in enumerate(structure_data):
        pocket_info = f" | Pocket: {sd['pocket_size']} res" if sd["pocket_size"] > 0 else ""
        options_html += (
            f'<option value="{i}">{sd["gene"]} ({sd["uniprot"]}) - pLDDT: {sd["plddt_mean"]}{pocket_info}</option>\n'
        )

    # 구조 데이터를 별도 JS 파일 대신 인라인으로
    structures_js = "var structures = [\n"
    for sd in structure_data:
        pdb_escaped = sd["pdb"].replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
        pocket_js_str = json.dumps(sd["pocket_residues"])
        pocket_res_str = json.dumps(sd["pocket_residues_str"])
        structures_js += f"""  {{
    gene: "{sd['gene']}", uniprot: "{sd['uniprot']}", drug: "{sd['drug']}",
    plddt: {sd['plddt_mean']}, pocket_size: {sd['pocket_size']},
    pocket_conf: {sd['pocket_conf']}, pocket_volume: {sd['pocket_volume']},
    pocket_residues: {pocket_js_str},
    pocket_residues_str: {pocket_res_str},
    pdb: `{pdb_escaped}`
  }},
"""
    structures_js += "];\n"

    # 테이블 행
    table_rows = ""
    for sd in structure_data:
        pocket_info = f"{sd['pocket_size']} residues ({sd['pocket_conf']:.3f})" if sd["pocket_size"] > 0 else "Not detected"
        table_rows += (
            f'<tr><td>{sd["gene"]}</td><td>{sd["uniprot"]}</td><td>{sd["drug"]}</td>'
            f'<td>{sd["plddt_mean"]}</td><td>{pocket_info}</td><td>{sd["pocket_volume"]:.0f}</td></tr>\n'
        )

    html = f"""<!DOCTYPE html>
<html>
<head>
<title>AlphaFold 3D Viewer — Colon Drug Repurposing</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/3Dmol/2.0.1/3Dmol-min.js"></script>
<style>
body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
.container {{ max-width: 1200px; margin: 0 auto; }}
h1 {{ color: #2c3e50; }}
h3 {{ color: #34495e; }}
.viewer-container {{ width: 100%; height: 550px; position: relative; border: 2px solid #3498db; border-radius: 8px; overflow: hidden; background: white; }}
.controls {{ margin: 15px 0; padding: 15px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
select, button {{ padding: 8px 15px; margin: 5px; font-size: 14px; border-radius: 4px; border: 1px solid #ccc; cursor: pointer; }}
button {{ background: #3498db; color: white; border: none; }}
button:hover {{ background: #2980b9; }}
button.active {{ background: #e74c3c; }}
.info-panel {{ padding: 15px; background: white; border-radius: 8px; margin-top: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
.legend {{ display: flex; gap: 15px; margin: 10px 0; flex-wrap: wrap; }}
.legend-item {{ display: flex; align-items: center; gap: 5px; font-size: 13px; }}
.legend-color {{ width: 18px; height: 18px; border-radius: 3px; }}
.metric {{ display: inline-block; padding: 5px 12px; margin: 3px; border-radius: 15px; font-size: 13px; font-weight: bold; }}
.metric-blue {{ background: #e8f4fd; color: #2980b9; }}
.metric-gold {{ background: #fef9e7; color: #d4ac0d; }}
.metric-green {{ background: #eafaf1; color: #27ae60; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; font-size: 13px; }}
th {{ background: #3498db; color: white; }}
tr:nth-child(even) {{ background: #f9f9f9; }}
.pocket-label {{ color: #d4ac0d; font-weight: bold; }}
</style>
</head>
<body>
<div class="container">
<h1>🔬 AlphaFold 3D Structure Viewer</h1>
<h3>Colon (COAD+READ) Drug Repurposing — Top 15 Target Proteins with Binding Sites</h3>

<div class="controls">
  <label><b>Select Target:</b></label>
  <select id="proteinSelect" onchange="loadStructure()">
    {options_html}
  </select>
  <button onclick="setStyle('cartoon')">Cartoon (pLDDT)</button>
  <button onclick="setStyle('stick')">Stick</button>
  <button onclick="setStyle('sphere')">Sphere</button>
  <button id="pocketBtn" onclick="togglePocket()">Show Pocket</button>
  <button onclick="toggleSpin()">Spin</button>
</div>

<div class="legend">
  <b>pLDDT:</b>
  <div class="legend-item"><div class="legend-color" style="background:#0053D6"></div> Very High (&gt;90)</div>
  <div class="legend-item"><div class="legend-color" style="background:#65CBF3"></div> High (70-90)</div>
  <div class="legend-item"><div class="legend-color" style="background:#FFDB13"></div> Low (50-70)</div>
  <div class="legend-item"><div class="legend-color" style="background:#FF7D45"></div> Very Low (&lt;50)</div>
  <div class="legend-item"><div class="legend-color" style="background:#DAA520"></div> <span class="pocket-label">Binding Pocket (gold stick)</span></div>
</div>

<div id="viewer" class="viewer-container"></div>

<div id="info" class="info-panel">Loading...</div>

<h3>All Target Structures</h3>
<table>
<tr><th>Gene</th><th>UniProt</th><th>Drug(s)</th><th>pLDDT</th><th>Binding Pocket</th><th>Volume (ų)</th></tr>
{table_rows}
</table>

<p style="color: #7f8c8d; font-size: 12px; margin-top: 20px;">
마우스 드래그로 회전, 휠로 확대/축소. Cartoon (pLDDT Color)는 B-factor(pLDDT) 기반입니다.
포켓 후보 잔기는 gold stick으로 표시됩니다.
</p>
</div>

<script>
{structures_js}

var viewer = null;
var spinning = false;
var showPocket = true;
var currentStyle = 'cartoon';

function initViewer() {{
  viewer = $3Dmol.createViewer("viewer", {{backgroundColor: "white"}});
  loadStructure();
}}

function loadStructure() {{
  var idx = document.getElementById("proteinSelect").value;
  var s = structures[idx];

  viewer.clear();
  viewer.addModel(s.pdb, "pdb");

  applyStyle();

  viewer.zoomTo();
  viewer.render();

  // Info panel
  var pocketInfo = s.pocket_size > 0
    ? '<span class="metric metric-gold">Pocket: ' + s.pocket_size + ' residues</span>' +
      '<span class="metric metric-gold">Conf: ' + s.pocket_conf.toFixed(3) + '</span>' +
      '<span class="metric metric-gold">Vol: ' + s.pocket_volume.toFixed(0) + ' ų</span>'
    : '<span class="metric" style="background:#fee;color:#c00;">No pocket detected</span>';

  var siteRes = s.pocket_residues_str.length > 0
    ? '<br><b>Site Residues:</b> ' + s.pocket_residues_str.join('; ')
    : '';

  document.getElementById("info").innerHTML =
    '<span class="metric metric-blue">Drug: ' + s.drug + '</span>' +
    '<span class="metric metric-blue">Target: ' + s.gene + '</span>' +
    '<span class="metric metric-blue">UniProt: ' + s.uniprot + '</span>' +
    '<span class="metric metric-green">Mean pLDDT: ' + s.plddt.toFixed(1) + '</span>' +
    pocketInfo + siteRes;
}}

function applyStyle() {{
  var idx = document.getElementById("proteinSelect").value;
  var s = structures[idx];

  // 기본 스타일
  if (currentStyle === 'cartoon') {{
    viewer.setStyle({{}}, {{
      cartoon: {{
        colorfunc: function(atom) {{
          var b = atom.b;
          if (b >= 90) return '#0053D6';
          if (b >= 70) return '#65CBF3';
          if (b >= 50) return '#FFDB13';
          return '#FF7D45';
        }}
      }}
    }});
  }} else if (currentStyle === 'stick') {{
    viewer.setStyle({{}}, {{stick: {{colorscheme: 'Jmol'}}}});
  }} else if (currentStyle === 'sphere') {{
    viewer.setStyle({{}}, {{sphere: {{scale: 0.3, colorscheme: 'Jmol'}}}});
  }}

  // 포켓 잔기 gold stick 으로 하이라이트
  if (showPocket && s.pocket_residues.length > 0) {{
    for (var i = 0; i < s.pocket_residues.length; i++) {{
      var pr = s.pocket_residues[i];
      viewer.addStyle(
        {{resi: pr.resi, chain: pr.chain}},
        {{stick: {{color: '#DAA520', radius: 0.15}}}}
      );
    }}
  }}

  viewer.render();
}}

function setStyle(style) {{
  currentStyle = style;
  applyStyle();
}}

function togglePocket() {{
  showPocket = !showPocket;
  var btn = document.getElementById("pocketBtn");
  btn.textContent = showPocket ? "Hide Pocket" : "Show Pocket";
  btn.className = showPocket ? "active" : "";
  applyStyle();
}}

function toggleSpin() {{
  spinning = !spinning;
  viewer.spin(spinning);
}}

window.onload = initViewer;
</script>
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)
    print(f"  ✅ 3D Viewer (with pockets): {output_path}")


def main():
    base_dir = Path(__file__).parent.parent
    results_dir = base_dir / "results"
    af_dir = results_dir / "alphafold_validation"
    af_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("Step 7.5: AlphaFold Structure-based Validation")
    print("=" * 80)

    # 1. Top 15 로드
    print("\n[1] Top 15 로드")
    top15 = load_top15(results_dir)

    # 2. 타겟 추출
    print("\n[2] 타겟 유전자 추출")
    drug_targets, all_genes = extract_targets(top15)

    # 3. UniProt ID 매핑
    print("\n[3] UniProt ID 매핑")
    gene_uniprot = {}
    for gene in all_genes:
        uid = resolve_uniprot(gene)
        if uid:
            gene_uniprot[gene] = uid
            print(f"  {gene:20s} → {uid}")
        else:
            print(f"  {gene:20s} → ❌ (no UniProt)")
        time.sleep(0.3)

    print(f"  매핑 성공: {len(gene_uniprot)}/{len(all_genes)}")

    # 4. AlphaFold 구조 다운로드
    print("\n[4] AlphaFold 구조 다운로드")
    structures = []
    unique_uniprots = set(gene_uniprot.values())

    for gene, uid in gene_uniprot.items():
        af_info = fetch_alphafold_info(uid)
        if af_info is None:
            print(f"  {gene} ({uid}): ❌ AlphaFold 없음")
            continue

        pdb_url = af_info.get("pdbUrl", "")
        if not pdb_url:
            continue

        pdb_path = af_dir / f"AF-{uid}-F1.pdb"

        if not pdb_path.exists():
            print(f"  {gene} ({uid}): 다운로드 중...", end=" ", flush=True)
            success = download_pdb(pdb_url, pdb_path)
            if success:
                print("✅")
            else:
                print("❌")
                continue
        else:
            print(f"  {gene} ({uid}): 이미 있음 ✅")

        # pLDDT 분석
        plddt = parse_plddt_from_pdb(pdb_path)

        # 이 유전자를 타겟으로 하는 약물 목록
        drugs_for_gene = [d for d, genes in drug_targets.items() if gene in genes]

        # Binding pocket 탐지
        pocket = detect_binding_pockets(str(pdb_path))
        if pocket:
            print(f"    Pocket: {pocket['n_residues']} residues, conf={pocket['confidence']:.3f}, vol={pocket['volume']:.0f}Å³")
        else:
            print("    Pocket: not detected")

        structures.append(
            {
                "gene": gene,
                "uniprot_id": uid,
                "pdb_path": str(pdb_path),
                "pdb_url": pdb_url,
                "plddt": plddt,
                "pocket": pocket,
                "drugs": drugs_for_gene,
                "alphafold_version": af_info.get("modelVersion", "?"),
            }
        )

        time.sleep(0.5)

    print(f"\n  구조 다운로드 완료: {len(structures)}/{len(gene_uniprot)}")

    # 5. 3D 뷰어 생성
    print("\n[5] 3D 뷰어 HTML 생성")
    viewer_path = af_dir / "alphafold_3d_viewer.html"
    generate_3d_viewer_html(structures, viewer_path)

    # 6. 결과 저장
    print("\n[6] 결과 저장")

    # pdb_path 를 상대 경로로
    for s in structures:
        s["pdb_path"] = str(Path(s["pdb_path"]).name)

    results = {
        "step": "Step 7.5 AlphaFold Validation",
        "disease": "colorectal cancer (COAD+READ)",
        "top_n_drugs": len(top15),
        "unique_targets": len(all_genes),
        "uniprot_mapped": len(gene_uniprot),
        "structures_downloaded": len(structures),
        "gene_to_uniprot": gene_uniprot,
        "structures": structures,
        "summary": {
            "avg_plddt": round(np.mean([s["plddt"]["mean"] for s in structures if s["plddt"]]), 2) if structures else 0,
            "high_confidence_targets": sum(1 for s in structures if s["plddt"] and s["plddt"]["mean"] >= 70),
            "very_high_confidence": sum(1 for s in structures if s["plddt"] and s["plddt"]["mean"] >= 90),
            "targets_with_pocket": sum(1 for s in structures if s.get("pocket")),
            "avg_pocket_size": round(np.mean([s["pocket"]["n_residues"] for s in structures if s.get("pocket")]), 1)
            if any(s.get("pocket") for s in structures)
            else 0,
            "avg_pocket_confidence": round(np.mean([s["pocket"]["confidence"] for s in structures if s.get("pocket")]), 3)
            if any(s.get("pocket") for s in structures)
            else 0,
        },
    }

    json_path = af_dir / "alphafold_validation_results.json"
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"  ✅ {json_path}")

    # 7. 요약
    print("\n" + "=" * 80)
    print("AlphaFold Validation Summary")
    print("=" * 80)
    print(f"  Targets: {len(all_genes)} genes → {len(gene_uniprot)} UniProt mapped → {len(structures)} structures")
    print(f"  Avg pLDDT: {results['summary']['avg_plddt']}")
    print(f"  High confidence (≥70): {results['summary']['high_confidence_targets']}")
    print(f"  Very high (≥90): {results['summary']['very_high_confidence']}")
    print()

    print(f"{'Gene':15s} {'UniProt':10s} {'pLDDT':>7s} {'Pocket':>8s} {'PocketConf':>10s} {'Vol':>8s} {'Drugs':25s}")
    print("-" * 90)
    for s in sorted(structures, key=lambda x: x["plddt"]["mean"] if x["plddt"] else 0, reverse=True):
        plddt = s["plddt"]
        pocket = s.get("pocket")
        if plddt:
            conf_icon = "🟢" if plddt["mean"] >= 70 else "🟡" if plddt["mean"] >= 50 else "🔴"
            p_size = f"{pocket['n_residues']}res" if pocket else "N/A"
            p_conf = f"{pocket['confidence']:.3f}" if pocket else "N/A"
            p_vol = f"{pocket['volume']:.0f}ų" if pocket else "N/A"
            print(
                f"{s['gene']:15s} {s['uniprot_id']:10s} {conf_icon} {plddt['mean']:>5.1f} "
                f"{p_size:>8s} {p_conf:>10s} {p_vol:>8s} {', '.join(s['drugs'][:2]):25s}"
            )

    print(f"\n  3D Viewer: {viewer_path}")
    print("\n✅ Step 7.5 완료!")


if __name__ == "__main__":
    main()
