"""YOLOv8-Pose tracker + 학습된 분류기를 이어붙인 실시간(스트리밍) 추론 파이프라인.

긴 원본 영상을 흘려보내면서, track별로 최근 30프레임 키포인트 윈도우가 차는 대로
분류기를 돌려 어떤 이상행동으로 보이는지 출력한다.

중요한 한계: 학습된 분류기는 assault/falldown/intrusion 3개 중 하나로만 분류하도록
학습되어서 "평상시" 클래스가 없다. 그래서 softmax 확률이 낮으면(threshold 미만)
"정상/불확실"로 처리하는 방식을 쓴다 — 엄밀한 이상탐지 기법은 아니고, 이 프로젝트
스코프에서의 근사적 해법이다.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import torch
from ultralytics import YOLO

from sentinelpose.data.preprocess import interpolate_missing_keypoints, normalize_by_bbox
from sentinelpose.models.classifier import TemporalGRU

WINDOW_SIZE = 30
CLASSES = ["assault", "falldown", "intrusion", "normal"]


@dataclass
class TrackBuffer:
    keypoints: deque = field(default_factory=lambda: deque(maxlen=WINDOW_SIZE))


def load_classifier(weight_path: Path, device: str) -> TemporalGRU:
    model = TemporalGRU(in_channels=34, num_classes=len(CLASSES))
    model.load_state_dict(torch.load(weight_path, map_location=device))
    model.to(device)
    model.eval()
    return model


def window_to_input(window: deque) -> np.ndarray:
    """(30, 17, 3) 키포인트 버퍼 -> 모델 입력 (1, 34, 30)."""
    kp = np.stack(list(window))  # (30, 17, 3)
    interpolated = interpolate_missing_keypoints(kp)  # (30, 17, 2)
    normalized = normalize_by_bbox(interpolated)  # (30, 17, 2)
    flat = normalized.reshape(30, -1).T  # (34, 30)
    return flat[None, ...].astype(np.float32)  # (1, 34, 30)


def run_realtime(
    video_path: Path,
    pose_model_name: str = "yolov8x-pose.pt",
    classifier_weight: Path = Path("outputs/temporalgru.pt"),
    conf_threshold: float = 0.6,
    device: str = "cuda" if torch.cuda.is_available() else "cpu",
    pose_conf: float = 0.15,
    log_every: int = 1,
):
    pose_model = YOLO(pose_model_name)
    classifier = load_classifier(classifier_weight, device)

    buffers: dict[int, TrackBuffer] = {}
    log_rows = []

    t_start = time.time()
    n_frames = 0
    clf_time_total = 0.0

    results_gen = pose_model.track(
        source=str(video_path),
        stream=True,
        persist=True,
        tracker="bytetrack.yaml",
        device=device,
        conf=pose_conf,
        verbose=False,
    )

    for frame_idx, result in enumerate(results_gen):
        n_frames += 1

        if result.keypoints is not None and result.boxes is not None and result.boxes.id is not None:
            kps = result.keypoints.data.cpu().numpy()
            ids = result.boxes.id.cpu().numpy().astype(int)
            for i, tid in enumerate(ids):
                buf = buffers.setdefault(tid, TrackBuffer())
                buf.keypoints.append(kps[i])

                if len(buf.keypoints) == WINDOW_SIZE:
                    t1 = time.time()
                    x = torch.tensor(window_to_input(buf.keypoints)).to(device)
                    with torch.no_grad():
                        logits = classifier(x)
                        probs = torch.softmax(logits, dim=1)[0].cpu().numpy()
                    clf_time_total += time.time() - t1

                    pred_idx = int(probs.argmax())
                    pred_conf = float(probs[pred_idx])
                    # "normal" 클래스가 생겼으니 그대로 argmax 사용, 확신도가 아주
                    # 낮을 때만 "불확실"로 별도 표시
                    label = CLASSES[pred_idx] if pred_conf >= conf_threshold else "불확실"

                    if frame_idx % log_every == 0:
                        log_rows.append(
                            {
                                "frame": frame_idx,
                                "track_id": int(tid),
                                "pred": label,
                                "conf": round(pred_conf, 3),
                                "probs": [round(float(p), 3) for p in probs],
                            }
                        )

    elapsed = time.time() - t_start
    fps = n_frames / elapsed if elapsed > 0 else 0.0
    pose_only_elapsed = elapsed - clf_time_total

    summary = {
        "video": str(video_path),
        "total_frames": n_frames,
        "elapsed_sec": round(elapsed, 2),
        "fps": round(fps, 2),
        "avg_pose_time_ms": round(pose_only_elapsed / n_frames * 1000, 2) if n_frames else 0,
        "avg_clf_time_ms": round(clf_time_total / max(1, len(log_rows)) * 1000, 3) if log_rows else 0,
        "num_classifications": len(log_rows),
    }
    return summary, log_rows
