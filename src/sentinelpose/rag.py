"""이상행동 감지 결과 -> 대응 매뉴얼 검색(RAG) -> (선택) Qwen 리포트 생성.

문서 수가 적어서(클래스당 1개 마크다운, 섹션별로 몇 개 청크) 별도 벡터DB
없이 sentence-transformers 임베딩 + numpy 코사인 유사도로 직접 구현한다.
"""

from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL = "jhgan/ko-sroberta-multitask"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "sentinelpose-qwen"


@dataclass
class ManualChunk:
    class_label: str
    section: str
    text: str


def parse_manual(path: Path) -> list[ManualChunk]:
    """'## 섹션명' 단위로 마크다운을 청크로 분리."""
    text = path.read_text(encoding="utf-8")
    class_label = path.stem  # assault.md -> assault

    chunks = []
    sections = re.split(r"^## ", text, flags=re.MULTILINE)[1:]  # 첫 조각(# 제목)은 버림
    for section in sections:
        lines = section.strip().split("\n", 1)
        title = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else ""
        chunks.append(ManualChunk(class_label=class_label, section=title, text=body))
    return chunks


def load_manuals(manuals_dir: Path) -> list[ManualChunk]:
    chunks = []
    for path in sorted(manuals_dir.glob("*.md")):
        chunks.extend(parse_manual(path))
    return chunks


class ManualIndex:
    """청크들을 임베딩해서 코사인 유사도로 검색하는 초경량 벡터 인덱스."""

    def __init__(self, chunks: list[ManualChunk], model_name: str = EMBEDDING_MODEL):
        self.chunks = chunks
        self.model = SentenceTransformer(model_name)
        texts = [f"{c.section}: {c.text}" for c in chunks]
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        self.embeddings = np.array(embeddings)

    def search(self, query: str, top_k: int = 3, class_filter: str | None = None) -> list[tuple[ManualChunk, float]]:
        query_vec = self.model.encode([query], normalize_embeddings=True)[0]
        sims = self.embeddings @ query_vec  # 코사인 유사도 (이미 정규화됨)

        candidates = list(enumerate(sims))
        if class_filter:
            candidates = [(i, s) for i, s in candidates if self.chunks[i].class_label == class_filter]

        candidates.sort(key=lambda x: -x[1])
        return [(self.chunks[i], float(s)) for i, s in candidates[:top_k]]


def build_query(event: dict) -> str:
    """{"event": "falldown", "time": "...", "location": "..."} -> 검색 쿼리 문자열."""
    return f"{event['event']} 상황 발생. 시간: {event.get('time', '미상')}, 장소: {event.get('location', '미상')}. 대응 방법은?"


def retrieve_manual(index: ManualIndex, event: dict, top_k: int = 3) -> list[tuple[ManualChunk, float]]:
    """감지된 이벤트의 class_label로 필터링해서 검색 (다른 클래스 매뉴얼이 섞이지 않게)."""
    query = build_query(event)
    return index.search(query, top_k=top_k, class_filter=event["event"])


def generate_report(event: dict, chunks: list[tuple[ManualChunk, float]], model: str = OLLAMA_MODEL) -> str:
    """검색된 매뉴얼 청크 + 이벤트 메타데이터를 Qwen(Ollama)에 넣어 사고 리포트 생성."""
    manual_text = "\n\n".join(f"[{c.section}]\n{c.text}" for c, _ in chunks)
    prompt = f"""다음은 CCTV 이상행동 감지 시스템이 감지한 이벤트와 관련 대응 매뉴얼입니다.
이를 바탕으로 관제 담당자에게 보여줄 간결한 사고 리포트를 한국어로 작성하세요 (3~5문장).

이벤트: {event['event']}
시간: {event.get('time', '미상')}
장소: {event.get('location', '미상')}

관련 대응 매뉴얼:
{manual_text}

사고 리포트:"""

    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    text = result["response"].strip()
    # Qwen3는 <think>...</think>로 추론 과정을 먼저 출력함 - 관제 화면에는
    # 최종 리포트만 보여줘야 하므로 제거
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return text
