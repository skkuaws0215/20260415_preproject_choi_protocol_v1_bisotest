"""
Overview 탭 (Tab 1).

파이프라인 전체 상태를 한눈에 보여줌:
  1. 핵심 지표 카드 (4개)
  2. Step 파이프라인 상태
  3. Step 4 요약
  4. 최근 업데이트

다른 탭의 상세 뷰로 들어가기 전의 "랜딩 페이지" 역할.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.parsers import load_step4_results
from dashboard.utils import (
    PIPELINE_STEPS,
    PRIMARY_SPLITS,
    STATUS_ICONS,
    STATUS_LABELS,
    render_metric_card,
    render_step_badge,
)


# ─────────────────────────────────────────────────────────────────────────────
# 섹션 1: 핵심 지표 카드
# ─────────────────────────────────────────────────────────────────────────────


def _section_key_metrics(df: pd.DataFrame) -> None:
    """Drug + Scaffold 기준 핵심 지표 4개."""
    st.subheader("📊 Key Metrics")

    # Drug / Scaffold 필터
    drug_df = df[df["split"] == "Drug Split"]
    scaf_df = df[df["split"] == "Scaffold Split"]

    # 최고 성능
    best_drug = drug_df.iloc[0] if len(drug_df) > 0 else None
    best_scaf = scaf_df.iloc[0] if len(scaf_df) > 0 else None

    # Drop 계산 (Drug 최고 → Scaffold 최고)
    drop_pct = None
    if best_drug is not None and best_scaf is not None:
        drop_pct = (
            (best_scaf["val_spearman_mean"] - best_drug["val_spearman_mean"])
            / best_drug["val_spearman_mean"]
            * 100
        )

    # 2x2 grid
    col1, col2 = st.columns(2)
    col3, col4 = st.columns(2)

    with col1:
        render_metric_card(
            label="Total Experiments",
            value=f"{len(df)}",
            sub=(
                f"across {df['source_file'].nunique()} JSON files, "
                f"{df['model'].nunique()} models"
            ),
        )

    with col2:
        if best_drug is not None:
            render_metric_card(
                label="Best Drug Split",
                value=f"{best_drug['val_spearman_mean']:.4f}",
                sub=(
                    f"{best_drug['model']} · {best_drug['phase']} "
                    f"(±{best_drug['val_spearman_std']:.4f})"
                ),
                variant="success",
            )
        else:
            render_metric_card(
                label="Best Drug Split",
                value="N/A",
                sub="no Drug Split results yet",
            )

    with col3:
        if best_scaf is not None:
            render_metric_card(
                label="Best Scaffold Split",
                value=f"{best_scaf['val_spearman_mean']:.4f}",
                sub=(
                    f"{best_scaf['model']} · {best_scaf['phase']} "
                    f"(±{best_scaf['val_spearman_std']:.4f})"
                ),
                variant="success",
            )
        else:
            render_metric_card(
                label="Best Scaffold Split",
                value="N/A",
                sub="no Scaffold Split results yet",
            )

    with col4:
        if drop_pct is not None:
            # 성능이 떨어지면 warning, 오르면 success
            variant = "warning" if drop_pct < 0 else "success"
            sign = "+" if drop_pct > 0 else ""
            render_metric_card(
                label="Scaffold vs Drug",
                value=f"{sign}{drop_pct:.1f}%",
                sub="robustness indicator (negative = performance drop)",
                variant=variant,
            )
        else:
            render_metric_card(
                label="Scaffold vs Drug",
                value="N/A",
                sub="both splits needed",
            )


# ─────────────────────────────────────────────────────────────────────────────
# 섹션 2: 파이프라인 Step 상태
# ─────────────────────────────────────────────────────────────────────────────


def _section_pipeline_status() -> None:
    """Step 1~6 진행 상황 카드."""
    st.subheader("🔧 Pipeline Status")

    for step in PIPELINE_STEPS:
        status = step["status"]
        icon = STATUS_ICONS.get(status, "❓")
        label = STATUS_LABELS.get(status, status)
        name = step["name"]
        badge = render_step_badge(status, label)

        st.markdown(
            f"{icon} &nbsp; **{name}** &nbsp; {badge}",
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# 섹션 3: Step 4 요약
# ─────────────────────────────────────────────────────────────────────────────


def _section_step4_summary(df: pd.DataFrame) -> None:
    """Step 4 Drug/Scaffold Top 모델 + 카테고리 분포."""
    st.subheader("🤖 Step 4 Modeling — Quick Summary")

    col_left, col_right = st.columns(2)

    # ── 왼쪽: Split 별 Top 3
    with col_left:
        st.markdown("**Top 3 per Split**")
        for split_name in PRIMARY_SPLITS:
            split_df = df[df["split"] == split_name].head(3)
            if len(split_df) == 0:
                st.markdown(f"- {split_name}: _no results_")
                continue

            st.markdown(f"**{split_name}**")
            for _, row in split_df.iterrows():
                st.markdown(
                    f"&nbsp;&nbsp;{row['rank']}. `{row['model']}` "
                    f"({row['phase']}) — **{row['val_spearman_mean']:.4f}** "
                    f"±{row['val_spearman_std']:.4f}"
                )

    # ── 오른쪽: 카테고리별 분포
    with col_right:
        st.markdown("**Category Distribution**")
        cat_counts = df["category"].value_counts()

        for cat, count in cat_counts.items():
            cat_df = df[df["category"] == cat]
            best_val = cat_df["val_spearman_mean"].max()
            avg_val = cat_df["val_spearman_mean"].mean()
            st.markdown(
                f"- **{cat}**: {count} experiments · "
                f"best {best_val:.4f} · avg {avg_val:.4f}"
            )

        st.markdown("")
        st.markdown("**Phase Distribution**")
        phase_counts = df["phase"].value_counts().sort_index()
        for phase, count in phase_counts.items():
            st.markdown(f"- **{phase}**: {count} experiments")


# ─────────────────────────────────────────────────────────────────────────────
# 섹션 4: Footer 정보
# ─────────────────────────────────────────────────────────────────────────────


def _section_footer(df: pd.DataFrame) -> None:
    """데이터 출처, 마지막 업데이트 등."""
    st.markdown("---")
    st.caption(
        f"📁 {df['source_file'].nunique()} JSON files parsed from `results/` · "
        f"{len(df)} experiments total · "
        f"Drug+Scaffold primary view (5-Fold CV / Holdout excluded, see `dashboard/TODO.md`)"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 메인 render 함수 (app.py 에서 호출)
# ─────────────────────────────────────────────────────────────────────────────


def render() -> None:
    """
    Overview 탭 메인 렌더.

    app.py 에서 이 함수만 호출하면 탭 전체가 그려짐.
    """
    # 데이터 로드 (Primary splits 만)
    df = load_step4_results(splits=["groupcv", "scaffoldcv"])

    if len(df) == 0:
        st.error("❌ Step 4 결과가 없습니다. `results/` 디렉토리를 확인하세요.")
        return

    # 4개 섹션 렌더
    _section_key_metrics(df)
    st.markdown("")
    _section_pipeline_status()
    st.markdown("")
    _section_step4_summary(df)
    _section_footer(df)
