"""
Step 4 Modeling 탭 (Tab 4) — 대시보드 메인 탭.

전체 129 experiments (30 JSON files) 를 다각도로 보여줌:
    1. Summary Metrics — 지표 6개 카드
    2. Filters — 인터랙티브 필터 (Split, Phase, Category, Model)
    3. Full Ranking Table — 필터링된 결과 표 (정렬 가능)
    4. Visualizations — Bar / Heatmap / Box (Plotly)
    5. Drill-down — 선택한 실험의 Fold별 상세

현재 구현: Section 1-2 (다음 단계에서 3-5 확장 예정)
"""

from __future__ import annotations

from typing import List

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.parsers import (
    get_summary_stats,
    load_step4_results,
)
from dashboard.utils import (
    CATEGORY_ORDER,
    PHASE_ORDER,
    SPLIT_ORDER,
    render_metric_card,
)


# ─────────────────────────────────────────────────────────────────────────────
# Section 1: Summary Metrics (6개 카드)
# ─────────────────────────────────────────────────────────────────────────────


def _section_summary_metrics(df: pd.DataFrame) -> None:
    """상단 요약 카드 6개 (2행 × 3열)."""
    st.subheader("📊 Summary")

    stats = get_summary_stats(df)

    # 첫 줄
    row1 = st.columns(3)

    with row1[0]:
        render_metric_card(
            label="Total Experiments",
            value=f"{stats['total_experiments']}",
            sub=f"{stats['total_files']} JSON · {stats['total_models']} models",
        )

    best_drug = stats.get("best_per_split", {}).get("Drug Split")
    with row1[1]:
        if best_drug:
            std_str = (
                f"±{best_drug['val_spearman_std']:.4f}"
                if best_drug["val_spearman_std"]
                else ""
            )
            render_metric_card(
                label="Best Drug Split",
                value=f"{best_drug['val_spearman_mean']:.4f}",
                sub=f"{best_drug['model']} · {best_drug['phase']} {std_str}",
                variant="success",
            )
        else:
            render_metric_card(label="Best Drug Split", value="N/A")

    best_scaf = stats.get("best_per_split", {}).get("Scaffold Split")
    with row1[2]:
        if best_scaf:
            std_str = (
                f"±{best_scaf['val_spearman_std']:.4f}"
                if best_scaf["val_spearman_std"]
                else ""
            )
            render_metric_card(
                label="Best Scaffold Split",
                value=f"{best_scaf['val_spearman_mean']:.4f}",
                sub=f"{best_scaf['model']} · {best_scaf['phase']} {std_str}",
                variant="success",
            )
        else:
            render_metric_card(label="Best Scaffold Split", value="N/A")

    # 둘째 줄
    row2 = st.columns(3)

    best_5f = stats.get("best_per_split", {}).get("5-Fold CV")
    with row2[0]:
        if best_5f:
            std_str = (
                f"±{best_5f['val_spearman_std']:.4f}"
                if best_5f["val_spearman_std"]
                else ""
            )
            render_metric_card(
                label="Best 5-Fold CV",
                value=f"{best_5f['val_spearman_mean']:.4f}",
                sub=f"{best_5f['model']} · {best_5f['phase']} {std_str} ⚠️ leakage suspected",
                variant="warning",
            )
        else:
            render_metric_card(label="Best 5-Fold CV", value="N/A")

    with row2[1]:
        overfit_variant = "danger" if stats["overfitting_pct"] > 50 else "warning"
        render_metric_card(
            label="Overfitting Flags",
            value=f"{stats['overfitting_count']}",
            sub=f"{stats['overfitting_pct']:.1f}% of ML/DL experiments",
            variant=overfit_variant,
        )

    with row2[2]:
        unstable_variant = "danger" if stats["unstable_pct"] > 30 else "warning"
        render_metric_card(
            label="Unstable Flags",
            value=f"{stats['unstable_count']}",
            sub=f"{stats['unstable_pct']:.1f}% (std ≥ 0.05)",
            variant=unstable_variant,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Section 2: Filters
# ─────────────────────────────────────────────────────────────────────────────


def _section_filters(df: pd.DataFrame) -> pd.DataFrame:
    """필터 UI + 필터 적용된 DataFrame 반환."""
    st.subheader("🎛️ Filters")

    # 사용 가능한 옵션 (실제 DataFrame 기반)
    available_splits = [s for s in SPLIT_ORDER if s in df["split"].unique()]
    available_phases = [p for p in PHASE_ORDER if p in df["phase"].unique()]
    available_categories = [c for c in CATEGORY_ORDER if c in df["category"].unique()]

    # 4열 레이아웃
    c1, c2, c3, c4 = st.columns([2, 2, 2, 3])

    with c1:
        selected_splits = st.multiselect(
            "Split",
            options=available_splits,
            default=(
                ["Drug Split", "Scaffold Split"]
                if set(["Drug Split", "Scaffold Split"]).issubset(available_splits)
                else available_splits
            ),
            help="기본값: Drug + Scaffold (Primary). 필요시 5-Fold 추가.",
        )

    with c2:
        selected_phases = st.multiselect(
            "Phase",
            options=available_phases,
            default=available_phases,
        )

    with c3:
        selected_categories = st.multiselect(
            "Category",
            options=available_categories,
            default=available_categories,
        )

    with c4:
        model_search = st.text_input(
            "Model (contains)",
            value="",
            placeholder="e.g. CatBoost, MLP, GAT",
            help="대소문자 무시, 부분 일치",
        )

    # 필터 적용
    filtered = df.copy()

    if selected_splits:
        filtered = filtered[filtered["split"].isin(selected_splits)]
    else:
        st.warning("⚠️ Split 을 최소 1개 선택하세요.")
        filtered = filtered.iloc[0:0]

    if selected_phases:
        filtered = filtered[filtered["phase"].isin(selected_phases)]

    if selected_categories:
        filtered = filtered[filtered["category"].isin(selected_categories)]

    if model_search.strip():
        pattern = model_search.strip()
        filtered = filtered[filtered["model"].str.contains(pattern, case=False, na=False)]

    # Rank 재계산 (필터 후)
    if len(filtered) > 0:
        filtered = filtered.sort_values(
            "val_spearman_mean", ascending=False, na_position="last"
        ).reset_index(drop=True)
        filtered["rank"] = filtered.index + 1

    # 필터 결과 요약
    st.caption(
        f"📋 **{len(filtered)}** experiments match filters "
        f"(out of {len(df)} total)"
    )

    return filtered


# ─────────────────────────────────────────────────────────────────────────────
# Section 3: Full Ranking Table
# ─────────────────────────────────────────────────────────────────────────────


def _format_val_spearman(row: pd.Series) -> str:
    """'0.4881 ± 0.0539' 형식."""
    mean = row["val_spearman_mean"]
    std = row["val_spearman_std"]
    if pd.isna(mean):
        return "—"
    if pd.isna(std):
        return f"{mean:.4f}"
    return f"{mean:.4f} ± {std:.4f}"


def _format_rank(rank: int) -> str:
    """Top 3는 메달, 나머지는 숫자."""
    if rank == 1:
        return "🥇 1"
    if rank == 2:
        return "🥈 2"
    if rank == 3:
        return "🥉 3"
    return f"{rank}"


def _format_flag(flag, positive_icon: str, negative_icon: str) -> str:
    """
    True → positive_icon, False → negative_icon, None/NaN → '—'.
    """
    if flag is None or pd.isna(flag):
        return "—"
    return positive_icon if flag else negative_icon


def _build_display_table(filtered: pd.DataFrame) -> pd.DataFrame:
    """Ranking 표에 사용할 표시용 DataFrame 생성."""
    if len(filtered) == 0:
        return pd.DataFrame()

    display = pd.DataFrame(
        {
            "#": filtered["rank"].apply(_format_rank),
            "Split": filtered["split"],
            "Phase": filtered["phase"],
            "Category": filtered["category"],
            "Model": filtered["model"],
            "Val Spearman": filtered.apply(_format_val_spearman, axis=1),
            "Gap": filtered["gap_mean"].apply(
                lambda x: f"{x:.4f}" if pd.notna(x) else "—"
            ),
            # Overfit: ⚠️ = overfitting 있음, ✅ = 없음
            "Overfit": filtered["overfitting_flag"].apply(
                lambda x: _format_flag(x, "⚠️", "✅")
            ),
            # Stable: ✅ = 안정, ❌ = 불안정
            "Stable": filtered["stability_flag"].apply(
                lambda x: _format_flag(x, "✅", "❌")
            ),
            "N Folds": filtered["n_folds"],
        }
    )

    return display


def _section_ranking_table(filtered: pd.DataFrame) -> None:
    """Section 3: 전체 랭킹 테이블."""
    st.subheader("📋 Ranking Table")

    if len(filtered) == 0:
        st.warning("⚠️ 필터 조건에 맞는 실험이 없습니다.")
        return

    # Top N 슬라이더
    total = len(filtered)
    default_n = min(20, total)

    col_slider, col_stats = st.columns([3, 2])
    with col_slider:
        top_n = st.slider(
            "Show Top N",
            min_value=5,
            max_value=max(total, 10),
            value=default_n,
            step=5,
            help="정렬은 Val Spearman 내림차순",
        )
    with col_stats:
        st.markdown("")  # spacer
        st.markdown("")
        st.caption(f"Showing **{min(top_n, total)}** / {total} experiments")

    # 표 렌더
    display = _build_display_table(filtered.head(top_n))

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "#": st.column_config.TextColumn("#", width="small"),
            "Split": st.column_config.TextColumn("Split", width="medium"),
            "Phase": st.column_config.TextColumn("Phase", width="small"),
            "Category": st.column_config.TextColumn("Cat", width="small"),
            "Model": st.column_config.TextColumn("Model", width="medium"),
            "Val Spearman": st.column_config.TextColumn(
                "Val Spearman ± Std", width="medium"
            ),
            "Gap": st.column_config.TextColumn(
                "Train-Val Gap",
                help="Train Spearman - Val Spearman (overfitting indicator)",
                width="small",
            ),
            "Overfit": st.column_config.TextColumn(
                "Overfit",
                help="⚠️ = overfitting detected, ✅ = OK, — = N/A (Graph)",
                width="small",
            ),
            "Stable": st.column_config.TextColumn(
                "Stable",
                help="✅ = stable (std < 0.05), ❌ = unstable, — = N/A",
                width="small",
            ),
            "N Folds": st.column_config.NumberColumn("Folds", width="small"),
        },
    )

    # CSV 다운로드
    st.markdown("")
    csv_data = filtered.drop(
        columns=["fold_details", "val_spearman_folds", "train_spearman_folds"],
        errors="ignore",
    ).to_csv(index=False).encode("utf-8")

    st.download_button(
        label="📥 Download filtered results as CSV",
        data=csv_data,
        file_name=f"colon_step4_ranking_{len(filtered)}_experiments.csv",
        mime="text/csv",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Section 4: Visualizations
# ─────────────────────────────────────────────────────────────────────────────


def _chart_bar_by_model(filtered: pd.DataFrame) -> None:
    """모델별 Val Spearman 막대 차트."""
    if len(filtered) == 0:
        st.info("No data for bar chart.")
        return

    top_df = (
        filtered.groupby(["model", "category"], as_index=False)["val_spearman_mean"]
        .mean()
        .sort_values("val_spearman_mean", ascending=False)
        .head(20)
    )

    fig = px.bar(
        top_df,
        x="model",
        y="val_spearman_mean",
        color="category",
        title="Top Models by Mean Val Spearman",
        labels={
            "model": "Model",
            "val_spearman_mean": "Val Spearman (mean)",
            "category": "Category",
        },
    )
    fig.update_layout(xaxis_tickangle=-35, height=420)
    st.plotly_chart(fig, use_container_width=True)


def _chart_heatmap_model_phase(filtered: pd.DataFrame) -> None:
    """Model × Phase Heatmap."""
    if len(filtered) == 0:
        st.info("No data for heatmap.")
        return

    pivot = filtered.pivot_table(
        index="model",
        columns="phase",
        values="val_spearman_mean",
        aggfunc="mean",
    )
    if len(pivot) == 0:
        st.info("No data for heatmap.")
        return

    fig = px.imshow(
        pivot,
        text_auto=".3f",
        aspect="auto",
        color_continuous_scale="Purples",
        title="Model × Phase Val Spearman Heatmap",
        labels={"x": "Phase", "y": "Model", "color": "Val Spearman"},
    )
    fig.update_layout(height=520)
    st.plotly_chart(fig, use_container_width=True)


def _chart_box_category(filtered: pd.DataFrame) -> None:
    """카테고리별 Val Spearman 분포(Box)."""
    if len(filtered) == 0:
        st.info("No data for category box plot.")
        return

    fig = px.box(
        filtered,
        x="category",
        y="val_spearman_mean",
        color="category",
        points="all",
        title="Category-wise Distribution of Val Spearman",
        labels={
            "category": "Category",
            "val_spearman_mean": "Val Spearman (mean)",
        },
    )
    fig.update_layout(showlegend=False, height=420)
    st.plotly_chart(fig, use_container_width=True)


def _chart_scatter_train_vs_val(filtered: pd.DataFrame) -> None:
    """Train vs Val scatter (overfitting 탐색)."""
    if len(filtered) == 0:
        st.info("No data for train-vs-val scatter.")
        return

    sub = filtered[
        filtered["train_spearman_mean"].notna() & filtered["val_spearman_mean"].notna()
    ].copy()
    if len(sub) == 0:
        st.info("No train/val pairs available.")
        return

    fig = px.scatter(
        sub,
        x="train_spearman_mean",
        y="val_spearman_mean",
        color="category",
        symbol="split",
        hover_data=["model", "phase", "split", "gap_mean"],
        title="Train vs Val Spearman (Overfitting View)",
        labels={
            "train_spearman_mean": "Train Spearman (mean)",
            "val_spearman_mean": "Val Spearman (mean)",
            "category": "Category",
            "split": "Split",
        },
    )
    fig.add_shape(
        type="line",
        x0=sub["train_spearman_mean"].min(),
        y0=sub["train_spearman_mean"].min(),
        x1=sub["train_spearman_mean"].max(),
        y1=sub["train_spearman_mean"].max(),
        line=dict(color="gray", dash="dash"),
    )
    fig.update_layout(height=460)
    st.plotly_chart(fig, use_container_width=True)


def _section_visualizations(df: pd.DataFrame, filtered: pd.DataFrame) -> None:
    """Section 4: Plotly 시각화 모음."""
    st.subheader("📈 Visualizations")

    # 필터된 데이터가 비어 있으면 전체 데이터 fallback
    viz_df = filtered if len(filtered) > 0 else df
    if len(viz_df) == 0:
        st.warning("⚠️ 시각화할 데이터가 없습니다.")
        return

    top_left, top_right = st.columns(2)
    with top_left:
        _chart_bar_by_model(viz_df)
    with top_right:
        _chart_box_category(viz_df)

    _chart_heatmap_model_phase(viz_df)
    _chart_scatter_train_vs_val(viz_df)


# ─────────────────────────────────────────────────────────────────────────────
# Section 5: Drill-down
# ─────────────────────────────────────────────────────────────────────────────


def _format_experiment_label(row: pd.Series) -> str:
    """드릴다운 선택용 라벨 생성."""
    return (
        f"#{int(row['rank'])} | {row['split']} | {row['phase']} | "
        f"{row['category']} | {row['model']} | "
        f"{row['val_spearman_mean']:.4f}"
    )


def _build_fold_table(row: pd.Series) -> pd.DataFrame:
    """선택한 실험의 fold 상세를 표 형태로 변환."""
    fold_details = row.get("fold_details", {}) or {}
    records = []

    for fold_key, metrics in fold_details.items():
        train = (metrics or {}).get("train", {}) or {}
        val = (metrics or {}).get("val", {}) or {}

        records.append(
            {
                "fold": int(fold_key) if str(fold_key).isdigit() else fold_key,
                "train_spearman": train.get("spearman"),
                "val_spearman": val.get("spearman"),
                "train_pearson": train.get("pearson"),
                "val_pearson": val.get("pearson"),
                "train_rmse": train.get("rmse"),
                "val_rmse": val.get("rmse"),
                "train_mae": train.get("mae"),
                "val_mae": val.get("mae"),
            }
        )

    if not records:
        return pd.DataFrame()

    df_fold = pd.DataFrame(records).sort_values("fold").reset_index(drop=True)
    return df_fold


def _chart_radar_train_vs_val(row: pd.Series) -> None:
    """선택 실험의 Train vs Val 평균 지표를 레이더 차트로 표시."""
    train_s = row.get("train_spearman_mean")
    val_s = row.get("val_spearman_mean")
    gap = row.get("gap_mean")

    if pd.isna(train_s) or pd.isna(val_s):
        st.info("Radar chart unavailable (missing train/val metrics).")
        return

    # Radar에서는 값이 클수록 좋은 방향으로 통일하기 위해 gap은 음수화
    categories = ["Val Spearman", "Train Spearman", "(-) Gap"]
    values = [float(val_s), float(train_s), float(-gap if pd.notna(gap) else 0.0)]

    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=values,
            theta=categories,
            fill="toself",
            name="Experiment",
        )
    )
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True)),
        showlegend=False,
        height=380,
        title="Train vs Val Radar",
    )
    st.plotly_chart(fig, use_container_width=True)


