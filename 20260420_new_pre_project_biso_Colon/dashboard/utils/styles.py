"""
대시보드 공통 스타일 (Lung 대시보드 참고).

Lung 원본:
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%)
  metric-card: white bg + shadow + hover transform

이 모듈은 Streamlit 의 st.markdown(..., unsafe_allow_html=True) 용 CSS 를 제공.
"""

import streamlit as st

from dashboard.utils.constants import (
    COLORS,
    DISEASE,
    PROJECT_NAME,
    PROTOCOL_VERSION,
)


# ─────────────────────────────────────────────────────────────────────────────
# 전역 CSS (app.py 초반에 한 번 주입)
# ─────────────────────────────────────────────────────────────────────────────

GLOBAL_CSS = f"""
<style>
/* 헤더 그라디언트 배너 */
.app-header {{
    background: linear-gradient(135deg, {COLORS['primary']} 0%, {COLORS['secondary']} 100%);
    color: white;
    padding: 30px 40px;
    border-radius: 12px;
    margin-bottom: 24px;
    box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
}}
.app-header h1 {{
    font-size: 2.2em;
    margin: 0 0 8px 0;
    font-weight: 700;
}}
.app-header .subtitle {{
    font-size: 1.05em;
    opacity: 0.92;
    margin: 0;
}}
.app-header .meta {{
    font-size: 0.85em;
    opacity: 0.8;
    margin-top: 10px;
}}

/* 지표 카드 */
.metric-card {{
    background: white;
    padding: 20px 24px;
    border-radius: 10px;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.06);
    border-left: 4px solid {COLORS['primary']};
    margin-bottom: 16px;
}}
.metric-card .label {{
    font-size: 0.82em;
    color: {COLORS['neutral']};
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 6px;
}}
.metric-card .value {{
    font-size: 1.9em;
    font-weight: 700;
    color: #1f2937;
    line-height: 1.2;
}}
.metric-card .sub {{
    font-size: 0.85em;
    color: {COLORS['neutral']};
    margin-top: 4px;
}}

/* 성공/경고/위험 카드 변형 */
.metric-card.success {{ border-left-color: {COLORS['success']}; }}
.metric-card.warning {{ border-left-color: {COLORS['warning']}; }}
.metric-card.danger  {{ border-left-color: {COLORS['danger']}; }}

/* 파이프라인 Step 배지 */
.step-badge {{
    display: inline-block;
    padding: 4px 12px;
    border-radius: 999px;
    font-size: 0.82em;
    font-weight: 600;
    margin-right: 8px;
}}
.step-badge.done {{
    background: #d1fae5;
    color: #065f46;
}}
.step-badge.in_progress {{
    background: #fef3c7;
    color: #92400e;
}}
.step-badge.pending {{
    background: #e5e7eb;
    color: #374151;
}}
.step-badge.failed {{
    background: #fee2e2;
    color: #991b1b;
}}

/* Streamlit 기본 여백 축소 */
.block-container {{
    padding-top: 2rem !important;
    padding-bottom: 2rem !important;
    max-width: 1400px;
}}

/* 탭 스타일 */
.stTabs [data-baseweb="tab-list"] {{
    gap: 4px;
}}
.stTabs [data-baseweb="tab"] {{
    padding: 10px 18px;
    font-weight: 600;
}}
</style>
"""


def inject_global_css() -> None:
    """앱 시작 시 한 번 호출하여 CSS 주입."""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def render_header(
    title: str | None = None,
    subtitle: str | None = None,
) -> None:
    """
    그라디언트 배너 헤더 렌더.

    Args:
        title: 기본값 = "{PROJECT_NAME} Drug Repurposing Pipeline"
        subtitle: 기본값 = DISEASE
    """
    title = title or f"{PROJECT_NAME} Drug Repurposing Pipeline"
    subtitle = subtitle or DISEASE

    html = f"""
    <div class="app-header">
        <h1>🧬 {title}</h1>
        <p class="subtitle">{subtitle}</p>
        <p class="meta">Protocol {PROTOCOL_VERSION} &nbsp;·&nbsp; Dashboard MVP</p>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_metric_card(
    label: str,
    value: str,
    sub: str | None = None,
    variant: str = "default",
) -> None:
    """
    지표 카드 렌더.

    Args:
        label: 카드 상단 작은 라벨
        value: 큰 숫자 / 값
        sub: 보조 설명 (옵션)
        variant: "default" | "success" | "warning" | "danger"
    """
    variant_class = (
        f" {variant}" if variant in ("success", "warning", "danger") else ""
    )
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""

    html = f"""
    <div class="metric-card{variant_class}">
        <div class="label">{label}</div>
        <div class="value">{value}</div>
        {sub_html}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_step_badge(status: str, label: str) -> str:
    """
    Step 상태 배지 HTML 반환 (st.markdown 에 직접 넣기 위함).

    Args:
        status: "done" | "in_progress" | "pending" | "failed"
        label: 표시할 텍스트

    Returns:
        HTML string
    """
    return f'<span class="step-badge {status}">{label}</span>'
