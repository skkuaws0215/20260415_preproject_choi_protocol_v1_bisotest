#!/usr/bin/env python3
"""
Step 9: LLM 기반 약물 재창출 근거 생성

Top 15 약물 각각에 대해 전체 파이프라인 검증 근거를 종합하여
Ollama (llama3.1) 로 상세 Explanation 생성.

포함 근거:
  - 예측 모델 (앙상블 Spearman, pred IC50)
  - 외부 검증 (PRISM, ClinicalTrials, COSMIC, CPTAC, GEO)
  - ADMET (22 assay, safety score, verdict)
  - AlphaFold (pLDDT, binding pocket)
  - COAD vs READ 분석
  - 약물 카테고리 (FDA_APPROVED_CRC / REPURPOSING / CLINICAL_TRIAL / RESEARCH)

입력:
  - results/colon_final_top15.csv
  - results/colon_comprehensive_drug_scores.csv
  - results/colon_admet_summary.json
  - results/alphafold_validation/alphafold_validation_results.json
  - results/colon_coad_read_analysis.json

출력:
  - results/colon_drug_explanations.json
  - results/colon_drug_explanations_report.md
"""

import json
import subprocess
import pandas as pd
import numpy as np
from pathlib import Path
import time


def query_ollama(prompt, model="llama3.1"):
    """Ollama 로컬 LLM 에 질의"""
    try:
        result = subprocess.run(
            ["ollama", "run", model],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f"ERROR: {result.stderr}"
    except subprocess.TimeoutExpired:
        return "ERROR: Timeout (120s)"
    except Exception as e:
        return f"ERROR: {e}"


def load_all_evidence(results_dir):
    """모든 검증 근거 로드"""
    evidence = {}

    # Top 15
    top15 = pd.read_csv(results_dir / "colon_final_top15.csv")
    evidence["top15"] = top15

    # Comprehensive validation
    comp_path = results_dir / "colon_comprehensive_drug_scores.csv"
    if comp_path.exists():
        evidence["validation"] = pd.read_csv(comp_path)

    # ADMET
    admet_path = results_dir / "colon_admet_summary.json"
    if admet_path.exists():
        with open(admet_path) as f:
            evidence["admet"] = json.load(f)

    # AlphaFold
    af_path = results_dir / "alphafold_validation" / "alphafold_validation_results.json"
    if af_path.exists():
        with open(af_path) as f:
            evidence["alphafold"] = json.load(f)

    # COAD/READ
    cr_path = results_dir / "colon_coad_read_analysis.json"
    if cr_path.exists():
        with open(cr_path) as f:
            evidence["coad_read"] = json.load(f)

    # ClinicalTrials 상세
    ct_path = results_dir / "colon_clinical_trials_validation_results.json"
    if ct_path.exists():
        with open(ct_path) as f:
            evidence["clinical_trials"] = json.load(f)

    return evidence


def build_drug_context(drug_name, evidence):
    """약물별 전체 근거 컨텍스트 구성"""
    context = {}

    # Top 15 정보
    top15 = evidence["top15"]
    name_col = "drug_name" if "drug_name" in top15.columns else "DRUG_NAME"
    drug_row = top15[top15[name_col] == drug_name]

    if len(drug_row) == 0:
        return None

    row = drug_row.iloc[0]
    context["rank"] = int(row.get("recommendation_rank", row.get("rank", 0)))
    context["pred_ic50"] = round(float(row.get("pred_ic50_mean", 0)), 4)
    context["target"] = str(row.get("target", ""))
    context["target_pathway"] = str(row.get("target_pathway", ""))
    context["category"] = str(row.get("usage_category", ""))
    context["safety_score"] = round(float(row.get("safety_score", 0)), 2)
    context["verdict"] = str(row.get("verdict", ""))
    context["mw"] = row.get("mw", "?")
    context["logp"] = row.get("logp", "?")
    context["tpsa"] = row.get("tpsa", "?")
    context["ct_max_phase"] = str(row.get("ct_max_phase", ""))

    # Validation scores
    if "validation" in evidence:
        val_df = evidence["validation"]
        val_row = val_df[val_df["drug_name"] == drug_name]
        if len(val_row) > 0:
            vr = val_row.iloc[0]
            context["validation_count"] = int(vr.get("validation_count", 0))
            context["confidence"] = str(vr.get("confidence", ""))
            context["prism"] = bool(vr.get("prism", 0))
            context["clinical_trials"] = bool(vr.get("clinical_trials", 0))
            context["cosmic"] = bool(vr.get("cosmic", 0))
            context["cptac"] = bool(vr.get("cptac", 0))
            context["geo"] = bool(vr.get("geo", 0))

    # ClinicalTrials 상세
    if "clinical_trials" in evidence:
        ct = evidence["clinical_trials"]
        if "matched_details" in ct:
            for m in ct["matched_details"]:
                if m["drug_name"] == drug_name:
                    context["ct_phases"] = m.get("phases", [])
                    context["ct_n_trials"] = m.get("n_trials", 0)
                    break

    # AlphaFold
    if "alphafold" in evidence:
        af = evidence["alphafold"]
        for structure in af.get("structures", []):
            if drug_name in structure.get("drugs", []):
                context["alphafold_gene"] = structure["gene"]
                context["alphafold_uniprot"] = structure["uniprot_id"]
                plddt = structure.get("plddt", {})
                context["alphafold_plddt"] = plddt.get("mean", 0) if plddt else 0
                pocket = structure.get("pocket", {})
                context["pocket_size"] = pocket.get("n_residues", 0) if pocket else 0
                context["pocket_volume"] = pocket.get("volume", 0) if pocket else 0
                break

    # COAD/READ
    if "coad_read" in evidence:
        cr = evidence["coad_read"]
        for rec in cr.get("drug_recommendations", []):
            if rec["drug"] == drug_name:
                context["coad_read_rec"] = rec["recommendation"]
                context["coad_read_detail"] = rec["detail"]
                break

    return context


def build_prompt(drug_name, context):
    """LLM 프롬프트 생성"""

    # 카테고리 설명
    category_desc = {
        "FDA_APPROVED_CRC": "이미 대장암(CRC)에서 FDA 승인/사용 중인 약물. 모델 검증 목적.",
        "REPURPOSING_CANDIDATE": "다른 암종에서 승인되었으나 대장암에는 아직 적응증이 없는 약물. 약물 재창출 핵심 후보.",
        "CLINICAL_TRIAL": "대장암 관련 임상시험이 진행 중인 약물. 재창출 가능성 높음.",
        "RESEARCH_PHASE": "전임상/연구 단계 약물. 추가 연구 필요한 탐색적 후보.",
    }

    cat = context.get("category", "Unknown")
    cat_desc = category_desc.get(cat, "분류 정보 없음")

    # 검증 통과 목록
    validations = []
    if context.get("prism"):
        validations.append("PRISM (독립 약물 스크린에서 대장암 세포주 감수성 확인)")
    if context.get("clinical_trials"):
        phase = context.get("ct_max_phase", "")
        n_trials = context.get("ct_n_trials", 0)
        validations.append(f"ClinicalTrials.gov ({n_trials}개 임상시험, 최대 {phase})")
    if context.get("cosmic"):
        validations.append("COSMIC (Cancer Gene Census 타겟 유전자 매칭)")
    if context.get("cptac"):
        validations.append("CPTAC (대장암 환자 mRNA에서 타겟 유전자 발현 확인)")
    if context.get("geo"):
        validations.append("GEO GSE39582 (585명 대장암 코호트에서 타겟 발현 확인)")

    val_text = "\n".join(f"  - {v}" for v in validations) if validations else "  - 외부 검증 소스 매칭 없음"

    # AlphaFold
    af_text = ""
    if context.get("alphafold_gene"):
        af_text = f"""
AlphaFold 구조 검증:
  - 타겟 단백질: {context['alphafold_gene']} (UniProt: {context['alphafold_uniprot']})
  - 구조 신뢰도 (pLDDT): {context.get('alphafold_plddt', 0):.1f} (70 이상이면 high confidence)
  - 결합 포켓: {context.get('pocket_size', 0)} residues, 볼륨 {context.get('pocket_volume', 0):.0f} ų"""

    # COAD/READ
    cr_text = ""
    if context.get("coad_read_rec"):
        cr_text = f"""
COAD vs READ 분석:
  - 추천: {context['coad_read_rec']}
  - 근거: {context.get('coad_read_detail', '')}"""

    prompt = f"""You are a pharmaceutical research expert specializing in drug repurposing for colorectal cancer (CRC).

Based on the following evidence from our computational drug repurposing pipeline, write a detailed scientific explanation for why {drug_name} is recommended as a drug repurposing candidate for colorectal cancer.

Write in Korean (한국어). Be specific, cite the evidence provided, and explain the scientific rationale.

=== 약물 정보 ===
약물명: {drug_name}
추천 순위: #{context['rank']}
카테고리: {cat} — {cat_desc}
예측 IC50 (낮을수록 효과적): {context['pred_ic50']}
타겟: {context.get('target', 'N/A')}
타겟 경로: {context.get('target_pathway', 'N/A')}

=== ADMET 안전성 ===
Safety Score: {context['safety_score']} (6.0 이상 PASS, 4.0~6.0 WARNING, 4.0 미만 FAIL)
판정: {context['verdict']}
분자량: {context.get('mw', '?')}, LogP: {context.get('logp', '?')}, TPSA: {context.get('tpsa', '?')}

=== 외부 검증 ({context.get('validation_count', 0)}/5 소스 통과, 신뢰도: {context.get('confidence', '?')}) ===
{val_text}
{af_text}
{cr_text}

=== 작성 요구사항 ===
1. 이 약물이 대장암에 왜 효과적일 수 있는지 과학적 근거를 설명
2. 타겟 유전자/경로와 대장암의 관계
3. 외부 검증 결과가 이 추천을 어떻게 뒷받침하는지
4. ADMET 안전성 평가 결과
5. AlphaFold 구조 검증이 약물-타겟 결합 가능성을 어떻게 지지하는지
6. COAD(결장암) vs READ(직장암) 적합성
7. 카테고리 관점에서의 약물 재창출 의의
8. 향후 필요한 추가 연구/검증 제안

500자 이내로 간결하게 작성하되, 근거를 명확히 인용하세요.
"""
    return prompt


def main():
    base_dir = Path(__file__).parent.parent
    results_dir = base_dir / "results"

    print("=" * 80)
    print("Step 9: LLM Drug Repurposing Explanation (Ollama llama3.1)")
    print("=" * 80)

    # 1. 전체 근거 로드
    print("\n[1] 근거 데이터 로드")
    evidence = load_all_evidence(results_dir)
    print(f"  Top 15: {len(evidence['top15'])} drugs")
    print(f"  Evidence sources: {list(evidence.keys())}")

    # 2. 약물별 Explanation 생성
    print("\n[2] 약물별 Explanation 생성")

    top15 = evidence["top15"]
    name_col = "drug_name" if "drug_name" in top15.columns else "DRUG_NAME"

    explanations = []
    total = len(top15)

    for idx, (_, row) in enumerate(top15.iterrows(), 1):
        drug_name = row[name_col]
        category = row.get("usage_category", "?")

        print(f"\n  [{idx}/{total}] {drug_name} ({category})")

        # 컨텍스트 구성
        context = build_drug_context(drug_name, evidence)
        if context is None:
            print(f"    ⚠️ Context 생성 실패")
            continue

        # 프롬프트 생성
        prompt = build_prompt(drug_name, context)

        # LLM 질의
        print(f"    Querying Ollama...", end=" ", flush=True)
        start_time = time.time()
        explanation = query_ollama(prompt)
        elapsed = time.time() - start_time
        print(f"Done ({elapsed:.1f}s, {len(explanation)} chars)")

        explanations.append({
            "rank": context["rank"],
            "drug_name": drug_name,
            "category": category,
            "pred_ic50": context["pred_ic50"],
            "target": context.get("target", ""),
            "safety_score": context["safety_score"],
            "verdict": context["verdict"],
            "validation_count": context.get("validation_count", 0),
            "confidence": context.get("confidence", ""),
            "coad_read": context.get("coad_read_rec", ""),
            "explanation": explanation,
            "context": context,
        })

    # 3. 저장 (JSON)
    print("\n\n[3] 저장")

    json_path = results_dir / "colon_drug_explanations.json"
    with open(json_path, "w") as f:
        json.dump(explanations, f, indent=2, ensure_ascii=False, default=str)
    print(f"  ✅ {json_path}")

    # 4. Markdown 보고서 생성
    md_lines = [
        "# Colon (COAD+READ) 약물 재창출 — Top 15 추천 보고서\n",
        f"**생성일**: 2026-04-24\n",
        f"**파이프라인**: Drug Repurposing Pipeline v1.4\n",
        f"**앙상블 성능**: Spearman 0.6010 (GraphSAGE×0.8 + CatBoost×0.2)\n",
        f"**외부 검증**: PRISM, ClinicalTrials, COSMIC, CPTAC, GEO (5대 소스)\n",
        f"**ADMET**: 초이 프로토콜 22 assay + Tanimoto matching\n",
        f"**구조 검증**: AlphaFold + binding pocket detection\n",
        "\n---\n",
        "\n## 카테고리 분류\n",
        "| 카테고리 | 설명 | 약물 수 |",
        "|----------|------|---------|",
        f"| FDA_APPROVED_CRC | CRC 에서 이미 사용 중 (모델 검증) | {sum(1 for e in explanations if e['category']=='FDA_APPROVED_CRC')} |",
        f"| REPURPOSING_CANDIDATE | 다른 암 승인 → CRC 재창출 🎯 | {sum(1 for e in explanations if e['category']=='REPURPOSING_CANDIDATE')} |",
        f"| CLINICAL_TRIAL | CRC 임상시험 진행 중 | {sum(1 for e in explanations if e['category']=='CLINICAL_TRIAL')} |",
        f"| RESEARCH_PHASE | 전임상/연구 단계 | {sum(1 for e in explanations if e['category']=='RESEARCH_PHASE')} |",
        "\n---\n",
    ]

    for exp in explanations:
        cat_icon = {
            "FDA_APPROVED_CRC": "✅",
            "REPURPOSING_CANDIDATE": "🎯",
            "CLINICAL_TRIAL": "🔬",
            "RESEARCH_PHASE": "📝",
        }.get(exp["category"], "")

        md_lines.extend([
            f"\n## #{exp['rank']} {exp['drug_name']} {cat_icon}\n",
            f"**카테고리**: {exp['category']}\n",
            f"**타겟**: {exp['target']}\n",
            f"**예측 IC50**: {exp['pred_ic50']}\n",
            f"**ADMET**: Safety Score {exp['safety_score']}, {exp['verdict']}\n",
            f"**검증**: {exp['validation_count']}/5 ({exp['confidence']})\n",
            f"**COAD/READ**: {exp.get('coad_read', 'N/A')}\n",
            f"\n### 추천 근거\n",
            f"\n{exp['explanation']}\n",
            "\n---\n",
        ])

    md_path = results_dir / "colon_drug_explanations_report.md"
    with open(md_path, "w") as f:
        f.write("\n".join(md_lines))
    print(f"  ✅ {md_path}")

    # 5. 요약
    print("\n" + "=" * 80)
    print("Step 9 Summary")
    print("=" * 80)
    print(f"  Total explanations: {len(explanations)}")
    print(f"  Categories:")
    for cat in ["FDA_APPROVED_CRC", "REPURPOSING_CANDIDATE", "CLINICAL_TRIAL", "RESEARCH_PHASE"]:
        cnt = sum(1 for e in explanations if e["category"] == cat)
        if cnt > 0:
            print(f"    {cat}: {cnt}")

    print(f"\n  Report: {md_path}")
    print("\n✅ Step 9 완료!")


if __name__ == "__main__":
    main()
