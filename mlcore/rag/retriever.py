import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+", re.UNICODE)


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    source: str
    score: float


@dataclass(frozen=True)
class Chunk:
    text: str
    source: str
    tf: dict[str, int]
    norm: float


class KnowledgeRetriever:
    def __init__(self, chunks: list[Chunk], idf: dict[str, float], top_k: int):
        self._chunks = chunks
        self._idf = idf
        self._top_k = top_k

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    @classmethod
    def from_directory(
        cls,
        knowledge_dir: str,
        chunk_size_chars: int,
        chunk_overlap_chars: int,
        top_k: int,
    ) -> "KnowledgeRetriever":
        root = Path(knowledge_dir)
        if not root.exists():
            return cls(chunks=[], idf={}, top_k=top_k)

        raw_chunks: list[tuple[str, str]] = []
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".md", ".txt"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            source = str(path.relative_to(root))
            for piece in _split_text(text, chunk_size_chars, chunk_overlap_chars):
                raw_chunks.append((piece, source))

        if not raw_chunks:
            return cls(chunks=[], idf={}, top_k=top_k)

        tokenized_chunks: list[dict[str, int]] = []
        doc_freq: dict[str, int] = {}
        for text, _ in raw_chunks:
            tf = _term_frequency(text)
            tokenized_chunks.append(tf)
            for token in tf.keys():
                doc_freq[token] = doc_freq.get(token, 0) + 1

        docs_count = len(raw_chunks)
        idf = {
            token: math.log((1 + docs_count) / (1 + freq)) + 1.0
            for token, freq in doc_freq.items()
        }
        chunks: list[Chunk] = []
        for (text, source), tf in zip(raw_chunks, tokenized_chunks):
            norm_sq = 0.0
            for token, freq in tf.items():
                weight = freq * idf.get(token, 0.0)
                norm_sq += weight * weight
            norm = math.sqrt(norm_sq) if norm_sq > 0 else 1.0
            chunks.append(Chunk(text=text, source=source, tf=tf, norm=norm))

        return cls(chunks=chunks, idf=idf, top_k=top_k)

    def retrieve(self, query: str, top_k: Optional[int] = None) -> list[RetrievedChunk]:
        if not self._chunks:
            return []
        q_tf = _term_frequency(query)
        if not q_tf:
            return []

        q_norm_sq = 0.0
        for token, freq in q_tf.items():
            weight = freq * self._idf.get(token, 0.0)
            q_norm_sq += weight * weight
        q_norm = math.sqrt(q_norm_sq) if q_norm_sq > 0 else 1.0

        ranked: list[RetrievedChunk] = []
        for chunk in self._chunks:
            dot = 0.0
            for token, q_freq in q_tf.items():
                idf = self._idf.get(token)
                if idf is None:
                    continue
                c_freq = chunk.tf.get(token, 0)
                if c_freq == 0:
                    continue
                dot += (q_freq * idf) * (c_freq * idf)
            if dot <= 0:
                continue
            score = dot / (q_norm * chunk.norm)
            ranked.append(RetrievedChunk(text=chunk.text, source=chunk.source, score=score))

        ranked.sort(key=lambda x: x.score, reverse=True)
        limit = self._top_k if top_k is None else top_k
        return ranked[: max(limit, 0)]


def _split_text(text: str, chunk_size_chars: int, chunk_overlap_chars: int) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []

    size = max(chunk_size_chars, 200)
    overlap = max(min(chunk_overlap_chars, size - 1), 0)
    chunks: list[str] = []
    start = 0
    total = len(stripped)
    while start < total:
        end = min(start + size, total)
        piece = stripped[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= total:
            break
        start = end - overlap
    return chunks


def _term_frequency(text: str) -> dict[str, int]:
    tf: dict[str, int] = {}
    for token in _TOKEN_RE.findall(text.lower()):
        tf[token] = tf.get(token, 0) + 1
    return tf
