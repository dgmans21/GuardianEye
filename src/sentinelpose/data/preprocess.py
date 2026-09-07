"""키포인트 결측치 보간 + BBox 상대좌표 정규화.

입력 포맷: YOLOv8-Pose 출력 기준 keypoints shape (T, K, 3) = (프레임 수, 17개
키포인트, (x, y, confidence)).
"""

from __future__ import annotations

import numpy as np


def interpolate_missing_keypoints(
    keypoints: np.ndarray,
    conf_threshold: float = 0.3,
    max_gap: int = 10,
) -> np.ndarray:
    """confidence < conf_threshold인 좌표를 NaN 처리 후 시간축 선형보간.

    보간 가능한 범위(연속 결측 길이가 max_gap 이하)는 선형보간으로 채우고,
    그보다 긴 결측 구간은 신뢰할 수 없다고 보고 (0, 0)으로 마스킹한다.

    Args:
        keypoints: (T, K, 3) 배열. 마지막 축은 (x, y, conf).
        conf_threshold: 이 값 미만인 키포인트는 결측으로 취급.
        max_gap: 이 프레임 수를 초과하는 연속 결측은 보간하지 않고 0으로 마스킹.

    Returns:
        (T, K, 2) 배열. conf 채널은 제거되고 보간이 끝난 (x, y)만 남는다.
    """
    if keypoints.ndim != 3 or keypoints.shape[-1] != 3:
        raise ValueError(f"keypoints shape must be (T, K, 3), got {keypoints.shape}")

    T, K, _ = keypoints.shape
    xy = keypoints[..., :2].astype(float).copy()
    conf = keypoints[..., 2]
    xy[conf < conf_threshold] = np.nan

    out = np.zeros_like(xy)
    for k in range(K):
        out[:, k, 0] = _interpolate_1d(xy[:, k, 0], max_gap)
        out[:, k, 1] = _interpolate_1d(xy[:, k, 1], max_gap)
    return out


def _interpolate_1d(series: np.ndarray, max_gap: int) -> np.ndarray:
    """1차원 시계열의 NaN을 선형보간. max_gap보다 긴 연속 NaN 구간은 0으로 마스킹."""
    n = len(series)
    valid = ~np.isnan(series)

    if valid.sum() == 0:
        return np.zeros(n)
    if valid.all():
        return series.copy()

    idx = np.arange(n)
    result = np.interp(idx, idx[valid], series[valid])

    gap_start = None
    for i in range(n):
        if not valid[i]:
            if gap_start is None:
                gap_start = i
        elif gap_start is not None:
            if i - gap_start > max_gap:
                result[gap_start:i] = 0.0
            gap_start = None
    if gap_start is not None and n - gap_start > max_gap:
        result[gap_start:n] = 0.0

    return result


def normalize_by_bbox(keypoints_xy: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """프레임별 BBox(그 프레임 키포인트들의 min/max) 기준 상대좌표로 정규화.

    x_norm = (x - x_min) / w, y_norm = (y - y_min) / h  → 각 프레임에서 [0, 1] 범위.
    카메라와의 거리/각도에 따른 절대 스케일 차이를 제거하기 위한 것.

    Args:
        keypoints_xy: (T, K, 2) 배열 (보간 완료된 좌표).

    Returns:
        (T, K, 2) 정규화된 좌표.
    """
    if keypoints_xy.ndim != 3 or keypoints_xy.shape[-1] != 2:
        raise ValueError(f"keypoints_xy shape must be (T, K, 2), got {keypoints_xy.shape}")

    x = keypoints_xy[..., 0]
    y = keypoints_xy[..., 1]

    x_min = x.min(axis=1, keepdims=True)
    x_max = x.max(axis=1, keepdims=True)
    y_min = y.min(axis=1, keepdims=True)
    y_max = y.max(axis=1, keepdims=True)

    w = np.maximum(x_max - x_min, eps)
    h = np.maximum(y_max - y_min, eps)

    out = np.empty_like(keypoints_xy)
    out[..., 0] = (x - x_min) / w
    out[..., 1] = (y - y_min) / h
    return out


def to_fixed_length(keypoints: np.ndarray, target_len: int = 30) -> np.ndarray:
    """시간축 길이를 target_len으로 통일 (트리밍된 클립이 29~90프레임으로 제각각이라 필요).

    길면 중앙 target_len 프레임만 crop, 짧으면 가장자리 프레임을 반복해서 채운다
    (동작이 이미 시작/끝난 정지 구간을 늘리는 것이라 보간보다 이 방식이 안전).

    Args:
        keypoints: (T, ...) 형태 배열 (K,2)든 (K,3)이든 첫 축이 시간이면 됨.
    """
    T = keypoints.shape[0]
    if T == target_len:
        return keypoints.copy()

    if T > target_len:
        start = (T - target_len) // 2
        return keypoints[start : start + target_len].copy()

    # T < target_len: 앞뒤로 가장자리 프레임 반복해서 패딩
    deficit = target_len - T
    pad_before = deficit // 2
    pad_after = deficit - pad_before
    pad_width = [(pad_before, pad_after)] + [(0, 0)] * (keypoints.ndim - 1)
    return np.pad(keypoints, pad_width, mode="edge")
