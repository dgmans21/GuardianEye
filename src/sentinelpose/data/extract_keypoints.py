"""트리밍된 클립에서 YOLOv8-Pose(+ByteTrack)로 키포인트 시퀀스 추출.

클립 하나 = 라벨된 액션 하나에 대응하도록 이미 트리밍되어 있지만, 화면 안에는
여러 사람이 같이 잡힐 수 있다 (예: assault 클립에 가해자+피해자 둘 다 보임).
클립 내에서 가장 오래 지속적으로 추적된 track을 "라벨된 행동의 주체"로 간주하는
근사 방식을 쓴다 (세션 전체를 트래킹해서 XML의 <position> 참조점으로 정교하게
매칭하는 방법도 있지만, 포트폴리오 스코프에서는 이 근사로 충분하다고 판단).

출력: data/keypoints/<class_label>/<clip_stem>.npy, shape (T, 17, 3) = (x, y, conf).
프레임에서 주 track이 검출되지 않으면 (0, 0, 0)으로 채운다 (후속 보간 단계에서 처리).
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import numpy as np
from ultralytics import YOLO

NUM_KEYPOINTS = 17


def extract_clip_keypoints(
    model: YOLO, clip_path: Path, device: int | str = 0, conf: float = 0.15
) -> tuple[np.ndarray, int, int]:
    """클립 하나를 추적하며 처리해서 주 track의 키포인트 시퀀스를 반환.

    Returns:
        keypoints: (T, 17, 3) 배열
        chosen_track_id: 사용된 track id (없으면 -1)
        max_people_in_frame: 클립에서 동시에 검출된 최대 인원 수 (QA용)
    """
    results = model.track(
        source=str(clip_path),
        persist=False,
        tracker="bytetrack.yaml",
        device=device,
        conf=conf,
        verbose=False,
    )

    T = len(results)
    per_frame_tracks: list[dict[int, np.ndarray]] = []
    track_frame_count: dict[int, int] = defaultdict(int)
    max_people = 0

    for frame_result in results:
        frame_map: dict[int, np.ndarray] = {}
        if frame_result.keypoints is not None and frame_result.boxes is not None and frame_result.boxes.id is not None:
            kps = frame_result.keypoints.data.cpu().numpy()  # (N, 17, 3)
            ids = frame_result.boxes.id.cpu().numpy().astype(int)  # (N,)
            max_people = max(max_people, len(ids))
            for i, tid in enumerate(ids):
                frame_map[int(tid)] = kps[i]
                track_frame_count[int(tid)] += 1
        per_frame_tracks.append(frame_map)

    keypoints = np.zeros((T, NUM_KEYPOINTS, 3), dtype=np.float32)
    chosen_track_id = -1
    if track_frame_count:
        chosen_track_id = max(track_frame_count, key=track_frame_count.get)
        for t, frame_map in enumerate(per_frame_tracks):
            if chosen_track_id in frame_map:
                keypoints[t] = frame_map[chosen_track_id]

    return keypoints, chosen_track_id, max_people


def extract_dataset(
    trimmed_dir: Path,
    out_dir: Path,
    exclude_patterns: dict[str, list[str]] | None = None,
    model_name: str = "yolov8n-pose.pt",
    device: int | str = 0,
    conf: float = 0.15,
) -> None:
    """trimmed_dir/<class>/*.mp4 전체에서 키포인트를 추출해 out_dir/<class>/*.npy로 저장.

    exclude_patterns: {class_label: [glob 패턴, ...]} — 예: assault에서 falldown 제외.

    증분 처리: out_dir에 기존 manifest.csv가 있으면, 이미 처리된(.npy 존재 +
    manifest에 기록된) 클립은 건너뛰고 새로 생긴 클립만 모델을 돌린다. 데이터를
    조금씩 계속 추가하는 워크플로우라 매번 전체를 재처리하면 GPU 시간이 낭비됨.
    """
    exclude_patterns = exclude_patterns or {}
    manifest_path = out_dir / "manifest.csv"

    existing_rows: dict[str, dict] = {}
    if manifest_path.exists():
        with open(manifest_path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                existing_rows[row["npy"]] = row

    model = None  # 새로 처리할 클립이 있을 때만 로드 (전부 재사용이면 모델 로드도 생략)
    manifest_rows = []

    for class_dir in sorted(trimmed_dir.iterdir()):
        if not class_dir.is_dir():
            continue
        class_label = class_dir.name
        patterns = exclude_patterns.get(class_label, [])

        clips = sorted(class_dir.glob("*.mp4"))
        excluded = set()
        for pat in patterns:
            excluded.update(class_dir.glob(pat))
        clips = [c for c in clips if c not in excluded]

        out_class_dir = out_dir / class_label
        out_class_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n=== {class_label}: {len(clips)}개 클립 (제외 {len(excluded)}개) ===")
        new_count, reused_count = 0, 0
        for i, clip_path in enumerate(clips, 1):
            out_path = out_class_dir / (clip_path.stem + ".npy")
            rel_npy = str(out_path.relative_to(out_dir))

            if out_path.exists() and rel_npy in existing_rows:
                manifest_rows.append(existing_rows[rel_npy])
                reused_count += 1
                continue

            if model is None:
                model = YOLO(model_name)

            keypoints, track_id, max_people = extract_clip_keypoints(model, clip_path, device=device, conf=conf)
            np.save(out_path, keypoints)
            manifest_rows.append(
                {
                    "class_label": class_label,
                    "clip": clip_path.name,
                    "npy": rel_npy,
                    "num_frames": keypoints.shape[0],
                    "track_id_used": track_id,
                    "max_people_detected": max_people,
                }
            )
            new_count += 1
            if new_count % 50 == 0:
                print(f"  신규 {new_count}개 처리 중...")

        print(f"  {class_label}: 신규 {new_count}개 처리, 기존 {reused_count}개 재사용")

    with open(manifest_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(manifest_rows[0].keys()))
        writer.writeheader()
        writer.writerows(manifest_rows)
    print(f"\nmanifest 저장: {manifest_path} ({len(manifest_rows)}행, 그중 신규 처리분 확인은 위 로그 참고)")
