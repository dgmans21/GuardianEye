from pathlib import Path

from sentinelpose.rag import build_query, parse_manual

SAMPLE_MD = """# 폭행(assault) 대응 매뉴얼

## 즉시 대응
- 첫 번째 지침
- 두 번째 지침

## 신고 절차
112에 신고한다.
"""


def test_parse_manual_splits_by_section(tmp_path):
    p = tmp_path / "assault.md"
    p.write_text(SAMPLE_MD, encoding="utf-8")

    chunks = parse_manual(p)

    assert len(chunks) == 2
    assert chunks[0].class_label == "assault"
    assert chunks[0].section == "즉시 대응"
    assert "첫 번째 지침" in chunks[0].text
    assert chunks[1].section == "신고 절차"
    assert "112" in chunks[1].text


def test_build_query_includes_event_fields():
    event = {"event": "falldown", "time": "14:32", "location": "B2"}
    query = build_query(event)
    assert "falldown" in query
    assert "14:32" in query
    assert "B2" in query


def test_build_query_handles_missing_fields():
    event = {"event": "intrusion"}
    query = build_query(event)
    assert "intrusion" in query
    assert "미상" in query
