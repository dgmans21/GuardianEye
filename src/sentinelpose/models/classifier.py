"""경량 행동 분류기: 1D-CNN / 단일 레이어 GRU.

입력 shape: (Batch, Channel=51, Length=30)
  - Channel 51 = 17 keypoints x (x_norm, y_norm, conf) 또는 (x_norm, y_norm)+conf 별도.
    현재 preprocess 단계는 conf 채널을 버리므로 conf를 계속 쓰려면 채널 구성을
    맞춰서 34(=17*2) 또는 51(=17*3)을 선택하면 된다. 기본값은 51.
  - Length 30 = 30프레임(1초 @30fps) 윈도우.
"""

from __future__ import annotations

import torch
from torch import nn


class TemporalCNN(nn.Module):
    """가벼운 1D-CNN 분류기. 소규모 데이터셋에서 빠르게 수렴시키는 용도."""

    def __init__(self, in_channels: int = 51, num_classes: int = 3, hidden: int = 64):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv1d(in_channels, hidden, kernel_size=3, padding=1),
            nn.BatchNorm1d(hidden),
            nn.ReLU(inplace=True),
            nn.Conv1d(hidden, hidden, kernel_size=3, padding=1),
            nn.BatchNorm1d(hidden),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool1d(1),
        )
        self.classifier = nn.Linear(hidden, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, C, L)
        feat = self.features(x).squeeze(-1)  # (B, hidden)
        return self.classifier(feat)


class TemporalGRU(nn.Module):
    """단일 레이어 GRU 분류기."""

    def __init__(self, in_channels: int = 51, num_classes: int = 3, hidden: int = 64):
        super().__init__()
        self.gru = nn.GRU(input_size=in_channels, hidden_size=hidden, num_layers=1, batch_first=True)
        self.classifier = nn.Linear(hidden, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, C, L) -> GRU는 (B, L, C) 필요
        x = x.transpose(1, 2)
        _, h_n = self.gru(x)  # h_n: (1, B, hidden)
        return self.classifier(h_n[-1])
