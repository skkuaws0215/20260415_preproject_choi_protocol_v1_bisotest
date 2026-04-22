"""
dashboard.views — 각 탭의 뷰 구현.

각 뷰는 render() 함수를 노출하며, app.py 에서 다음과 같이 사용:

    from dashboard.views import render_overview
    render_overview()

모듈:
    - overview: Tab 1 — 파이프라인 전체 요약 (구현 완료)
    - step1_2_data_qc: Tab 2 — Step 1-2 Data & QC (예정)
    - step3_fe: Tab 3 — Step 3 Feature Engineering (예정)
    - step4_modeling: Tab 4 — Step 4 Modeling (예정, 메인 탭)
    - step5_ensemble: Tab 5 — Step 5 Ensemble (예정)
    - step6_validation: Tab 6 — Step 6 External Validation (예정)
    - comparison: Tab 7 — Lung vs Colon vs STAD (예정)
"""

from dashboard.views.overview import render as render_overview

__all__ = ["render_overview"]
