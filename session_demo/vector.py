"""Chroma에 명시적인 TF-IDF 벡터를 넣어 top-k 회수 과정을 관찰한다.

문자 n-gram TF-IDF는 오프라인 재현을 위한 검색 벡터다. 의미 임베딩 모델의
성능을 대표하지 않는다. 핵심 관찰은 실제 회수 ID와 근거 누락 여부다.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import chromadb
from sklearn.feature_extraction.text import TfidfVectorizer

from .data import Document


@dataclass(frozen=True)
class SearchHit:
    id: str
    title: str
    text: str
    distance: float
    rank: int


class ChromaTfidfIndex:
    def __init__(self, documents: list[Document]):
        if not documents:
            raise ValueError("검색할 문서가 없습니다.")
        self.vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(2, 4), norm="l2")
        matrix = self.vectorizer.fit_transform([doc.text for doc in documents]).toarray()
        self.client = chromadb.EphemeralClient()
        self.collection = self.client.create_collection(name=f"session-{uuid4().hex[:12]}")
        self.collection.add(
            ids=[doc.id for doc in documents],
            documents=[doc.text for doc in documents],
            metadatas=[{"title": doc.title} for doc in documents],
            embeddings=matrix.tolist(),
        )
        self.count = len(documents)

    def search(self, question: str, k: int) -> list[SearchHit]:
        if k < 1:
            raise ValueError("k는 1 이상이어야 합니다.")
        query_vector = self.vectorizer.transform([question]).toarray()[0].tolist()
        result = self.collection.query(
            query_embeddings=[query_vector],
            n_results=min(k, self.count),
            include=["documents", "metadatas", "distances"],
        )
        return [
            SearchHit(
                id=doc_id,
                title=result["metadatas"][0][i]["title"],
                text=result["documents"][0][i],
                distance=float(result["distances"][0][i]),
                rank=i + 1,
            )
            for i, doc_id in enumerate(result["ids"][0])
        ]


def hit_rows(hits: list[SearchHit]) -> list[dict[str, object]]:
    return [
        {"순위": hit.rank, "ID": hit.id, "거리(작을수록 가까움)": round(hit.distance, 4), "회수된 문장": hit.text}
        for hit in hits
    ]

