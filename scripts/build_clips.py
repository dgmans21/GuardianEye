"""3개 클래스(assault / falldown / intrusion) 전체를 파싱해서 트리밍까지 실행.

falldown 클래스는 swoon(실신) 데이터만 사용한다 (assault의 person_2 falldown은
"맞아서 넘어짐"이라 동작 패턴이 달라 섞지 않기로 결정 - WORKLOG.md 참고).

원본 영상은 건드리지 않고 data/trimmed/<class>/ 아래에 잘라낸 클립만 생성한다.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sentinelpose.data.trim import trim_segments
from sentinelpose.data.xml_parser import parse_dataset

DOWNLOADS = Path(r"C:\Users\dsltr\Downloads\이상행동 CCTV 영상")
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "trimmed"

# (클래스 라벨, XML이 들어있는 base 디렉토리들)
SOURCES = {
    "assault": [
        DOWNLOADS / "01.폭행(assult)" / "inside_croki_01",
    ],
    "falldown": [
        DOWNLOADS / "05.실신(swoon)" / "inside_croki_01",
        DOWNLOADS / "05.실신(swoon)" / "outsidedoor_01",
        DOWNLOADS / "05.실신(swoon)" / "insidedoor_03",
    ],
    "intrusion": [
        DOWNLOADS / "07.침입(trespass)" / "outsidedoor_01",
        DOWNLOADS / "07.침입(trespass)" / "outsidedoor_02",
        DOWNLOADS / "07.침입(trespass)" / "outsidedoor_04",
    ],
}


def main() -> None:
    grand_total = 0
    for class_label, base_dirs in SOURCES.items():
        segments = []
        for base_dir in base_dirs:
            if not base_dir.exists():
                print(f"[경고] 경로 없음, 스킵: {base_dir}")
                continue
            segments.extend(parse_dataset(base_dir, class_label=class_label))

        print(f"\n=== {class_label}: {len(segments)}개 세그먼트 트리밍 시작 ===")
        out_paths = trim_segments(segments, OUT_DIR)
        ok = sum(1 for p in out_paths if p.exists())
        print(f"{class_label}: {ok}/{len(segments)}개 클립 생성 완료 -> {OUT_DIR / class_label}")
        grand_total += ok

    print(f"\n총 {grand_total}개 클립 생성 완료 -> {OUT_DIR}")


if __name__ == "__main__":
    main()
