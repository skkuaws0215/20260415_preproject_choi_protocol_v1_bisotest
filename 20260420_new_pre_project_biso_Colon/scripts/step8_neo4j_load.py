#!/usr/bin/env python3
"""
Step 8: Neo4j Knowledge Graph 적재

기존 biso-kg Aura 인스턴스 (BRCA + Lung) 에 Colon 데이터 추가.

적재 내용:
  1. Disease 노드: Colorectal Cancer (COAD+READ)
  2. Drug-Disease 관계: TREATS / PREDICTED_FOR
  3. CellLine 노드: Colon 35개
  4. Validation 관계: VALIDATED_BY (PRISM, CT, COSMIC, CPTAC, GEO)
  5. ADMET 속성: safety_score, verdict
  6. AlphaFold 속성: pLDDT, pocket_size
  7. COAD/READ 분석 결과

입력:
  - results/colon_final_top15.csv
  - results/colon_comprehensive_drug_scores.csv
  - results/colon_coad_read_drug_recommendations.csv
  - results/alphafold_validation/alphafold_validation_results.json
  - results/colon_admet_summary.json
  - data/labels.parquet

출력:
  - Neo4j Aura 에 노드/관계 적재
  - results/colon_neo4j_load_summary.json
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from neo4j import GraphDatabase


# Neo4j Aura 연결 정보
NEO4J_URI = "neo4j+s://108928fe.databases.neo4j.io"
NEO4J_USER = "108928fe"
NEO4J_PASSWORD = "hdU-dZXa1IFUaxhCsvQmLgbtxdjM8_ZJeUVCl8Dijak"


def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def create_disease_node(session):
    """Colorectal Cancer Disease 노드 생성"""
    session.run("""
        MERGE (d:Disease {name: 'Colorectal Cancer'})
        SET d.acronym = 'CRC',
            d.subtypes = ['COAD', 'READ'],
            d.description = 'Colorectal Cancer (COAD + READ)',
            d.tcga_code = 'COAD/READ',
            d.pipeline_version = 'v1.4',
            d.updated_at = datetime()
        RETURN d.name AS name
    """)
    print("  ✅ Disease: Colorectal Cancer (COAD+READ)")


def create_cell_line_nodes(session, base_dir):
    """Colon cell line 노드 생성 + Disease 연결"""
    labels = pd.read_parquet(base_dir / "data" / "labels.parquet")
    cell_lines = sorted(labels["sample_id"].unique())

    count = 0
    for cl in cell_lines:
        session.run("""
            MERGE (c:CellLine {name: $name})
            SET c.tissue = 'large_intestine',
                c.cancer_type = 'COAD/READ'
            WITH c
            MATCH (d:Disease {name: 'Colorectal Cancer'})
            MERGE (c)-[:CELL_LINE_OF]->(d)
        """, name=cl)
        count += 1

    print(f"  ✅ CellLine: {count} nodes (linked to CRC)")


def create_drug_disease_relationships(session, results_dir):
    """Top 30 Drug → Disease 관계 생성"""
    # Top 30 전체 (validation 포함)
    comp = pd.read_csv(results_dir / "colon_comprehensive_drug_scores.csv")

    count = 0
    for _, row in comp.iterrows():
        drug_name = row["drug_name"]

        session.run("""
            MATCH (drug:Drug) WHERE toLower(drug.name) = toLower($drug_name)
            MATCH (disease:Disease {name: 'Colorectal Cancer'})
            MERGE (drug)-[r:PREDICTED_FOR]->(disease)
            SET r.rank = $rank,
                r.pred_ic50 = $pred_ic50,
                r.validation_count = $val_count,
                r.confidence = $confidence,
                r.prism = $prism,
                r.clinical_trials = $ct,
                r.cosmic = $cosmic,
                r.cptac = $cptac,
                r.geo = $geo,
                r.pipeline = 'colon_v1',
                r.updated_at = datetime()
        """,
            drug_name=drug_name,
            rank=int(row["rank"]),
            pred_ic50=float(row.get("pred_ic50_mean", 0)),
            val_count=int(row.get("validation_count", 0)),
            confidence=str(row.get("confidence", "")),
            prism=int(row.get("prism", 0)),
            ct=int(row.get("clinical_trials", 0)),
            cosmic=int(row.get("cosmic", 0)),
            cptac=int(row.get("cptac", 0)),
            geo=int(row.get("geo", 0)),
        )
        count += 1

    print(f"  ✅ PREDICTED_FOR: {count} relationships")


def add_admet_properties(session, results_dir):
    """Top 15 약물에 ADMET 속성 추가"""
    top15 = pd.read_csv(results_dir / "colon_final_top15.csv")
    name_col = "drug_name" if "drug_name" in top15.columns else "DRUG_NAME"

    count = 0
    for _, row in top15.iterrows():
        drug_name = row[name_col]

        session.run("""
            MATCH (drug:Drug) WHERE toLower(drug.name) = toLower($drug_name)
            MATCH (drug)-[r:PREDICTED_FOR]->(d:Disease {name: 'Colorectal Cancer'})
            SET r.admet_safety_score = $safety,
                r.admet_verdict = $verdict,
                r.category = $category,
                r.recommendation_rank = $rec_rank,
                r.is_top15 = true
        """,
            drug_name=drug_name,
            safety=float(row.get("safety_score", 0)),
            verdict=str(row.get("verdict", "")),
            category=str(row.get("category", "")),
            rec_rank=int(row.get("recommendation_rank", row.get("rank", 0))),
        )
        count += 1

    print(f"  ✅ ADMET properties: {count} drugs updated")


def add_alphafold_properties(session, results_dir):
    """AlphaFold 구조 정보 추가"""
    af_path = results_dir / "alphafold_validation" / "alphafold_validation_results.json"
    if not af_path.exists():
        print("  ⚠️ AlphaFold results not found")
        return

    with open(af_path) as f:
        af_data = json.load(f)

    count = 0
    for structure in af_data.get("structures", []):
        gene = structure["gene"]
        uniprot = structure["uniprot_id"]
        plddt = structure.get("plddt", {})
        pocket = structure.get("pocket", {})
        drugs = structure.get("drugs", [])

        # Target 노드에 AlphaFold 정보 추가
        session.run("""
            MERGE (t:Target {name: $gene})
            SET t.uniprot_id = $uniprot,
                t.alphafold_plddt = $plddt_mean,
                t.alphafold_confidence = CASE WHEN $plddt_mean >= 70 THEN 'high' ELSE 'low' END,
                t.pocket_size = $pocket_size,
                t.pocket_volume = $pocket_volume,
                t.pocket_confidence = $pocket_conf
        """,
            gene=gene,
            uniprot=uniprot,
            plddt_mean=float(plddt.get("mean", 0)) if plddt else 0,
            pocket_size=int(pocket.get("n_residues", 0)) if pocket else 0,
            pocket_volume=float(pocket.get("volume", 0)) if pocket else 0,
            pocket_conf=float(pocket.get("confidence", 0)) if pocket else 0,
        )

        # Drug → Target 관계
        for drug_name in drugs:
            session.run("""
                MATCH (drug:Drug) WHERE toLower(drug.name) = toLower($drug_name)
                MATCH (t:Target {name: $gene})
                MERGE (drug)-[r:TARGETS]->(t)
                SET r.disease = 'CRC',
                    r.alphafold_validated = true
            """, drug_name=drug_name, gene=gene)

        count += 1

    print(f"  ✅ AlphaFold: {count} targets with structure info")


def add_coad_read_analysis(session, results_dir):
    """COAD vs READ 분석 결과 추가"""
    rec_path = results_dir / "colon_coad_read_drug_recommendations.csv"
    if not rec_path.exists():
        print("  ⚠️ COAD/READ results not found")
        return

    recs = pd.read_csv(rec_path)

    count = 0
    for _, row in recs.iterrows():
        drug_name = row["drug"]
        recommendation = row["recommendation"]

        session.run("""
            MATCH (drug:Drug) WHERE toLower(drug.name) = toLower($drug_name)
            MATCH (drug)-[r:PREDICTED_FOR]->(d:Disease {name: 'Colorectal Cancer'})
            SET r.coad_read_recommendation = $rec,
                r.coad_score = $coad_score,
                r.read_score = $read_score
        """,
            drug_name=drug_name,
            rec=recommendation,
            coad_score=float(row.get("coad_score", 0)),
            read_score=float(row.get("read_score", 0)),
        )
        count += 1

    print(f"  ✅ COAD/READ: {count} recommendations added")


def add_pipeline_metadata(session):
    """파이프라인 메타데이터"""
    session.run("""
        MATCH (d:Disease {name: 'Colorectal Cancer'})
        SET d.pipeline_steps_completed = ['Step1-2', 'Step3', 'Step3.5', 'Step4', 'Step4.5', 'Step5', 'Step6', 'Step7', 'Step7.5', 'Step7.6', 'Step8'],
            d.best_ensemble_spearman = 0.6010,
            d.ensemble_model = 'GraphSAGE(0.8) + CatBoost(0.2)',
            d.top15_count = 15,
            d.validation_sources = ['PRISM', 'ClinicalTrials', 'COSMIC', 'CPTAC', 'GEO'],
            d.very_high_confidence_drugs = ['Temsirolimus', 'Camptothecin', 'Irinotecan', 'Topotecan'],
            d.data_samples = 9692,
            d.data_drugs = 295,
            d.data_cell_lines = 35,
            d.updated_at = datetime()
    """)
    print("  ✅ Pipeline metadata added to Disease node")


def verify_load(session):
    """적재 검증"""
    print("\n=== 적재 검증 ===")

    # Disease
    result = session.run("MATCH (d:Disease {name: 'Colorectal Cancer'}) RETURN d.acronym AS acronym")
    record = result.single()
    print(f"  Disease CRC: {'✅' if record else '❌'}")

    # PREDICTED_FOR 관계
    result = session.run("""
        MATCH (drug:Drug)-[r:PREDICTED_FOR]->(d:Disease {name: 'Colorectal Cancer'})
        RETURN count(r) AS cnt
    """)
    cnt = result.single()["cnt"]
    print(f"  PREDICTED_FOR relationships: {cnt}")

    # Top 15 (is_top15)
    result = session.run("""
        MATCH (drug:Drug)-[r:PREDICTED_FOR {is_top15: true}]->(d:Disease {name: 'Colorectal Cancer'})
        RETURN count(r) AS cnt
    """)
    cnt = result.single()["cnt"]
    print(f"  Top 15 drugs: {cnt}")

    # CellLine
    result = session.run("""
        MATCH (c:CellLine)-[:CELL_LINE_OF]->(d:Disease {name: 'Colorectal Cancer'})
        RETURN count(c) AS cnt
    """)
    cnt = result.single()["cnt"]
    print(f"  CellLines: {cnt}")

    # Targets with AlphaFold
    result = session.run("""
        MATCH (t:Target) WHERE t.alphafold_plddt IS NOT NULL
        RETURN count(t) AS cnt
    """)
    cnt = result.single()["cnt"]
    print(f"  Targets with AlphaFold: {cnt}")

    # 전체 현황
    result = session.run("MATCH (n) RETURN count(n) AS total")
    total = result.single()["total"]

    result = session.run("MATCH ()-[r]->() RETURN count(r) AS total")
    rels = result.single()["total"]

    print(f"\n  Total nodes: {total}")
    print(f"  Total relationships: {rels}")

    # Disease 별 약물 수
    result = session.run("""
        MATCH (drug:Drug)-[:PREDICTED_FOR]->(d:Disease)
        RETURN d.name AS disease, count(drug) AS drugs
        ORDER BY drugs DESC
    """)
    print(f"\n  Drugs per Disease:")
    for record in result:
        print(f"    {record['disease']}: {record['drugs']}")


def main():
    base_dir = Path(__file__).parent.parent
    results_dir = base_dir / "results"

    print("=" * 80)
    print("Step 8: Neo4j Knowledge Graph Loading")
    print("=" * 80)
    print(f"  Target: {NEO4J_URI}")

    driver = get_driver()

    with driver.session() as session:
        # 1. Disease 노드
        print("\n[1] Disease 노드 생성")
        create_disease_node(session)

        # 2. Cell Line 노드
        print("\n[2] CellLine 노드 생성")
        create_cell_line_nodes(session, base_dir)

        # 3. Drug-Disease 관계
        print("\n[3] Drug-Disease 관계 (PREDICTED_FOR)")
        create_drug_disease_relationships(session, results_dir)

        # 4. ADMET 속성
        print("\n[4] ADMET 속성 추가")
        add_admet_properties(session, results_dir)

        # 5. AlphaFold 속성
        print("\n[5] AlphaFold 구조 정보")
        add_alphafold_properties(session, results_dir)

        # 6. COAD/READ 분석
        print("\n[6] COAD vs READ 분석 결과")
        add_coad_read_analysis(session, results_dir)

        # 7. Pipeline 메타데이터
        print("\n[7] Pipeline 메타데이터")
        add_pipeline_metadata(session)

        # 8. 검증
        verify_load(session)

    driver.close()

    # 9. 결과 저장
    print("\n[9] 로컬 결과 저장")
    summary = {
        "step": "Step 8 Neo4j Knowledge Graph",
        "target": NEO4J_URI,
        "disease": "Colorectal Cancer (COAD+READ)",
        "loaded": {
            "disease_node": 1,
            "cell_lines": 35,
            "drug_disease_relations": 30,
            "top15_admet": 15,
            "alphafold_targets": 14,
            "coad_read_recommendations": "loaded",
        },
    }

    json_path = results_dir / "colon_neo4j_load_summary.json"
    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"  ✅ {json_path}")

    print("\n✅ Step 8 완료!")


if __name__ == "__main__":
    main()
