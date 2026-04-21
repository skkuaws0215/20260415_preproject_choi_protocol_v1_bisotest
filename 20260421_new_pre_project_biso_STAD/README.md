# 20260421_new_pre_project_biso_STAD

위암(TCGA-STAD) drug repurposing 파이프라인 프로젝트입니다.  
코드는 Colon/Lung 파이프라인 구조를 재사용하고, 데이터 경로만 STAD 기준으로 운영합니다.

## 현재 상태


| Stage    | Status                              |
| -------- | ----------------------------------- |
| Step 0-1 | `Stad_raw` 기반 raw 수집/동기화 스크립트 구성 완료 |
| Step 2   | 전처리 실행 완료 (`run_step2_stad.sh`)     |
| Step 6   | STAD config 기반 외부검증 실행 경로 구성 완료     |


## 핵심 제약

- `curated_data/`는 raw mirror로 취급하며 **읽기 전용**입니다. 수정/삭제 금지.
- 전처리/가공 산출물은 `curated_data/processed/`, `data/`, `reports/`, `logs/`에만 생성합니다.
- LINCS는 `configs/lincs_source.json` 기준으로 `GSE92742`를 사용합니다.
- 현재 `GSE92742` 기준 usable STAD cell은 `AGS` 1개입니다.  
이후 분석/해석 문서에 **coverage limitation(AGS-only)** 를 명시해야 합니다.

## 주요 참고 문서

- 운영 컨텍스트: [configs/CONTEXT.md](configs/CONTEXT.md)
- STAD 재현 절차: [STAD_reproduction_protocol.md](STAD_reproduction_protocol.md)
- 상위(계속 업데이트) 프로토콜: `/Users/skku_aws2_14/Downloads/drug_repurposing_pipeline_protocol (2).md`
- 코드 템플릿: [20260420_new_pre_project_biso_Colon](../20260420_new_pre_project_biso_Colon), [20260416_new_pre_project_biso_Lung](../20260416_new_pre_project_biso_Lung)

## 빠른 실행 순서

### 1) Raw 동기화

```bash
cd 20260421_new_pre_project_biso_STAD
./scripts/parallel_download_stad.sh
```

### 2) LINCS GSE92742 정렬 (필요 시)

`Stad_raw/LInc1000`에 `GSE92742`가 없고, 같은 머신의 Colon 프로젝트에 이미 있으면:

```bash
./scripts/link_lincs_gse92742_from_colon.sh
```

### 3) 전처리 (Step 2)

```bash
./scripts/run_step2_stad.sh
```

### 4) LINCS cell_id 재검증/재생성 (GSE92742 기준)

```bash
python3 scripts/rebuild_stad_lincs_cell_ids_gse92742.py --project-root .
```

산출물:

- `configs/stad_lincs_cell_ids.json`
- `reports/lincs/stad_lincs_cell_id_review.csv`
- `reports/lincs/stad_lincs_cell_id_qc.json`

## Step 6 외부검증 (STAD)

```bash
SYNC_S3=1 ./scripts/run_step6_stad.sh
```

주의:

- `results/stad_top30_phase2b_catboost_with_names.csv`
- `results/stad_top30_phase2c_catboost_with_names.csv`
- `results/stad_top30_unified_2b_and_2c_with_names.csv`

위 3개가 있어야 Step 6이 끝까지 실행됩니다.

## 현재 확인된 사실 (LINCS coverage)

- `GSE92742` `cell_info`에서 stomach/gastric annotation을 가진 cell_id는 `AGS`만 확인됨
- `sig_info`(`pert_type == trt_cp`)에서도 `AGS`만 usable (`362 signatures`)
- 따라서 STAD 분석 시 LINCS 기반 evidence는 AGS 중심으로 해석해야 하며, 일반화 한계를 명시해야 함

