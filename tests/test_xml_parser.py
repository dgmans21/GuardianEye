from pathlib import Path

import pytest

from sentinelpose.data.xml_parser import (
    normalize_object_id,
    parse_annotation_xml,
    parse_dataset,
)

SAMPLE_XML = """<?xml version='1.0' encoding='utf-8'?>
<annotation>
    <folder>assault</folder>
    <filename>10-1_cam01_assault01_place07_night_spring.mp4</filename>
    <header>
        <duration>00:00:10.0</duration>
        <fps>30</fps>
        <frames>300</frames>
        <population>2</population>
    </header>
    <event>
        <eventname>assault</eventname>
        <starttime>00:00:01.0</starttime>
        <duration>00:00:08.0</duration>
    </event>
    <object>
        <objectname>person_1</objectname>
        <action>
            <actionname>pushing</actionname>
            <frame><start>10</start><end>40</end></frame>
            <frame><start>100</start><end>120</end></frame>
        </action>
    </object>
    <object>
        <objectname>Person02</objectname>
        <action>
            <actionname>falldown</actionname>
            <frame><start>150</start><end>200</end></frame>
        </action>
    </object>
</annotation>
"""


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("person_1", "person_1"),
        ("Person_1", "person_1"),
        ("Person", "person_1"),
        ("Person01", "person_1"),
        ("person_2", "person_2"),
        ("Person02", "person_2"),
    ],
)
def test_normalize_object_id(raw, expected):
    assert normalize_object_id(raw) == expected


def _write_sample(tmp_path: Path) -> Path:
    session_dir = tmp_path / "10-1"
    session_dir.mkdir()
    xml_path = session_dir / "10-1_cam01_assault01_place07_night_spring.xml"
    xml_path.write_text(SAMPLE_XML, encoding="utf-8")
    return xml_path


def test_parse_annotation_xml_extracts_event_and_segments(tmp_path):
    xml_path = _write_sample(tmp_path)
    event, segments = parse_annotation_xml(xml_path)

    assert event.event_name == "assault"
    assert event.start_sec == pytest.approx(1.0)
    assert event.duration_sec == pytest.approx(8.0)

    # person_1 pushing x2 + person_2(정규화된 Person01) falldown x1 = 3개
    assert len(segments) == 3

    pushing = [s for s in segments if s.action_name == "pushing"]
    assert len(pushing) == 2
    assert pushing[0].object_id == "person_1"
    assert pushing[0].start_frame == 10
    assert pushing[0].end_frame == 40
    assert pushing[0].duration_frames == 30

    falldown = [s for s in segments if s.action_name == "falldown"]
    assert len(falldown) == 1
    assert falldown[0].object_id == "person_2"  # Person02 -> person_2로 정규화됨


def test_parse_dataset_overrides_class_label(tmp_path):
    _write_sample(tmp_path)
    segments = parse_dataset(tmp_path, class_label="assault")
    assert len(segments) == 3
    assert all(s.class_label == "assault" for s in segments)