def _section_drilldown(filtered: pd.DataFrame) -> None:
    """Section 5: 선택 실험 Fold-level 드릴다운."""
    st.subheader("🔎 Drill-down")

    if len(filtered) == 0:
        st.warning("⚠️ 드릴다운할 실험이 없습니다. 필터를 확인하세요.")
        return

    options = [_format_experiment_label(row) for _, row in filtered.iterrows()]
    selected_label = st.selectbox(
        "Select an experiment",
        options=options,
        index=0,
        help="랭킹/스플릿/페이즈/모델 기준으로 실험 선택",
    )

    selected_idx = options.index(selected_label)
    selected_row = filtered.iloc[selected_idx]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Val Spearman", f"{selected_row['val_spearman_mean']:.4f}")
    c2.metric(
        "Train Spearman",
        (
            f"{selected_row['train_spearman_mean']:.4f}"
            if pd.notna(selected_row["train_spearman_mean"])
            else "—"
        ),
    )
    c3.metric(
        "Gap",
        f"{selected_row['gap_mean']:.4f}" if pd.notna(selected_row["gap_mean"]) else "—",
    )
    c4.metric("Folds", str(int(selected_row["n_folds"])))

    _chart_radar_train_vs_val(selected_row)

    fold_df = _build_fold_table(selected_row)
    if len(fold_df) == 0:
        st.info("Fold 상세 정보가 없습니다.")
        return

    st.markdown("**Fold-level metrics**")
    st.dataframe(fold_df, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# 메인 render
# ─────────────────────────────────────────────────────────────────────────────


def render() -> None:
    """Step 4 Modeling 탭 메인."""
    # 전체 데이터 로드 (Primary + 5-Fold 모두)
    df = load_step4_results(splits=["groupcv", "scaffoldcv", "5foldcv"])

    if len(df) == 0:
        st.error("❌ Step 4 결과가 없습니다. `results/` 디렉토리를 확인하세요.")
        return

    st.caption(
        f"📁 Source: `results/` · "
        f"Loaded {len(df)} experiments from {df['source_file'].nunique()} JSON files · "
        f"_Holdout results excluded — see `dashboard/TODO.md`_"
    )

    # Sections
    _section_summary_metrics(df)
    st.markdown("")

    filtered = _section_filters(df)
    st.markdown("")

    _section_ranking_table(filtered)
    st.markdown("")

    _section_visualizations(df, filtered)
    st.markdown("")

    _section_drilldown(filtered)
