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


def generate_3d_viewer_html(structures, output_path):
    """3Dmol.js 기반 3D 뷰어 HTML 생성"""

    # 각 구조의 PDB 내용 로드
    structure_data = []
    for s in structures:
        pdb_path = s.get("pdb_path")
        if pdb_path and Path(pdb_path).exists():
            with open(pdb_path) as f:
                pdb_content = f.read()
            structure_data.append(
                {
                    "gene": s["gene"],
                    "uniprot": s["uniprot_id"],
                    "drug": s.get("drugs", [""])[0],
                    "plddt_mean": s.get("plddt", {}).get("mean", 0),
                    "pdb": pdb_content,
                }
            )

    if not structure_data:
        print("  No structures to visualize")
        return

    # HTML 생성
    options_html = ""
    pdb_js_array = ""

    for i, sd in enumerate(structure_data):
        pdb_escaped = sd["pdb"].replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
        pdb_js_array += (
            f'  {{ gene: "{sd["gene"]}", uniprot: "{sd["uniprot"]}", drug: "{sd["drug"]}", '
            f'plddt: {sd["plddt_mean"]}, pdb: `{pdb_escaped}` }},\n'
        )
        options_html += f'<option value="{i}">{sd["gene"]} ({sd["uniprot"]}) - pLDDT: {sd["plddt_mean"]}</option>\n'

    html = f"""<!DOCTYPE html>
<html>
<head>
<title>AlphaFold 3D Viewer — Colon Drug Repurposing</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/3Dmol/2.0.1/3Dmol-min.js"></script>
<style>
body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
.container {{ max-width: 1200px; margin: 0 auto; }}
h1 {{ color: #2c3e50; }}
.viewer-container {{ width: 100%; height: 500px; position: relative; border: 2px solid #3498db; border-radius: 8px; overflow: hidden; }}
.controls {{ margin: 15px 0; padding: 15px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
select, button {{ padding: 8px 15px; margin: 5px; font-size: 14px; border-radius: 4px; border: 1px solid #ccc; }}
button {{ background: #3498db; color: white; border: none; cursor: pointer; }}
button:hover {{ background: #2980b9; }}
.info {{ padding: 15px; background: white; border-radius: 8px; margin-top: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
.legend {{ display: flex; gap: 15px; margin: 10px 0; }}
.legend-item {{ display: flex; align-items: center; gap: 5px; }}
.legend-color {{ width: 20px; height: 20px; border-radius: 3px; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
th {{ background: #3498db; color: white; }}
tr:nth-child(even) {{ background: #f9f9f9; }}
</style>
</head>
<body>
<div class="container">
<h1>AlphaFold 3D Structure Viewer</h1>
<h3>Colon (COAD+READ) Drug Repurposing — Top 15 Target Proteins</h3>

<div class="controls">
  <label><b>Select Target:</b></label>
  <select id="proteinSelect" onchange="loadStructure()">
    {options_html}
  </select>
  <button onclick="setStyle('cartoon')">Cartoon</button>
  <button onclick="setStyle('stick')">Stick</button>
  <button onclick="setStyle('sphere')">Sphere</button>
  <button onclick="toggleSpin()">Spin</button>
</div>

<div class="legend">
  <b>pLDDT Color:</b>
  <div class="legend-item"><div class="legend-color" style="background:#0053D6"></div> Very High (>90)</div>
  <div class="legend-item"><div class="legend-color" style="background:#65CBF3"></div> High (70-90)</div>
  <div class="legend-item"><div class="legend-color" style="background:#FFDB13"></div> Low (50-70)</div>
  <div class="legend-item"><div class="legend-color" style="background:#FF7D45"></div> Very Low (<50)</div>
</div>

<div id="viewer" class="viewer-container"></div>

<div id="info" class="info"></div>

<h3>All Target Structures</h3>
<table>
<tr><th>Gene</th><th>UniProt</th><th>Drug(s)</th><th>pLDDT Mean</th><th>pLDDT Confident (%)</th></tr>
{"".join(f'<tr><td>{sd["gene"]}</td><td>{sd["uniprot"]}</td><td>{sd["drug"]}</td><td>{sd["plddt_mean"]}</td><td>-</td></tr>' for sd in structure_data)}
</table>
</div>

<script>
var structures = [
{pdb_js_array}
];

var viewer = null;
var spinning = false;
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
  applyPLDDTColoring();
  viewer.zoomTo();
  viewer.render();

  document.getElementById("info").innerHTML =
    "<b>Gene:</b> " + s.gene + " | <b>UniProt:</b> " + s.uniprot +
    " | <b>Drug:</b> " + s.drug + " | <b>Mean pLDDT:</b> " + s.plddt;
}}

function applyPLDDTColoring() {{
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
}}

function setStyle(style) {{
  currentStyle = style;
  var styleObj = {{}};

  if (style === 'cartoon') {{
    applyPLDDTColoring();
  }} else if (style === 'stick') {{
    viewer.setStyle({{}}, {{stick: {{colorscheme: 'Jmol'}}}});
  }} else if (style === 'sphere') {{
    viewer.setStyle({{}}, {{sphere: {{scale: 0.3, colorscheme: 'Jmol'}}}});
  }}
  viewer.render();
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
    print(f"  ✅ 3D Viewer: {output_path}")


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

        structures.append(
            {
                "gene": gene,
                "uniprot_id": uid,
                "pdb_path": str(pdb_path),
                "pdb_url": pdb_url,
                "plddt": plddt,
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

    print(f"{'Gene':15s} {'UniProt':10s} {'pLDDT':>7s} {'Confident%':>10s} {'Drugs':30s}")
    print("-" * 80)
    for s in sorted(structures, key=lambda x: x["plddt"]["mean"] if x["plddt"] else 0, reverse=True):
        plddt = s["plddt"]
        if plddt:
            conf_icon = "🟢" if plddt["mean"] >= 70 else "🟡" if plddt["mean"] >= 50 else "🔴"
            print(
                f"{s['gene']:15s} {s['uniprot_id']:10s} {conf_icon} {plddt['mean']:>5.1f} "
                f"{plddt['pct_confident']:>9.1f}% {', '.join(s['drugs'][:3]):30s}"
            )

    print(f"\n  3D Viewer: {viewer_path}")
    print("\n✅ Step 7.5 완료!")


if __name__ == "__main__":
    main()
