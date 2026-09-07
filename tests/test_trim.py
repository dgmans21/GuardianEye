from pathlib import Path

from sentinelpose.data.trim import compute_clip_window
from sentinelpose.data.xml_parser import ActionSegment


def make_segment(start, end, total_frames=10000, fps=30):
    return ActionSegment(
        class_label="assault",
        session="10-1",
        video_path=Path("dummy.mp4"),
        xml_path=Path("dummy.xml"),
        fps=fps,
        total_frames=total_frames,
        object_id="person_1",
        action_name="pushing",
        start_frame=start,
        end_frame=end,
    )


def test_short_action_padded_to_minimum_length():
    # 9프레임짜리 짧은 액션 -> 최소 30프레임(min_frames)까지 늘어나야 함
    seg = make_segment(start=1000, end=1009)
    window = compute_clip_window(seg, min_frames=30, max_frames=90, pad_frames=5)
    assert window.num_frames >= 30
    # 원래 구간(패딩 포함 995~1014)을 포함해야 함
    assert window.start_frame <= 995
    assert window.end_frame >= 1014


def test_long_action_capped_to_maximum_length():
    # 1000프레임짜리 긴 액션 -> 최대 90프레임으로 잘려야 함
    seg = make_segment(start=1000, end=2000)
    window = compute_clip_window(seg, min_frames=30, max_frames=90, pad_frames=5)
    assert window.num_frames == 90

    # 중앙 부분을 포함해야 함 (원 구간의 중앙 근처)
    center = (1000 + 2000) // 2
    assert window.start_frame <= center <= window.end_frame


def test_window_clamped_to_video_bounds():
    # 영상 시작 부분(start=0)에 있는 액션 -> 음수 프레임으로 안 나가야 함
    seg = make_segment(start=0, end=5, total_frames=1000)
    window = compute_clip_window(seg, min_frames=30, max_frames=90, pad_frames=5)
    assert window.start_frame >= 0
    assert window.end_frame <= 1000
