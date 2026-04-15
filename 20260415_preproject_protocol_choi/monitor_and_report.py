"""
주기적으로 결과를 모니터링하고 완료 시 비교표 생성
"""
import time
import json
from pathlib import Path
import subprocess
import sys

def check_results(results_dir):
    """현재 완료된 결과 파일 확인"""
    ml_files = list(results_dir.glob("*_ml_v1_*.json"))
    dl_files = list(results_dir.glob("*_dl_v1_*.json"))

    # 기대하는 파일 수
    # 3 input sets × 3 eval modes = 9 files each
    ml_expected = 9
    dl_expected = 9

    ml_count = len(ml_files)
    dl_count = len(dl_files)

    return {
        'ml_count': ml_count,
        'ml_expected': ml_expected,
        'ml_complete': ml_count == ml_expected,
        'ml_files': sorted([f.name for f in ml_files]),
        'dl_count': dl_count,
        'dl_expected': dl_expected,
        'dl_complete': dl_count == dl_expected,
        'dl_files': sorted([f.name for f in dl_files])
    }

def generate_ml_table(results_dir):
    """ML 비교표 생성"""
    print("\n" + "="*140)
    print("ML 결과 비교표 생성 중...")
    print("="*140)

    try:
        result = subprocess.run(
            [sys.executable, "generate_comparison_table.py"],
            cwd=results_dir.parent,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            print(result.stdout)
            return True
        else:
            print(f"Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"Failed to generate table: {e}")
        return False

def main():
    base_dir = Path(__file__).parent
    results_dir = base_dir / "results"

    check_interval = 180  # 3분
    ml_reported = False
    dl_reported = False

    print("="*140)
    print("결과 모니터링 시작")
    print(f"체크 간격: {check_interval}초 (3분)")
    print("="*140)

    while True:
        status = check_results(results_dir)

        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{current_time}]")
        print(f"  ML: {status['ml_count']}/{status['ml_expected']} 파일")
        print(f"  DL: {status['dl_count']}/{status['dl_expected']} 파일")

        # ML 완료 감지
        if status['ml_complete'] and not ml_reported:
            print("\n" + "🎉"*50)
            print("ML 학습 완료!")
            print("🎉"*50)
            print("\nML 결과 파일:")
            for f in status['ml_files']:
                print(f"  - {f}")

            # ML 비교표 생성
            generate_ml_table(results_dir)
            ml_reported = True

        # DL 완료 감지
        if status['dl_complete'] and not dl_reported:
            print("\n" + "🎉"*50)
            print("DL 학습 완료!")
            print("🎉"*50)
            print("\nDL 결과 파일:")
            for f in status['dl_files']:
                print(f"  - {f}")

            dl_reported = True

        # 전체 완료
        if status['ml_complete'] and status['dl_complete']:
            print("\n" + "🎉"*50)
            print("전체 학습 완료!")
            print("🎉"*50)

            # 최종 통합 비교표 생성
            print("\n최종 통합 비교표 생성 중...")
            generate_ml_table(results_dir)

            print("\n모니터링 종료")
            break

        # 대기
        time.sleep(check_interval)

if __name__ == "__main__":
    main()
