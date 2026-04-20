# 20260420_new_pre_project_biso_Colon

대장암(COAD+READ) 약물 재창출 파이프라인

## 기반 프로토콜
- drug_repurposing_pipeline_protocol.md v2.3 기준
- Option B (중간 확장) 적용

## 주요 차이점 (vs Lung)
1. 전처리 단계 신규 추가
2. LINCS: GSE70138만 사용
3. Subtype 태깅 추가 (COAD/READ, MSI 평가 / RAS, BRAF 기록)
4. 외부검증에 GSE39582 추가
5. Colon_raw/ 루트 4개 parquet 배제 (원본만 사용)

## 진행 상태
- [ ] Step 1: 환경 설정 + Raw 수집 준비
- [ ] Step 2: 데이터 전처리
- [ ] Step 3: FE (Nextflow)
- [ ] Step 3.5: Feature Selection
- [ ] Step 4: 모델 학습
- [ ] Step 5: 앙상블
- [ ] Step 6: 외부 검증
- [ ] Step 7: ADMET
- [ ] Step 8: Neo4j 적재
