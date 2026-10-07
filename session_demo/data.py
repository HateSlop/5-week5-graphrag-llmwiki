"""시연 자료를 읽고, 회수된 근거가 충분한지 표시한다."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import DATA


@dataclass(frozen=True)
class Document:
    id: str
    title: str
    text: str
    path: Path | None = None


def project_documents(ids: tuple[str, ...] = ("D1", "D2", "D3")) -> list[Document]:
    """D1–D6 중 지정한 문서를 ID 순서로 읽는다."""
    result: list[Document] = []
    for doc_id in ids:
        matches = list((DATA / "project").glob(f"{doc_id}_*.md"))
        if len(matches) != 1:
            raise FileNotFoundError(f"{doc_id} 문서는 정확히 하나여야 합니다: {matches}")
        path = matches[0]
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        result.append(Document(doc_id, lines[0].removeprefix("# "), "\n".join(lines[1:]).strip(), path))
    return result


def policy_chunks() -> list[Document]:
    rows = json.loads((DATA / "policy_chunks.json").read_text(encoding="utf-8"))
    return [Document(row["id"], row["section"], row["text"]) for row in rows]


def relation_coverage(retrieved_ids: list[str] | tuple[str, ...]) -> dict[str, object]:
    """D1–D3 예제에 필요한 근거가 모두 보였는지 판정한다.

    모델 답변의 정확도를 측정하는 함수가 아니다. 검색 단계의 근거 범위만 본다.
    """
    expected = {"D1", "D2", "D3"}
    got = set(retrieved_ids)
    return {"retrieved": sorted(got), "missing": sorted(expected - got), "complete": expected <= got}


def policy_coverage(retrieved_ids: list[str] | tuple[str, ...]) -> dict[str, object]:
    """Check retrieval coverage; complete does not measure answer correctness."""
    expected = {"A", "B", "C"}
    got = set(retrieved_ids)
    return {"retrieved": sorted(got), "missing": sorted(expected - got), "complete": expected <= got}

