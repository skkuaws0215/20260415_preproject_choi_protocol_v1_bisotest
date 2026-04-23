"""
Step 1-2 Data & QC 뷰 — 전처리 결과 + QC 리포트 시각화.
"""

import json
import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path


BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data"
CURATED_DIR = BASE_DIR / "curated_data"
REPORTS_DIR = BASE_DIR / "reports"


def render_step2_data_qc():
    """Tab 2 메인 렌더"""

    # ─── Section 1: 데이터 개요 ───
    st.subheader("📊 데이터 개요")

    col1, col2, col3, col4 = st.columns(4)

    # y_train 로드
    y_path = DATA_DIR / "y_train.npy"
    if y_path.exists():
        y = np.load(y_path)
        with col1:
            st.metric("Total Samples", f"{len(y):,}")
        with col2:
            st.metric("y mean", f"{y.mean():.4f}")
        with col3:
            st.metric("y std", f"{y.std():.4f}")
        with col4:
            st.metric("y range", f"{y.min():.2f} ~ {y.max():.2f}")

    # ─── Section 2: 입력 파일 현황 ───
    st.subheader("📁 학습 입력 파일")

    file_info = []
    for name in ["X_numeric.npy", "X_numeric_smiles.npy", "X_numeric_context_smiles.npy", "y_train.npy"]:
        fpath = DATA_DIR / name
        if fpath.exists():
            arr = np.load(fpath)
            size_mb = fpath.stat().st_size / 1024 / 1024
            file_info.append({
                "File": name,
                "Shape": str(arr.shape),
                "Dtype": str(arr.dtype),
                "Size (MB)": f"{size_mb:.1f}",
            })

    if file_info:
        st.dataframe(pd.DataFrame(file_info), use_container_width=True, hide_index=True)

    # ─── Section 3: curated_data 구조 ───
    st.subheader("📂 curated_data 구조")

    if CURATED_DIR.exists():
        subdirs = sorted([d.name for d in CURATED_DIR.iterdir() if d.is_dir()])
        cols = st.columns(5)
        for i, name in enumerate(subdirs):
            with cols[i % 5]:
                subdir = CURATED_DIR / name
                file_count = len(list(subdir.rglob("*")))
                st.metric(name, f"{file_count} files")
    else:
        st.warning("curated_data/ 디렉토리가 없습니다.")

    # ─── Section 4: QC 리포트 ───
    st.subheader("🔍 QC 리포트")

    if REPORTS_DIR.exists():
        # 통합 QC 리포트
        integrated_qc = REPORTS_DIR / "step2_integrated_qc_report.json"
        if integrated_qc.exists():
            with open(integrated_qc) as f:
                qc_data = json.load(f)

            if isinstance(qc_data, dict):
                # 전체 결과 요약
                if "overall_status" in qc_data:
                    status = qc_data["overall_status"]
                    if status == "ALL PASSED" or status == "PASS":
                        st.success(f"✅ 통합 QC: {status}")
                    else:
                        st.error(f"❌ 통합 QC: {status}")

                # 상세 항목 expander
                with st.expander("QC 상세 항목", expanded=False):
                    st.json(qc_data)

        # 개별 리포트 목록
        report_files = sorted(REPORTS_DIR.glob("*.json")) + sorted(REPORTS_DIR.glob("*.txt")) + sorted(REPORTS_DIR.glob("*.csv"))
        if report_files:
            with st.expander(f"📄 리포트 파일 목록 ({len(report_files)} 개)", expanded=False):
                for rfile in report_files:
                    size_kb = rfile.stat().st_size / 1024
                    st.text(f"  {rfile.name} ({size_kb:.1f} KB)")
    else:
        st.info("reports/ 디렉토리가 없습니다.")

    # ─── Section 5: Cell Line 매칭 ───
    st.subheader("🧬 Cell Line 매칭")

    matched_csv = REPORTS_DIR / "matched_colon_cell_lines.csv"
    if matched_csv.exists():
        df_cells = pd.read_csv(matched_csv)
        col1, col2 = st.columns(2)
        with col1:
            st.metric("매칭된 Cell Lines", len(df_cells))
        with col2:
            if "cell_line_name" in df_cells.columns:
                st.metric("고유 Cell Lines", df_cells["cell_line_name"].nunique())

        with st.expander("Cell Line 목록", expanded=False):
            st.dataframe(df_cells, use_container_width=True, hide_index=True)

    # ─── Section 6: Scaffold 통계 ───
    st.subheader("🔬 Scaffold 통계")

    scaffold_stats = DATA_DIR / "scaffold_stats.json"
    if scaffold_stats.exists():
        with open(scaffold_stats) as f:
            stats = json.load(f)

        if isinstance(stats, dict):
            cols = st.columns(3)
            keys = list(stats.keys())[:6]
            for i, key in enumerate(keys):
                with cols[i % 3]:
                    val = stats[key]
                    if isinstance(val, (int, float)):
                        st.metric(key, f"{val:,}" if isinstance(val, int) else f"{val:.4f}")
                    else:
                        st.metric(key, str(val))

            with st.expander("전체 Scaffold 통계", expanded=False):
                st.json(stats)
