import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sentinelpose.rag import ManualIndex, generate_report, load_manuals, retrieve_manual

ROOT = Path(__file__).resolve().parent.parent
MANUALS_DIR = ROOT / "data" / "manuals"
OUT_PATH = ROOT / "outputs" / "rag_test_result.txt"

if __name__ == "__main__":
    lines = []
    chunks = load_manuals(MANUALS_DIR)
    lines.append(f"매뉴얼 청크 {len(chunks)}개 로드")
    for c in chunks:
        lines.append(f"  [{c.class_label}] {c.section}")

    index = ManualIndex(chunks)
    lines.append("인덱스 빌드 완료")

    event = {"event": "falldown", "time": "2026-09-09 14:32", "location": "지하주차장 B2"}
    lines.append(f"\n=== 이벤트: {event} ===")
    results = retrieve_manual(index, event, top_k=3)
    for chunk, score in results:
        lines.append(f"  유사도 {score:.3f} [{chunk.class_label}/{chunk.section}]: {chunk.text[:60]}...")

    lines.append("\n=== Qwen 리포트 생성 ===")
    try:
        report = generate_report(event, results)
        lines.append(report)
    except Exception as e:
        lines.append(f"실패: {e}")

    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"결과 저장: {OUT_PATH}")
