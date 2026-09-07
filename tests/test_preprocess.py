import numpy as np

from sentinelpose.data.preprocess import (
    interpolate_missing_keypoints,
    normalize_by_bbox,
    to_fixed_length,
)


def make_keypoints(xs, ys, confs):
    """xs/ys/confs: 길이 T 리스트. 키포인트 1개짜리 (T, 1, 3) 배열 생성."""
    T = len(xs)
    arr = np.zeros((T, 1, 3))
    arr[:, 0, 0] = xs
    arr[:, 0, 1] = ys
    arr[:, 0, 2] = confs
    return arr


def test_interpolate_fills_single_missing_frame_linearly():
    # 프레임 1이 결측(conf 낮음) -> 0과 2 사이 선형보간으로 5가 나와야 함
    kp = make_keypoints(xs=[0, 999, 10], ys=[0, 999, 10], confs=[1.0, 0.1, 1.0])
    out = interpolate_missing_keypoints(kp, conf_threshold=0.3, max_gap=10)
    assert out.shape == (3, 1, 2)
    assert out[1, 0, 0] == 5.0
    assert out[1, 0, 1] == 5.0


def test_interpolate_all_valid_passes_through():
    kp = make_keypoints(xs=[1, 2, 3], ys=[4, 5, 6], confs=[1.0, 1.0, 1.0])
    out = interpolate_missing_keypoints(kp)
    assert np.allclose(out[:, 0, 0], [1, 2, 3])
    assert np.allclose(out[:, 0, 1], [4, 5, 6])


def test_interpolate_long_gap_is_zero_masked():
    # 길이 5인 결측이 max_gap=2를 초과 -> 보간하지 않고 0으로 마스킹
    confs = [1.0] + [0.0] * 5 + [1.0]
    xs = [0] + [999] * 5 + [100]
    kp = make_keypoints(xs=xs, ys=xs, confs=confs)
    out = interpolate_missing_keypoints(kp, conf_threshold=0.3, max_gap=2)
    assert np.allclose(out[1:6, 0, 0], 0.0)


def test_normalize_by_bbox_maps_corners_to_unit_range():
    # 한 프레임에 키포인트 4개: (0,0), (10,0), (0,20), (10,20) -> bbox는 10x20
    kp = np.array(
        [[[0, 0], [10, 0], [0, 20], [10, 20]]],
        dtype=float,
    )  # shape (1, 4, 2)
    out = normalize_by_bbox(kp)
    assert np.allclose(out[0, 0], [0.0, 0.0])
    assert np.allclose(out[0, 3], [1.0, 1.0])


def test_normalize_by_bbox_handles_degenerate_bbox():
    # 모든 키포인트가 같은 점 -> w, h가 0이라 eps로 나눠 NaN/inf 없이 0이 나와야 함
    kp = np.array([[[5, 5], [5, 5]]], dtype=float)
    out = normalize_by_bbox(kp)
    assert np.isfinite(out).all()


def test_to_fixed_length_passthrough_when_already_correct():
    kp = np.zeros((30, 17, 2))
    out = to_fixed_length(kp, target_len=30)
    assert out.shape == (30, 17, 2)


def test_to_fixed_length_center_crops_long_sequence():
    # 0..89 프레임 인덱스를 값으로 채워서, 중앙 30프레임(30~59)이 남는지 확인
    kp = np.arange(90).reshape(90, 1, 1).astype(float)
    out = to_fixed_length(kp, target_len=30)
    assert out.shape == (30, 1, 1)
    assert out[0, 0, 0] == 30
    assert out[-1, 0, 0] == 59


def test_to_fixed_length_pads_short_sequence_with_edge_values():
    kp = np.arange(29).reshape(29, 1, 1).astype(float)
    out = to_fixed_length(kp, target_len=30)
    assert out.shape == (30, 1, 1)
    # 1프레임만 부족 -> 뒤쪽에 마지막 값(28)이 반복돼야 함
    assert out[-1, 0, 0] == 28
