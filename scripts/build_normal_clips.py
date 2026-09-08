"""원본 세션 영상에서 "라벨된 액션이 없는 구간(정상)"을 골라 30프레임 클립으로 추출.

실시간 데모에서 확인된 문제: 학습 데이터에 "정상" 클래스가 없어서, 평범하게 걷는
장면에서도 분류기가 강제로 assault/falldown/intrusion 중 하나를 확신 있게
찍어버림. 이를 해결하려면 정상 구간도 학습에 포함해야 한다.

방법: 세션별로 XML에 라벨된 모든 action 구간(+여유 마진)을 "점유 구간"으로 표시하고,
나머지 "빈 구간"에서 30프레임 윈도우를 일정 간격으로 샘플링한다.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sentinelpose.data.trim import trim_segments
from sentinelpose.data.xml_parser import ActionSegment, parse_dataset

DOWNLOADS = Path(r"C:\Users\dsltr\Downloads\이상행동 CCTV 영상")
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "trimmed"

SOURCE_DIRS = [
    DOWNLOADS / "01.폭행(assult)" / "inside_croki_01",
    DOWNLOADS / "05.실신(swoon)" / "inside_croki_01",
    DOWNLOADS / "05.실신(swoon)" / "outsidedoor_01",
    DOWNLOADS / "05.실신(swoon)" / "insidedoor_03",
    DOWNLOADS / "07.침입(trespass)" / "outsidedoor_01",
    DOWNLOADS / "07.침입(trespass)" / "outsidedoor_02",
    DOWNLOADS / "07.침입(trespass)" / "outsidedoor_04",
]

WINDOW = 30
MARGIN = 30          # 액션 앞뒤로 이 프레임만큼은 "애매한 전환 구간"으로 보고 제외
STRIDE = 90           # 빈 구간 안에서 윈도우 사이 간격 (3초 @30fps)
MAX_PER_SESSION = 4   # 세션 하나당 최대 정상 샘플 수 (특정 세션에 몰리지 않게)


def find_free_windows(occupied: list[tuple[int, int]], total_frames: int) -> list[tuple[int, int]]:
    """점유 구간들을 병합하고, 그 사이 빈 구간에서 WINDOW 크기 윈도우들을 STRIDE 간격으로 뽑는다."""
    if not occupied:
        occupied = []
    merged = []
    for start, end in sorted(occupied):
        start = max(0, start - MARGIN)
        end = min(total_frames, end + MARGIN)
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    gaps = []
    prev_end = 0
    for start, end in merged:
        if start > prev_end:
            gaps.append((prev_end, start))
        prev_end = max(prev_end, end)
    if prev_end < total_frames:
        gaps.append((prev_end, total_frames))

    windows = []
    for gap_start, gap_end in gaps:
        pos = gap_start
        while pos + WINDOW <= gap_end:
            windows.append((pos, pos + WINDOW))
            pos += STRIDE
    return windows


def main() -> None:
    # 세션(video_path)별로 액션 구간 모으기
    sessions: dict[Path, dict] = {}
    for base_dir in SOURCE_DIRS:
        if not base_dir.exists():
            print(f"[경고] 경로 없음: {base_dir}")
            continue
        for seg in parse_dataset(base_dir, class_label="_ignore"):
            info = sessions.setdefault(
                seg.video_path,
                {"segments": [], "fps": seg.fps, "total_frames": seg.total_frames, "session": seg.session, "xml_path": seg.xml_path},
            )
            info["segments"].append((seg.start_frame, seg.end_frame))

    print(f"세션(영상) 개수: {len(sessions)}")

    normal_segments: list[ActionSegment] = []
    for video_path, info in sorted(sessions.items()):
        windows = find_free_windows(info["segments"], info["total_frames"])
        for start, end in windows[:MAX_PER_SESSION]:
            normal_segments.append(
                ActionSegment(
                    class_label="normal",
                    session=info["session"],
                    video_path=video_path,
                    xml_path=info["xml_path"],
                    fps=info["fps"],
                    total_frames=info["total_frames"],
                    object_id="none",
                    action_name="normal",
                    start_frame=start,
                    end_frame=end,
                )
            )

    print(f"추출할 정상 윈도우 개수: {len(normal_segments)}")

    out_paths = trim_segments(normal_segments, OUT_DIR)
    ok = sum(1 for p in out_paths if p.exists())
    print(f"정상 클립 생성 완료: {ok}/{len(normal_segments)} -> {OUT_DIR / 'normal'}")


if __name__ == "__main__":
    main()
