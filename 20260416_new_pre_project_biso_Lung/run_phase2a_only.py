"""
Phase 2A만 실행하는 래퍼 스크립트
"""
from run_ml_all import run_phase_ml

if __name__ == "__main__":
    print("\n" + "="*120)
    print("Phase 2A: Lung - numeric-only")
    print("="*120)

    results_2a = run_phase_ml(
        input_file="X_numeric.npy",
        output_stem="lung_numeric_ml_v1",
        phase_name="Phase 2A - Lung"
    )

    print("\n" + "="*120)
    print("Phase 2A 완료!")
    print("="*120)
