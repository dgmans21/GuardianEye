"""NIA2019 이상행동 CCTV 영상 XML 라벨 파서.

실제 다운로드한 assault / swoon / trespass 샘플을 기준으로 확인된 스키마:

    <annotation>
        <folder>...</folder>
        <filename>...mp4</filename>
        <header>
            <fps>30</fps>
            <frames>8142</frames>
            <population>2</population>
            ...
        </header>
        <event>
            <eventname>assault</eventname>
            <starttime>00:01:11.5</starttime>
            <duration>00:03:16.5</duration>
        </event>
        <object>
            <objectname>person_1</objectname>
            <action>
                <actionname>pushing</actionname>
                <frame><start>2147</start><end>2193</end></frame>
                ...
            </action>
            ...
        </object>
        ...
    </annotation>

주의사항 (실 데이터에서 확인됨):
- <event>의 구간은 클래스마다 신뢰도가 다르다. assault는 영상 대부분을 덮는 넓은
  구간이라 트리밍 기준으로 못 쓰고, trespass/swoon은 수 초 단위로 짧고 정확하다.
  그래서 트리밍은 항상 <object><action><frame> 단위를 우선 사용한다.
- objectname 표기가 파일마다 다르다 (person_1 / Person_1 / Person / Person01 /
  person_2 ...). normalize_object_id()로 통일한다.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


def normalize_object_id(raw: str) -> str:
    """'Person', 'Person01', 'Person_1', 'person_2' 등을 'person_1' 형태로 통일."""
    m = re.search(r"(\d+)", raw)
    if m:
        return f"person_{int(m.group(1))}"
    return "person_1"


@dataclass
class ActionSegment:
    class_label: str          # assault / swoon / trespass 등 상위 클래스
    session: str               # 세션 폴더명 (예: 24-3, 145-1)
    video_path: Path
    xml_path: Path
    fps: int
    total_frames: int
    object_id: str
    action_name: str
    start_frame: int
    end_frame: int

    @property
    def duration_frames(self) -> int:
        return self.end_frame - self.start_frame

    @property
    def start_sec(self) -> float:
        return self.start_frame / self.fps

    @property
    def end_sec(self) -> float:
        return self.end_frame / self.fps


@dataclass
class EventWindow:
    """<event> 최상단 태그. trespass/swoon처럼 event 구간이 짧고 정확한
    클래스에서는 이걸 그대로 트리밍 기준으로 쓸 수 있다."""

    class_label: str
    session: str
    video_path: Path
    xml_path: Path
    fps: int
    event_name: str
    start_sec: float
    duration_sec: float


def _timestamp_to_sec(ts: str) -> float:
    """'HH:MM:SS.s' 또는 'MM:SS.s' 형태를 초 단위로 변환."""
    parts = ts.strip().split(":")
    parts = [float(p) for p in parts]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    h, m, s = parts
    return h * 3600 + m * 60 + s


def parse_annotation_xml(xml_path: Path) -> tuple[EventWindow, list[ActionSegment]]:
    """XML 파일 하나를 파싱해서 (event 윈도우, action 세그먼트 목록)을 반환.

    video_path는 xml과 같은 폴더/같은 이름(.mp4)이라고 가정한다 (실제 다운로드
    구조상 항상 그렇게 짝지어 있음).
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    class_label = root.findtext("folder", default="unknown")
    filename = root.findtext("filename", default=xml_path.stem + ".mp4")
    video_path = xml_path.parent / filename
    session = xml_path.parent.name

    header = root.find("header")
    fps = int(float(header.findtext("fps", default="30"))) if header is not None else 30
    total_frames = int(header.findtext("frames", default="0")) if header is not None else 0

    event_el = root.find("event")
    if event_el is not None:
        event = EventWindow(
            class_label=class_label,
            session=session,
            video_path=video_path,
            xml_path=xml_path,
            fps=fps,
            event_name=event_el.findtext("eventname", default=class_label),
            start_sec=_timestamp_to_sec(event_el.findtext("starttime", default="0")),
            duration_sec=_timestamp_to_sec(event_el.findtext("duration", default="0")),
        )
    else:
        event = EventWindow(
            class_label=class_label,
            session=session,
            video_path=video_path,
            xml_path=xml_path,
            fps=fps,
            event_name=class_label,
            start_sec=0.0,
            duration_sec=total_frames / fps if fps else 0.0,
        )

    segments: list[ActionSegment] = []
    for obj_el in root.findall("object"):
        raw_name = obj_el.findtext("objectname", default="person_1")
        object_id = normalize_object_id(raw_name)
        for action_el in obj_el.findall("action"):
            action_name = action_el.findtext("actionname", default="unknown")
            for frame_el in action_el.findall("frame"):
                start = int(frame_el.findtext("start"))
                end = int(frame_el.findtext("end"))
                segments.append(
                    ActionSegment(
                        class_label=class_label,
                        session=session,
                        video_path=video_path,
                        xml_path=xml_path,
                        fps=fps,
                        total_frames=total_frames,
                        object_id=object_id,
                        action_name=action_name,
                        start_frame=start,
                        end_frame=end,
                    )
                )

    return event, segments


def parse_dataset(base_dir: Path, class_label: str | None = None) -> list[ActionSegment]:
    """base_dir 아래 '세션폴더/*.xml' 전체를 스캔해서 ActionSegment 목록으로 반환.

    class_label을 넘기면 결과의 class_label 필드를 그 값으로 덮어쓴다 (XML의
    <folder> 값이 'assault'/'swoon'처럼 세분화되어 있지 않은 경우 대비).
    """
    all_segments: list[ActionSegment] = []
    for xml_path in sorted(Path(base_dir).glob("*/*.xml")):
        _, segments = parse_annotation_xml(xml_path)
        if class_label:
            for seg in segments:
                seg.class_label = class_label
        all_segments.extend(segments)
    return all_segments


def parse_dataset_events(base_dir: Path, class_label: str | None = None) -> list[EventWindow]:
    """base_dir 아래 모든 XML의 <event> 윈도우만 모아서 반환 (trespass/swoon처럼
    event 구간을 직접 트리밍에 쓰는 클래스용)."""
    events: list[EventWindow] = []
    for xml_path in sorted(Path(base_dir).glob("*/*.xml")):
        event, _ = parse_annotation_xml(xml_path)
        if class_label:
            event.class_label = class_label
        events.append(event)
    return events
