import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sentinelpose.data.extract_keypoints import extract_dataset

ROOT = Path(__file__).resolve().parent.parent
TRIMMED_DIR = ROOT / "data" / "trimmed"
KEYPOINTS_DIR = ROOT / "data" / "keypoints"

# assault의 person_2 falldown(맞아서 쓰러짐)은 falldown 클래스와 동작 패턴이
# 헷갈릴 수 있어 제외 (WORKLOG.md 참고)
#
# intrusion의 pulling(문/게이트 강제개방)이 assault의 pulling(잡아당김)과 관절
# 움직임이 실제로 비슷해서 일시적으로 제외 테스트해봤으나, intrusion 표본이
# 34개(테스트셋 5개)로 너무 줄어들어 baseline 대비 실질 이득이 오히려 감소함
# (+7.3%p -> +5.0%p). pulling 포함 버전이 더 나아서 원복함 (WORKLOG 참고)
EXCLUDE = {
    "assault": ["*_falldown_*.mp4"],
}

if __name__ == "__main__":
    extract_dataset(
        TRIMMED_DIR,
        KEYPOINTS_DIR,
        exclude_patterns=EXCLUDE,
        model_name="yolov8x-pose.pt",
        conf=0.15,
        device=0,
    )
