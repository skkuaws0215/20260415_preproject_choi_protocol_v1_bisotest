"""
dashboard.parsers — Step별 결과 파서.

사용 예:
    from dashboard.parsers import load_step4_results
    df = load_step4_results()

모듈:
    - step4_modeling_parser: Step 4 Modeling 결과 (ML/DL/Graph × Phase × Split)
    - step2_qc_parser      : (예정) Step 2 QC 리포트
    - step3_fe_parser      : (예정) Step 3 Feature Engineering
"""

from dashboard.parsers.step4_modeling_parser import (
    load_step4_results,
    parse_json_file,
    parse_filename,
    parse_model_result,
)

__all__ = [
    "load_step4_results",
    "parse_json_file",
    "parse_filename",
    "parse_model_result",
]
