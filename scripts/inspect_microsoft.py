"""Microsoft GraphRAG Parquet 산출물과 근거 ID를 표로 확인한다."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
NAMES = ("documents", "text_units", "entities", "relationships", "communities", "community_reports")


def load_tables(output: Path) -> dict[str, pd.DataFrame]:
    tables = {}
    for name in NAMES:
        path = output / f"{name}.parquet"
        if path.exists():
            tables[name] = pd.read_parquet(path)
    if not tables:
        raise FileNotFoundError(f"Parquet 산출물이 없습니다: {output}. 인덱싱을 먼저 실행하세요.")
    return tables


def show(tables: dict[str, pd.DataFrame]) -> None:
    for name, frame in tables.items():
        print(f"\n[{name}] {len(frame)}행 | 열: {', '.join(frame.columns)}")
    for name, columns in {
        "documents": ["id", "title", "text_unit_ids"],
        "text_units": ["id", "text", "document_id"],
        "entities": ["title", "type", "text_unit_ids"],
        "relationships": ["source", "target", "description", "text_unit_ids"],
        "community_reports": ["title", "summary"],
    }.items():
        if name in tables:
            available = [column for column in columns if column in tables[name].columns]
            print(f"\n[{name} 미리 보기]\n{tables[name][available].head(8).to_string(index=False)}")


def trace_entity_path(tables: dict[str, pd.DataFrame], start: str, end: str) -> pd.DataFrame:
    """Find a graph path, then show each edge's source document for human review."""
    required = {"relationships", "text_units", "documents"}
    if not required <= tables.keys():
        raise ValueError(f"경로 감사에 필요한 표가 없습니다: {sorted(required - tables.keys())}")
    relations = tables["relationships"]
    graph = nx.Graph()
    for relation in relations.itertuples(index=False):
        graph.add_edge(relation.source, relation.target)
    if start not in graph or end not in graph:
        raise ValueError("질문 대상 노드가 추출된 그래프에 없습니다.")
    try:
        path = nx.shortest_path(graph, start, end)
    except nx.NetworkXNoPath as exc:
        raise ValueError("두 대상 사이의 경로가 없습니다.") from exc
    units = tables["text_units"].set_index("id")
    docs = tables["documents"].set_index("id")
    rows = []
    for left, right in zip(path, path[1:]):
        found = relations.loc[
            ((relations["source"] == left) & (relations["target"] == right))
            | ((relations["source"] == right) & (relations["target"] == left))
        ]
        relation = found.iloc[0]
        originals = []
        for unit_id in dict.fromkeys(relation["text_unit_ids"]):
            if unit_id not in units.index:
                continue
            doc_id = units.loc[unit_id, "document_id"]
            if doc_id in docs.index:
                doc = docs.loc[doc_id]
                pair = (str(doc["title"]), str(doc["text"]).strip())
                if pair not in originals:
                    originals.append(pair)
        rows.append({
            "경로에서 이동": f"{left} — {right}",
            "추출된 간선 방향": f"{relation['source']} → {relation['target']}",
            "추출된 설명": relation["description"],
            "원문 파일": ", ".join(title for title, _ in originals) or "찾지 못함",
            "원문 텍스트": " / ".join(text for _, text in originals) or "찾지 못함",
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "runs" / "microsoft" / "output")
    args = parser.parse_args()
    show(load_tables(args.output))
