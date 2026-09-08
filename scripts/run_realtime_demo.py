import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sentinelpose.realtime import run_realtime

ROOT = Path(__file__).resolve().parent.parent
VIDEO = ROOT / "data" / "demo" / "swoon_101-1_test.mp4"

if __name__ == "__main__":
    summary, log_rows = run_realtime(
        video_path=VIDEO,
        classifier_weight=ROOT / "outputs" / "temporalgru.pt",
        conf_threshold=0.35,
    )

    print("=== 요약 ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    out_csv = ROOT / "outputs" / "realtime_demo_log.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["frame", "track_id", "pred", "conf", "probs"])
        writer.writeheader()
        writer.writerows(log_rows)
    print(f"\n로그 저장: {out_csv} ({len(log_rows)}행)")

    print("\n=== 처음 20개 분류 결과 ===")
    for row in log_rows[:20]:
        print(row)

    print("\n=== 마지막 20개 분류 결과 ===")
    for row in log_rows[-20:]:
        print(row)
