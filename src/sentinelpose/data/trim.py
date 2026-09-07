"""XML의 <object><action><frame> 구간을 기준으로 FFmpeg 트리밍.

실제 데이터 확인 결과 assault/swoon/trespass 모두 <object><action><frame> 단위
라벨이 존재해서 (trespass의 climbwall도 이 형태), 클래스 구분 없이 이 단일
경로로 트리밍하면 된다. (최상단 <event>는 assault에서는 너무 넓어 못 쓰지만
action 단위는 항상 유효하다.)
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from sentinelpose.data.xml_parser import ActionSegment

MIN_CLIP_FRAMES = 30   # 모델 입력 스펙: 30프레임(=1초 @30fps) 미만이면 안 됨
MAX_CLIP_FRAMES = 90   # 너무 긴 액션은 중앙 3초만 사용
PAD_FRAMES = 5         # 액션 전후 여유


@dataclass
class ClipWindow:
    start_frame: int
    end_frame: int

    @property
    def num_frames(self) -> int:
        return self.end_frame - self.start_frame


def compute_clip_window(
    segment: ActionSegment,
    min_frames: int = MIN_CLIP_FRAMES,
    max_frames: int = MAX_CLIP_FRAMES,
    pad_frames: int = PAD_FRAMES,
) -> ClipWindow:
    """액션 프레임 구간을 모델 입력 길이 스펙에 맞게 보정.

    - 너무 짧으면(패딩 포함 min_frames 미만) 앞뒤로 늘려서 최소 길이 확보
    - 너무 길면 구간 중앙 max_frames만 사용
    - 항상 [0, total_frames) 범위로 clamp
    """
    start = segment.start_frame - pad_frames
    end = segment.end_frame + pad_frames

    length = end - start
    if length < min_frames:
        deficit = min_frames - length
        start -= deficit // 2
        end += deficit - deficit // 2
    elif length > max_frames:
        center = (start + end) // 2
        start = center - max_frames // 2
        end = start + max_frames

    start = max(start, 0)
    if segment.total_frames:
        end = min(end, segment.total_frames)
    end = max(end, start + 1)

    return ClipWindow(start_frame=start, end_frame=end)


def trim_clip(
    segment: ActionSegment,
    out_dir: Path,
    clip_index: int,
    ffmpeg_bin: str = "ffmpeg",
    scale_height: int = 480,
) -> Path:
    """segment 하나를 FFmpeg로 잘라 out_dir/<class_label>/ 아래 mp4로 저장.

    재인코딩(-vf scale)을 쓰는 이유: 4K 원본을 그대로 -c copy로 자르면 키프레임
    경계 때문에 원하는 지점보다 앞에서 잘리는 경우가 있어서, 프레임 단위 정밀도가
    중요한 이 단계에서는 재인코딩을 택했다. 대신 해상도를 낮춰 속도/용량을 보완.
    """
    window = compute_clip_window(segment)
    start_sec = window.start_frame / segment.fps
    duration_sec = window.num_frames / segment.fps

    out_path = (
        Path(out_dir)
        / segment.class_label
        / f"{segment.session}_{segment.object_id}_{segment.action_name}_{clip_index:03d}.mp4"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        ffmpeg_bin,
        "-y",
        "-ss",
        f"{start_sec:.3f}",
        "-i",
        str(segment.video_path),
        "-t",
        f"{duration_sec:.3f}",
        "-vf",
        f"scale=-2:{scale_height}",
        "-an",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def trim_segments(
    segments: list[ActionSegment],
    out_dir: Path,
    ffmpeg_bin: str = "ffmpeg",
    scale_height: int = 480,
) -> list[Path]:
    """세그먼트 목록을 순서대로 트리밍. 세션+object+action 조합별로 인덱스를
    붙여서 같은 액션이 여러 번 나와도 파일명이 겹치지 않게 한다."""
    counters: dict[tuple[str, str, str], int] = {}
    out_paths: list[Path] = []
    for seg in segments:
        key = (seg.session, seg.object_id, seg.action_name)
        counters[key] = counters.get(key, 0) + 1
        out_paths.append(
            trim_clip(seg, out_dir, counters[key], ffmpeg_bin=ffmpeg_bin, scale_height=scale_height)
        )
    return out_paths
