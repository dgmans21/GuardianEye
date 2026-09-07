"""추출된 키포인트(.npy) + manifest.csv -> 학습용 (X, y) 텐서로 변환.

파이프라인: 결측 보간 -> BBox 정규화 -> 30프레임 고정 길이 -> (34, 30)로 flatten
(conf 채널은 보간 단계에서 이미 버려지므로 채널 수는 17*2=34).

검출 완전 실패(track_id_used=-1)한 클립은 제외.
"""

import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sentinelpose.data.preprocess import interpolate_missing_keypoints, normalize_by_bbox, to_fixed_length

ROOT = Path(__file__).resolve().parent.parent
KEYPOINTS_DIR = ROOT / "data" / "keypoints"
OUT_PATH = ROOT / "data" / "dataset.npz"

CLASSES = ["assault", "falldown", "intrusion"]
CLASS_TO_IDX = {c: i for i, c in enumerate(CLASSES)}


def main() -> None:
    with open(KEYPOINTS_DIR / "manifest.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    usable = [r for r in rows if int(r["track_id_used"]) != -1]
    skipped = len(rows) - len(usable)
    print(f"전체 {len(rows)}개 중 검출 실패 {skipped}개 제외, {len(usable)}개 사용")

    X = []
    y = []
    for row in usable:
        raw = np.load(KEYPOINTS_DIR / row["npy"])  # (T, 17, 3)
        interpolated = interpolate_missing_keypoints(raw)  # (T, 17, 2)
        normalized = normalize_by_bbox(interpolated)  # (T, 17, 2)
        fixed = to_fixed_length(normalized, target_len=30)  # (30, 17, 2)
        flat = fixed.reshape(30, -1).T  # (34, 30) = (channel, length)

        X.append(flat)
        y.append(CLASS_TO_IDX[row["class_label"]])

    X = np.stack(X).astype(np.float32)  # (N, 34, 30)
    y = np.array(y, dtype=np.int64)

    print(f"X shape: {X.shape}, y shape: {y.shape}")
    for c, idx in CLASS_TO_IDX.items():
        print(f"  {c}: {(y == idx).sum()}개")

    np.savez(OUT_PATH, X=X, y=y, classes=np.array(CLASSES))
    print(f"\n저장 완료: {OUT_PATH}")


if __name__ == "__main__":
    main()
