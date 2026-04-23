"""
dashboard.views — 각 탭의 뷰 구현.

각 뷰는 render() 함수를 노출하며, app.py 에서 다음과 같이 사용:

    from dashboard.views import render_overview, render_step4
    render_step4()

모듈:
    - overview: Tab 1 — 파이프라인 전체 요약 (구현 완료)
    - step4_modeling: Tab 4 — Step 4 Modeling (Section 1-2 구현 중)
    - step1_2_data_qc, step3_fe, step5_ensemble, step6_validation, comparison: (예정)
"""

from dashboard.views.overview import render as render_overview
from dashboard.views.step4_modeling import render as render_step4
from . import step6_9_results
from . import step6_validation
from . import step7_admet
from . import step8_knowledge_graph
from . import step9_llm

__all__ = [
    "render_overview",
    "render_step4",
]
