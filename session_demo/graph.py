"""D1–D3의 명시 관계를 로컬 그래프와 Neo4j에서 동일하게 다룬다."""

from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path

import networkx as nx
from dotenv import load_dotenv
from neo4j import GraphDatabase

from . import DATA, ROOT
from .plot_fonts import apply_korean_font


def facts() -> dict:
    return json.loads((DATA / "graph_facts.json").read_text(encoding="utf-8"))


def validate_facts(model: dict | None = None) -> None:
    model = model or facts()
    nodes = {node["id"] for node in model["nodes"]}
    incident: set[str] = set()
    for edge in model["edges"]:
        if edge["from"] not in nodes or edge["to"] not in nodes:
            raise ValueError(f"고아 간선: {edge}")
        incident.update((edge["from"], edge["to"]))
        matches = list((DATA / "project").glob(f"{edge['source_id']}_*.md"))
        if len(matches) != 1 or edge["evidence"] not in matches[0].read_text(encoding="utf-8"):
            raise ValueError(f"원문에서 확인할 수 없는 간선: {edge}")
    if isolated := nodes - incident:
        raise ValueError(f"어떤 관계에도 연결되지 않은 노드: {sorted(isolated)}")


def local_graph(model: dict | None = None) -> nx.MultiDiGraph:
    model = model or facts()
    validate_facts(model)
    graph = nx.MultiDiGraph()
    for node in model["nodes"]:
        graph.add_node(node["id"], kind=node["kind"], name=node["name"])
    for edge in model["edges"]:
        graph.add_edge(edge["from"], edge["to"], key=edge["kind"], **edge)
    return graph


def relation_path(graph: nx.MultiDiGraph) -> list[dict]:
    """질문에 필요한 LEADS → PART_OF ← REVIEWS 패턴을 확인한다.

    단순 무방향 최단 경로를 사실 관계로 해석하지 않는다.
    """
    person, team = "person:ohesl", "team:security"
    for _, project, lead_key, lead in graph.out_edges(person, keys=True, data=True):
        if lead_key != "LEADS" or graph.nodes[project]["kind"] != "Project":
            continue
        for _, program, part_key, part in graph.out_edges(project, keys=True, data=True):
            if part_key != "PART_OF" or graph.nodes[program]["kind"] != "Program":
                continue
            for _, reviewed_program, review_key, review in graph.out_edges(team, keys=True, data=True):
                if review_key == "REVIEWS" and reviewed_program == program:
                    return [dict(lead), dict(part), dict(review)]
    return []


def evidence_answer(path: list[dict]) -> str:
    if len(path) != 3:
        return "세 문서의 관계 경로를 모두 확인하지 못했습니다. 직접 협업 여부도 판단할 수 없습니다."
    return (
        "오헤슬이 총괄하는 결제 시스템 리팩터링 프로젝트는 결제 안정화 프로그램에 속합니다 "
        "[D1, D2]. 보안팀은 그 프로그램의 보안 검토를 담당합니다 [D3]. "
        "따라서 두 대상은 같은 프로그램을 통해 연결됩니다. "
        "직접 협업했다는 사실은 이 자료에서 확인되지 않습니다."
    )


def draw_local_graph(graph: nx.MultiDiGraph, output: Path | None = None):
    import matplotlib.pyplot as plt

    plt.rcParams["axes.unicode_minus"] = False
    positions = {
        "person:ohesl": (-2.0, 0.9),
        "project:payment-refactor": (0.25, 0.9),
        "program:payment-stability": (1.25, -0.65),
        "team:security": (3.5, 0.9),
    }
    fig, ax = plt.subplots(figsize=(13, 5.5))
    nx.draw_networkx_nodes(graph, positions, node_size=5500, node_color="#dceef2", edgecolors="#39788b", ax=ax)
    nx.draw_networkx_edges(graph, positions, arrows=True, arrowsize=20, node_size=5500, edge_color="#39788b", ax=ax)
    labels = {n: textwrap.fill(graph.nodes[n]["name"], width=8, break_long_words=False) for n in graph}
    nx.draw_networkx_labels(graph, positions, labels=labels, font_size=10, ax=ax)
    nx.draw_networkx_edge_labels(
        graph,
        positions,
        edge_labels={(u, v): f"{k} [{d['source_id']}]" for u, v, k, d in graph.edges(keys=True, data=True)},
        font_size=9,
        label_pos=0.5,
        ax=ax,
    )
    apply_korean_font(ax)
    ax.set_xlim(-2.8, 4.3)
    ax.set_ylim(-1.5, 1.7)
    ax.axis("off")
    fig.tight_layout()
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output, dpi=160, bbox_inches="tight")
    return fig


def neo4j_driver():
    load_dotenv(ROOT / ".env", override=False)
    password = os.getenv("NEO4J_PASSWORD", "").strip()
    if not password:
        raise RuntimeError("NEO4J_PASSWORD가 없습니다. 로컬 그래프 부분은 연결 없이 실행할 수 있습니다.")
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), password),
    )
    driver.verify_connectivity()
    return driver


def write_neo4j(driver, model: dict | None = None) -> None:
    """SessionDemo 노드만 추가·갱신한다. 데이터베이스를 삭제하지 않는다."""
    model = model or facts()
    validate_facts(model)
    allowed_labels = {"Person", "Project", "Program", "Team"}
    allowed_relations = {"LEADS", "PART_OF", "REVIEWS"}
    for node in model["nodes"]:
        label = node["kind"]
        if label not in allowed_labels:
            raise ValueError(f"허용하지 않은 노드 유형: {label}")
        driver.execute_query(
            f"MERGE (n:SessionDemo:{label} {{demo_key: $key}}) SET n.name = $name",
            key=node["id"], name=node["name"],
        )
    for edge in model["edges"]:
        relation = edge["kind"]
        if relation not in allowed_relations:
            raise ValueError(f"허용하지 않은 관계 유형: {relation}")
        driver.execute_query(
            f"MATCH (a:SessionDemo {{demo_key: $from_key}}), (b:SessionDemo {{demo_key: $to_key}}) "
            f"MERGE (a)-[r:{relation} {{source_id: $source_id}}]->(b) "
            "SET r.evidence = $evidence, r.demo = true",
            from_key=edge["from"], to_key=edge["to"],
            source_id=edge["source_id"], evidence=edge["evidence"],
        )


PATH_QUERY = """
MATCH (person:SessionDemo:Person {demo_key: $person})-[r1:LEADS]->
      (project:SessionDemo:Project)-[r2:PART_OF]->
      (program:SessionDemo:Program)<-[r3:REVIEWS]-
      (team:SessionDemo:Team {demo_key: $team})
RETURN person.name AS person, project.name AS project,
       program.name AS program, team.name AS team,
       type(r1) AS relation1, r1.source_id AS source1, r1.evidence AS evidence1,
       type(r2) AS relation2, r2.source_id AS source2, r2.evidence AS evidence2,
       type(r3) AS relation3, r3.source_id AS source3, r3.evidence AS evidence3
"""


VISUAL_QUERY = """
MATCH (person:SessionDemo:Person {demo_key: 'person:ohesl'})-[r1:LEADS]->
      (project:SessionDemo:Project)-[r2:PART_OF]->
      (program:SessionDemo:Program)<-[r3:REVIEWS]-
      (team:SessionDemo:Team {demo_key: 'team:security'})
RETURN person, r1, project, r2, program, r3, team
"""


def query_neo4j_path(driver) -> list[dict]:
    records, _, _ = driver.execute_query(
        PATH_QUERY, person="person:ohesl", team="team:security"
    )
    return [record.data() for record in records]
