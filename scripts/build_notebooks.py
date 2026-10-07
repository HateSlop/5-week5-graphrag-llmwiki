"""소스가 보이는 네 개의 교육용 .ipynb를 생성한다 (표준 라이브러리만 사용)."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks"


def md(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": textwrap.dedent(source).strip() + "\n"}


def code(source: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": textwrap.dedent(source).strip() + "\n"}


def write(name: str, cells: list[dict]) -> None:
    for number, cell in enumerate(cells, start=1):
        cell["id"] = f"cell-{number:02d}"
    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python (GraphRAG LLM Wiki)", "language": "python", "name": "hateslop-graphrag-wiki"},
            "language_info": {"name": "python", "version": "3.12"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    OUT.mkdir(exist_ok=True)
    (OUT / name).write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def notebook_01() -> list[dict]:
    return [
        md("""
        # 01. 벡터 RAG: 실제 회수 근거를 먼저 보기

        지난주 사용한 ChromaDB 흐름을 작은 문서로 복습합니다. 이 노트북의 검색 벡터는 **한국어 문자 n-gram TF-IDF**입니다. 모델을 내려받지 않아도 같은 절차를 실행할 수 있지만, 최신 의미 임베딩의 품질을 평가하려는 실험은 아닙니다.

        관찰 대상은 두 가지입니다. (1) 정책 예외 B가 검색 문맥에서 빠지면 어떤 답의 근거가 부족해지는가? (2) D1–D3의 관계 질문에 top-k=2로 어떤 청크가 회수되는가?
        """),
        code("""
        from pathlib import Path
        import sys
        import pandas as pd
        from IPython.display import display

        ROOT = Path.cwd().resolve()
        if ROOT.name == "notebooks":
            ROOT = ROOT.parent
        sys.path.insert(0, str(ROOT))

        from session_demo.data import Document, policy_chunks, project_documents, policy_coverage, relation_coverage
        from session_demo.vector import ChromaTfidfIndex, hit_rows
        print("자료 폴더:", ROOT / "data")
        """),
        md("""
        ## 1. 정책 예외가 청크 사이에 나뉜 경우

        먼저 원문 A·B·C를 모두 읽어 봅니다. 질문은 **“2025년 4월 가입한 VIP 고객의 해외 송금 수수료는 면제되는가?”**입니다. 원문 전체의 정답은 **면제되지 않는다**입니다. B가 해외 송금의 예외를 명시하기 때문입니다.
        """),
        code("""
        policy = policy_chunks()
        display(pd.DataFrame([{"ID": d.id, "문장": d.text} for d in policy]))
        policy_question = "2025년 4월 가입한 VIP 고객의 해외 송금 수수료는 면제돼?"
        index_policy = ChromaTfidfIndex(policy)
        policy_hits = index_policy.search(policy_question, k=2)
        display(pd.DataFrame(hit_rows(policy_hits)))
        print("실제 회수 ID:", [h.id for h in policy_hits])
        policy_found = policy_coverage([h.id for h in policy_hits])
        print("누락된 청크:", policy_found["missing"])
        """),
        md("""
        **검색 결과를 그대로 읽으세요.** 위의 `누락된 청크`는 답변 결과가 아니라 검색되지 않은 근거입니다. 검색기의 순위가 어떻게 나왔든 top-k=2에는 세 청크가 모두 들어갈 수 없습니다. 다만 `B`가 빠졌다는 결과와 `A`나 `C`가 빠졌다는 결과는 답변에 미치는 영향이 다릅니다. 아래 A·C만 제공하는 장면은 **의도적으로 만든 반례**이며, 위 Chroma의 실제 순위라고 주장하지 않습니다.
        """),
        code("""
        controlled_ids = ["A", "C"]
        controlled = [d for d in policy if d.id in controlled_ids]
        display(pd.DataFrame([{"제공된 ID": d.id, "LLM에 보이는 문장": d.text} for d in controlled]))
        controlled_coverage = policy_coverage(controlled_ids)
        print("제공된 청크:", controlled_coverage["retrieved"])
        print("누락된 예외 청크:", controlled_coverage["missing"])
        print("A·C만 보고 일반 규칙을 적용한 답(가능한 오답, LLM 출력 아님): 면제된다")
        print("A·B·C 전체 정책의 정답: 면제되지 않는다 [B]")
        """),
        md("""
        A·C만 보고 ‘면제된다’고 답하면 전체 정책의 예외 B와 충돌합니다. 위의 오답은 **누락된 근거의 위험을 보여주기 위해 구성한 예시**이며 실제 LLM 응답은 아닙니다. 모델이 반드시 이렇게 답한다는 뜻도 아닙니다.

        ### 같은 RAG에서도 보완할 수 있다

        실제 검색에서 관련 청크 하나를 찾으면 **부모 정책 문서 전체**나 **앞뒤 이웃 청크**를 함께 회수하도록 설계할 수 있습니다. 아래는 세 문장을 부모 문서 한 단위로 색인한 단순한 대안입니다. 이 사례만으로 그래프가 필요하다고 결론 내리지 않습니다.
        """),
        code("""
        parent = Document("POLICY", "VIP 정책 전체", " ".join(f"[{d.id}] {d.text}" for d in policy))
        parent_hits = ChromaTfidfIndex([parent]).search(policy_question, k=1)
        display(pd.DataFrame(hit_rows(parent_hits)))
        print("부모 문서 안에는 A·B·C가 모두 들어 있습니다.")
        """),
        md("""
        ## 2. 세 문서의 관계를 물으면 top-k=2에서 무엇이 빠질까?

자료는 D1 담당자, D2 프로그램 소속, D3 보안팀 역할입니다. 세 사실을 모두 연결해야 **오헤슬과 보안팀이 같은 프로그램을 통해 어떤 관계인지** 설명할 수 있습니다. 직접 협업을 추론할 근거는 없습니다.
        """),
        code("""
        docs = project_documents(("D1", "D2", "D3"))
        display(pd.DataFrame([{"ID": d.id, "제목": d.title, "원문": d.text} for d in docs]))
        relation_question = "오헤슬과 보안팀은 어떤 관계인가?"
        index_relation = ChromaTfidfIndex(docs)
        top2 = index_relation.search(relation_question, k=2)
        display(pd.DataFrame(hit_rows(top2)))
        print("실제 top-2 ID:", [h.id for h in top2])
        print("근거 범위:", relation_coverage([h.id for h in top2]))
        """),
        md("""
        `missing`에 나온 문서가 왜 필요한지 해당 원문을 다시 확인해 봅니다. **top-k=2가 늘 특정 두 문서를 고른다고 가정하지 않습니다.** 검색 방식·질문 표현·임베딩 모델이 바뀌면 순위도 달라집니다.

        `k=3`이면 이 작은 세 문서 예제에서는 모든 근거가 들어옵니다. 실제 시스템에서는 이웃·부모 회수, 질문 분해, 하이브리드 검색, 재순위화도 후보입니다.
        """),
        code("""
        top3 = index_relation.search(relation_question, k=3)
        display(pd.DataFrame(hit_rows(top3)))
        print("top-3 근거 범위:", relation_coverage([h.id for h in top3]))
        """),
        md("""
        ## 3. 생성 단계는 선택적으로 실행

아래를 `True`로 바꾸면 **실제 회수된 문장만** LLM에 보냅니다. API 비용이 발생합니다. `top2`와 `top3`의 답을 비교할 때 모델의 표현 차이보다 먼저 제공된 근거 ID를 확인합니다.
        """),
        code("""
        RUN_LLM = False
        if RUN_LLM:
            from session_demo.llm import grounded_answer
            by_id = {d.id: d for d in docs}
            for label, hits in [("top-2", top2), ("top-3", top3)]:
                evidence = [by_id[h.id] for h in hits]
                print(f"\\n[{label}] 제공 ID: {[d.id for d in evidence]}")
                print(grounded_answer(relation_question, evidence))
        else:
            print("LLM 호출을 건너뛰었습니다. 검색 근거 비교는 이미 실행되었습니다.")
        """),
        md("""
        **생성 답변도 근거와 대조:** D3는 보안팀이 *프로그램*을 검토한다고만 말합니다. 모델이 이를 "소속 프로젝트를 직접 검토한다"로 확대했다면 그 문장은 근거를 넘은 추론입니다. top-3에 세 문서가 모두 들어와도 답변 자체를 검토해야 합니다.

        **다음:** `02_graph_neo4j.ipynb`에서는 D1–D3를 명시적 관계로 보관하고, 질문에 맞는 경로와 각 선의 원문을 회수합니다. 그 그래프는 수업용으로 사람이 확인해 입력한 것입니다.
        """),
    ]


def notebook_02() -> list[dict]:
    return [
        md("""
        # 02. GraphRAG의 관계 검색 기초: 사람이 만든 작은 그래프

이 노트북은 원문에서 관계를 어떻게 표현하고 조회하는지 살펴보는 단계입니다. `data/graph_facts.json`은 D1–D3를 **사람이 읽고 직접 만든 구조화 결과**이며, 자동 GraphRAG 결과가 아닙니다. 관계 추출의 자동화와 그 오류 가능성은 3번 노트북에서 다룹니다.

| 원문 | 원문에서 확인한 사실 | 기록한 방향 관계 |
| --- | --- | --- |
| D1 | 오헤슬이 결제 시스템 리팩터링을 총괄 | 오헤슬 `-LEADS→` 프로젝트 |
| D2 | 리팩터링 프로젝트가 결제 안정화 프로그램에 속함 | 프로젝트 `-PART_OF→` 프로그램 |
| D3 | 보안팀이 프로그램의 보안 검토를 담당 | 보안팀 `-REVIEWS→` 프로그램 |

사람·프로젝트·프로그램·팀을 노드로, 세 동사를 관계로 정했습니다. 각 관계에는 원문 ID와 근거 문장을 함께 넣었습니다. 첫 셀의 `validate_facts`는 그 근거 문장이 실제 D1–D3에 있는지 확인하지만, 원문에서 관계를 스스로 발견하지는 않습니다.
        """),
        code("""
        from pathlib import Path
        import sys
        import pandas as pd
        from IPython.display import display

        ROOT = Path.cwd().resolve()
        if ROOT.name == "notebooks":
            ROOT = ROOT.parent
        sys.path.insert(0, str(ROOT))
        from session_demo.graph import facts, validate_facts, local_graph, relation_path, evidence_answer, draw_local_graph
        import matplotlib.pyplot as plt

        model = facts()
        validate_facts(model)  # 간선의 근거 문장이 실제 D1–D3 원문에 있는지 확인
        display(pd.DataFrame(model["nodes"]))
        display(pd.DataFrame(model["edges"]))
        """),
        md("""
        ## 1. 관계의 이름과 방향 읽기

`local_graph(model)`은 위 노드와 간선을 NetworkX의 **메모리 그래프 자료구조**로 만듭니다. 그림은 그 자료를 보여주는 화면일 뿐, 간선이 그림에서 새로 만들어진 것은 아닙니다. `LEADS`: 오헤슬 → 프로젝트, `PART_OF`: 프로젝트 → 프로그램, `REVIEWS`: 보안팀 → 프로그램입니다. 프로그램에 두 대상이 연결되어 있어도 **오헤슬 ↔ 보안팀 직접 협업** 간선은 없습니다.
        """),
        code("""
        graph = local_graph(model)
        fig = draw_local_graph(graph, ROOT / "runs" / "figures" / "small_graph.png")
        display(fig)
        plt.close(fig)
        print("그림 저장:", ROOT / "runs" / "figures" / "small_graph.png")
        """),
        md("""
        ## 2. 경로와 세 출처를 함께 회수

질문: **“오헤슬과 보안팀은 어떤 관계인가?”** 그래프에는 D1·D2·D3의 **개별 간선**이 저장돼 있습니다. 두 사람·팀의 연결을 설명하는 경로가 별도 정답으로 저장된 것은 아닙니다. `relation_path`는 오헤슬에서 시작해 `LEADS → PART_OF ← REVIEWS`라는 관계 종류와 방향을 만족하는 간선을 차례로 확인하고, 세 관계와 출처를 돌려줍니다. 무방향 최단 경로 검색은 아닙니다.

노드가 네 개인 이 예제에서는 경로를 눈으로도 알 수 있습니다. 이 조회는 새로운 사실을 발견하거나 임의의 자연어 질문을 처리하기보다 **관계 패턴을 조회하는 방식**을 보여줍니다. LLM은 호출하지 않습니다. `evidence_answer`는 경로가 확인되면 미리 작성한 문장을, 경로가 없으면 근거가 부족하다는 문장을 반환합니다.
        """),
        code("""
        path = relation_path(graph)
        display(pd.DataFrame([{
            "시작": graph.nodes[edge["from"]]["name"],
            "관계": edge["kind"],
            "도착": graph.nodes[edge["to"]]["name"],
            "출처": edge["source_id"],
            "원문 근거": edge["evidence"],
        } for edge in path]))
        print("[규칙 기반 예시 문장 · LLM 호출 없음]")
        print(evidence_answer(path))
        """),
        md("""
        ## 3. 관계가 하나 빠지면 경로도 끊긴다

그래프도 누락된 간선을 자동으로 복원하지 않습니다. D2 관계를 제거한 복사본에서 같은 패턴을 찾아 봅니다. 원래 그래프는 그대로 둡니다.
        """),
        code("""
        import copy
        incomplete = copy.deepcopy(model)
        incomplete["edges"] = [edge for edge in incomplete["edges"] if edge["source_id"] != "D2"]
        broken_graph = local_graph(incomplete)
        broken_path = relation_path(broken_graph)
        print("D2가 빠진 경로:", broken_path)
        print(evidence_answer(broken_path))
        """),
        md("""
        ## 4. Neo4j Browser에서 확인하기 (선택)

앞의 1~3번은 `graph_facts.json`에 사람이 확인해 적어 둔 관계를 **NetworkX 메모리 그래프**로 읽은 것입니다. 4번도 **바로 그 동일한 자료**를 사용합니다. `write_neo4j(driver, model)`이 네 노드와 세 관계를 Neo4j에 `MERGE`하고, Cypher로 같은 경로와 출처를 조회합니다. Neo4j가 D1–D3 원문을 분석해 관계를 자동 추출하는 과정은 없습니다. NetworkX도 앞에서 실제 그래프 구조를 만들어 탐색했습니다. Neo4j는 같은 구조를 **프로세스 밖의 데이터베이스에 보관**하고 Cypher로 조회하며 Browser에서 살펴볼 수 있게 합니다. 이 네 노드 예제만으로 Neo4j가 더 정확하거나 꼭 필요하다고 결론 내릴 수는 없습니다.

Neo4j 인스턴스를 켜고 `.env`에 접속 정보를 설정한 뒤 `CONNECT_NEO4J`를 `True`로 바꿉니다. 다른 노드는 삭제하지 않습니다. 출력된 Cypher를 Neo4j Browser에 붙여 넣으면 저장된 관계를 그래프로 볼 수 있습니다.
        """),
        code("""
        CONNECT_NEO4J = False
        if CONNECT_NEO4J:
            from session_demo.graph import neo4j_driver, write_neo4j, query_neo4j_path, VISUAL_QUERY
            with neo4j_driver() as driver:
                write_neo4j(driver, model)
                display(pd.DataFrame(query_neo4j_path(driver)))
            print("Neo4j Browser 그래프 시각화용 Cypher:\\n", VISUAL_QUERY)
        else:
            print("Neo4j 연결을 건너뛰었습니다. 위 로컬 그림과 경로는 이미 실행되었습니다.")
        """),
        md("""
        **무엇을 확인했나:** 사람이 만든 그래프에서 관계의 종류·방향·출처를 확인하고, 질문에 필요한 경로를 조회했습니다. 간선이 빠지면 경로도 끊깁니다. Neo4j는 같은 데이터를 저장·조회하는 다른 방식이며, 이 예제는 GraphRAG의 자동 추출 성능이나 답변 품질 우위를 증명하지 않습니다. `03_microsoft_graphrag.ipynb`에서는 원문을 자동 인덱싱했을 때 실제로 어떤 관계와 산출물이 나오는지 확인합니다.
        """),
    ]


def notebook_03() -> list[dict]:
    return [
        md("""
        # 03. Microsoft GraphRAG: 여섯 원문에서 자동 인덱스까지

        2번 노트북에서는 사람이 D1–D3의 관계를 직접 골랐습니다. 여기서는 [Microsoft GraphRAG](https://microsoft.github.io/graphrag/get_started/)가 문서를 읽고 **TextUnit, 엔터티·관계, 커뮤니티 보고서**를 만드는 과정을 살펴봅니다. 자동 추출 결과가 사람이 만든 그래프와 같으리라고 가정하지 않습니다.

        이 노트북에서 쓰는 자료와 파일 흐름은 다음과 같습니다.

        ```text
        data/project/D1_owner.md … D6_decision.md      원본 Markdown 6개
                ↓ scripts/prepare_microsoft.py
        runs/microsoft/input/*.pdf 또는 *.txt          GraphRAG에 넣는 사본
                ↓ graphrag index --method standard
        runs/microsoft/output/*.parquet               추출·요약·연결 결과
                ↓ 이 노트북의 표·그림 확인 / graphrag query
        출처를 확인한 답변
        ```

        위 경로는 모두 **이 저장소 안**에 있습니다. `runs/`는 실행하면서 생기는 작업공간이므로 새로 내려받은 저장소에는 없습니다. 입력 준비는 API를 호출하지 않지만, 실제 인덱싱과 새 Local·Global 질의는 모델 API를 사용합니다. Microsoft의 [기본 인덱싱 흐름](https://microsoft.github.io/graphrag/index/default_dataflow/)과 [출력 형식](https://microsoft.github.io/graphrag/index/outputs/)을 기준으로 설명합니다.
        """),
        code("""
        from pathlib import Path
        import os, shutil, subprocess, sys
        import pandas as pd
        from IPython.display import display, Markdown

        ROOT = Path.cwd().resolve()
        if ROOT.name == "notebooks":
            ROOT = ROOT.parent
        sys.path.insert(0, str(ROOT))
        sys.path.insert(0, str(ROOT / "scripts"))
        from session_demo.data import project_documents
        from inspect_microsoft import load_tables, show
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env", override=False)

        WORKSPACE = ROOT / "runs" / "microsoft"
        local_cli = Path(sys.executable).parent / ("Scripts/graphrag.exe" if os.name == "nt" else "bin/graphrag")
        GRAPHRAG_CLI = str(local_cli) if local_cli.is_file() else shutil.which("graphrag")
        documents = project_documents(("D1", "D2", "D3", "D4", "D5", "D6"))
        display(pd.DataFrame([{
            "ID": d.id, "원본 파일": d.path.relative_to(ROOT).as_posix(),
            "제목": d.title, "원문": d.text,
        } for d in documents]))
        print("원본 문서 폴더:", ROOT / "data" / "project")
        print("GraphRAG 작업공간:", WORKSPACE)
        """),
        md("""
        ## 1. 원본을 확인하고 GraphRAG 입력을 준비하기

        **바로 위 코드 셀**은 `project_documents(...)`로 `data/project/`의 D1–D6 Markdown을 읽어 파일명·제목·본문을 표시합니다. `.env`의 설정은 읽지만 키 값은 출력하지 않습니다. `WORKSPACE`는 GraphRAG가 입력과 산출물을 보관할 `runs/microsoft/`입니다.

        **아래 준비 코드 셀**에서 `RUN_PREPARE=True`로 설정하면 `scripts/prepare_microsoft.py`가 실행됩니다. 이 스크립트는 다음 일을 합니다.

        1. `graphrag init`으로 `runs/microsoft/settings.yaml`을 만듭니다. 추출 대상에 사람·프로젝트·프로그램·팀 등을 지정합니다.
        2. `INPUT_FORMAT="pdf"`이면 원본 Markdown 여섯 개를 각각 **텍스트가 들어 있는 PDF**로 만들어 `runs/microsoft/input/`에 둡니다. GraphRAG가 MarkItDown으로 읽도록 설정하고, 변환된 텍스트에 원문 문장이 남아 있는지 확인합니다. 이미지 스캔 PDF의 OCR을 수행하는 예시는 아닙니다. `"text"`이면 같은 내용을 UTF-8 `.txt`로 복사합니다.
        3. 준비된 입력 파일 목록과 GraphRAG CLI 설치 여부를 출력합니다. 여기까지는 인덱싱이나 답변 생성이 아닙니다.

        `RUN_PREPARE=False`는 기존 작업공간만 확인합니다. 작업공간이 이미 있으면 `True`여도 다시 만들지 않으므로, **`INPUT_FORMAT`을 바꾸는 것만으로 기존 PDF가 TXT로 바뀌지는 않습니다.** 처음 준비할 때 형식을 정하고, 한 작업공간에 두 형식을 섞지 않습니다. 입력 준비에도 `requirements-microsoft.txt`로 설치한 CLI가 필요합니다.
        """),
        code("""
        RUN_PREPARE = False
        INPUT_FORMAT = "pdf"  # 텍스트형 PDF 시연. 같은 WORKSPACE에 두 형식을 섞지 않습니다.
        if RUN_PREPARE:
            if WORKSPACE.exists():
                print("기존 작업공간:", WORKSPACE)
            else:
                subprocess.run([sys.executable, str(ROOT / "scripts" / "prepare_microsoft.py"), "--format", INPUT_FORMAT], check=True)
        else:
            print(f"준비 명령: python scripts/prepare_microsoft.py --format {INPUT_FORMAT}")
        print("GraphRAG CLI 설치 여부:", bool(GRAPHRAG_CLI))
        if WORKSPACE.exists():
            print("현재 입력 파일:", [p.name for p in sorted((WORKSPACE / "input").iterdir()) if p.is_file()])
        """),
        md("""
        ## 2. 문서로부터 인덱스 만들기

        아래 셀의 `RUN_PAID_INDEX=True`는 준비된 `runs/microsoft/input/`을 [GraphRAG의 standard 인덱싱](https://microsoft.github.io/graphrag/index/default_dataflow/)으로 처리합니다. 셀은 먼저 CLI·작업공간·프로젝트 루트 `.env`의 `OPENAI_API_KEY`를 확인합니다. `--dry-run --skip-validation`은 설정을 살펴보는 단계이며 모델 연결 검증을 건너뜁니다. 이어지는 **두 번째 `index` 명령**이 실제 API를 호출합니다.

        실제 실행에서는 입력 문서를 텍스트 조각인 `TextUnit`으로 나누고, LLM이 엔터티와 관계를 추출·요약합니다. 관계 그래프에서 커뮤니티를 찾고 보고서를 만든 뒤 검색에 쓸 임베딩도 생성합니다. 그 결과가 `runs/microsoft/output/`의 Parquet 표와 설정된 벡터 저장소에 남습니다. **Neo4j에 저장하는 과정은 아닙니다.** 원문이 짧아도 모델 호출 비용과 실행 시간이 듭니다.

        `RUN_PAID_INDEX=False`이면 이 셀은 건너뛰지만, 이전에 만들어 둔 산출물이 있다면 뒤의 확인 셀은 읽을 수 있습니다. 새 작업공간에서 아직 인덱싱하지 않았다면 뒤의 표와 그림은 나타나지 않습니다.
        """),
        code("""
        RUN_PAID_INDEX = False
        if RUN_PAID_INDEX:
            if not WORKSPACE.exists():
                raise FileNotFoundError("먼저 작업공간을 준비하세요.")
            if not GRAPHRAG_CLI:
                raise FileNotFoundError("GraphRAG CLI가 없습니다. requirements-microsoft.txt를 설치하세요.")
            if not os.getenv("OPENAI_API_KEY", "").strip():
                raise RuntimeError("프로젝트 루트 .env에 OPENAI_API_KEY가 없습니다.")
            subprocess.run([GRAPHRAG_CLI, "index", "--root", str(WORKSPACE), "--method", "standard", "--dry-run", "--skip-validation"], check=True)
            subprocess.run([GRAPHRAG_CLI, "index", "--root", str(WORKSPACE), "--method", "standard"], check=True)
        else:
            print("실제 인덱싱은 건너뛰었습니다. 설정을 확인한 뒤 RUN_PAID_INDEX=True로 바꾸세요.")
        """),
        md("""
        ## 3. 인덱싱 결과와 원문 출처 확인하기

        **첫 번째 코드 셀**은 `runs/microsoft/output/relationships.parquet`가 있는지 확인합니다. 있으면 `load_tables(output)`이 실제 Parquet 파일을 읽고, `show(tables)`가 각 표의 행 수·열 이름과 앞부분을 표시합니다. 이 셀은 새 그래프를 만들거나 API를 호출하지 않습니다.

        | 산출물 | 무엇이 들어 있나 |
        | --- | --- |
        | `documents` | 입력 문서와 연결된 TextUnit ID |
        | `text_units` | 문서에서 나눈 텍스트 조각과 원문 문서 ID |
        | `entities`, `relationships` | 자동 추출된 대상과 대상 사이의 설명·근거 TextUnit ID |
        | `communities`, `community_reports` | 관계 그래프의 묶음과 생성된 묶음별 요약 |

        **바로 다음 코드 셀**은 관계 표의 **첫 행 한 개**를 예로 들어 `관계 → text_unit_ids → TextUnit → document_id → 원문 문서`를 따라갑니다. 첫 행은 설명용 표본이지 정답 관계로 고른 것이 아닙니다. 화면의 `description`은 모델이 생성한 설명이므로 실제 문장과 대조해야 합니다. [공식 출력 스키마](https://microsoft.github.io/graphrag/index/outputs/)
        """),
        code("""
        output = WORKSPACE / "output"
        if (output / "relationships.parquet").exists():
            tables = load_tables(output)
            show(tables)
        else:
            tables = {}
            print("아직 실제 산출물이 없습니다:", output)
            print("이 셀의 표는 인덱싱 후에만 나타납니다. 가상 표를 실제 결과처럼 표시하지 않습니다.")
        """),
        code("""
        if {"relationships", "text_units"} <= tables.keys() and not tables["relationships"].empty:
            relation = tables["relationships"].iloc[0]
            units = tables["text_units"].set_index("id")
            documents_by_id = tables["documents"].set_index("id") if "documents" in tables else None
            print("추출 관계:", relation.get("source"), "→", relation.get("target"))
            print("설명:", relation.get("description"))
            for unit_id in list(dict.fromkeys(relation.get("text_unit_ids", [])))[:3]:
                if unit_id in units.index:
                    row = units.loc[unit_id]
                    doc_id = row.get("document_id")
                    title = documents_by_id.loc[doc_id].get("title") if documents_by_id is not None and doc_id in documents_by_id.index else "(제목 미확인)"
                    print("TextUnit:", unit_id, "| 문서:", title, "| 문서 ID:", doc_id)
                    print(str(row.get("text", ""))[:700])
        else:
            print("관계→TextUnit→원문 확인은 인덱싱 후 실행됩니다.")
        """),
        md("""
        ## 4. 추출된 관계 일부를 그림으로 보기

        아래 코드는 **실제 `relationships` 표의 앞 18개 행**에서 `source`와 `target`을 읽어 작은 NetworkX 그림을 만듭니다. 그림을 그리기 위한 별도의 Python 작업이며, Microsoft GraphRAG가 Neo4j에 그래프를 넣었다는 뜻은 아닙니다.

        이 그림은 연결을 한눈에 보는 용도입니다. 코드가 **무방향 그래프**로 그리므로 원래 관계의 방향과 설명은 보존되지 않습니다. 두 점 사이에 선이 보여도 직접 협업이나 원문에서 확인된 관계라고 단정하지 마세요. 관계 표의 `description`과 `text_unit_ids`를 원문과 대조해야 합니다. 2번 노트북에서 사람이 지정한 `LEADS`·`PART_OF`·`REVIEWS` 타입이 이 결과에 그대로 붙는 것도 아닙니다.
        """),
        code("""
        if "relationships" in tables and not tables["relationships"].empty:
            import networkx as nx
            import matplotlib.pyplot as plt
            import textwrap
            from session_demo.plot_fonts import apply_korean_font

            frame = tables["relationships"].head(18)
            graph = nx.from_pandas_edgelist(frame, source="source", target="target")
            fig, ax = plt.subplots(figsize=(15, 8))
            pos = nx.spring_layout(graph, seed=7, k=1.6, iterations=200)
            nx.draw_networkx_nodes(graph, pos, ax=ax, node_color="#dbead9", node_size=850, edgecolors="#89a688")
            nx.draw_networkx_edges(graph, pos, ax=ax, edge_color="#789079", width=1.3, alpha=0.7)
            labels = {node: textwrap.fill(str(node), width=15, break_long_words=False) for node in graph}
            nx.draw_networkx_labels(graph, pos, labels=labels, ax=ax, font_size=8,
                                    bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.82, "pad": 0.15})
            apply_korean_font(ax)
            ax.margins(0.13)
            ax.axis("off")
            fig.tight_layout()
            display(fig)
            plt.close(fig)
        else:
            print("시각화할 실제 관계가 아직 없습니다.")
        """),
        md("""
        ## 5. 자동 추출된 연결을 원문으로 되짚기

        아래 코드는 `inspect_microsoft.py`의 `trace_entity_path`를 호출합니다. 이 함수는 **이미 생성된 관계 표를 따로 읽어** 오헤슬과 보안팀 사이의 짧은 연결을 찾고, 각 관계의 `text_unit_ids`와 `document_id`로 원문을 되짚습니다. Microsoft GraphRAG의 Local Search 답변 함수가 아니라 **산출물 점검용 코드**입니다.

        이 점검에서는 관계를 무방향으로 이어 보므로 경로가 나타났다는 사실만으로 관계의 방향이나 뜻이 입증되지 않습니다. 원래 D1–D3에서는 오헤슬이 프로젝트를 총괄하고, 프로젝트가 프로그램에 속하며, 보안팀이 **프로그램**의 보안 검토를 맡습니다. 자동 추출 결과가 이 경로와 다르거나 경로가 없을 수도 있습니다. 각 행의 추출 설명을 옆에 나온 원문과 비교하고, **직접 협업했다는 기록은 원문에 없다는 점**을 확인합니다.
        """),
        code("""
        from inspect_microsoft import trace_entity_path

        if {"relationships", "text_units", "documents"} <= tables.keys():
            try:
                display(trace_entity_path(tables, "오헤슬", "보안팀"))
            except ValueError as exc:
                print("경로를 확인하지 못했습니다:", exc)
        else:
            print("인덱싱 산출물을 먼저 준비하세요.")
        """),
        md("""
        ## 6. 인덱스를 사용해 Local·Global 질문하기

        앞의 표·그림은 **인덱스를 읽어 검사**한 결과입니다. 아래 셀은 `graphrag query` CLI로 그 인덱스에 실제 질문을 보내 **새 답변을 생성**하는 단계입니다. [공식 질의 설명](https://microsoft.github.io/graphrag/query/overview/)에 따르면 Local Search는 질문과 관련된 엔터티·관계·원문 조각을 중심으로, Global Search는 커뮤니티 보고서를 종합해 답합니다.

        `RUN_PAID_QUERIES=True`이면 로컬 관계 질문과 전체 주제 질문을 차례로 실행해 답변을 노트북에 표시하고 `runs/microsoft/query_local_answer.md`, `query_global_answer.md`에도 저장합니다. API 호출 비용이 발생합니다. `False`이면 **새 질의를 보내지 않고**, 해당 파일이 있을 때만 이전 답변을 읽습니다. 새로 내려받은 저장소에는 `runs/`가 없어 이전 답변도 없습니다.

        질의 결과의 인용 표시와 문장을 원문에 다시 대조합니다. 여섯 문서만으로 Global Search의 일반적인 성능을 평가할 수는 없습니다.
        """),
        code("""
        RUN_PAID_QUERIES = False
        if RUN_PAID_QUERIES:
            if not (output / "relationships.parquet").exists():
                raise FileNotFoundError("인덱싱 산출물이 먼저 필요합니다.")
            if not GRAPHRAG_CLI:
                raise FileNotFoundError("GraphRAG CLI가 없습니다. requirements-microsoft.txt를 설치하세요.")
            for method, question in [
                ("local", "오헤슬과 보안팀은 어떤 관계인가? 각 관계의 출처를 밝혀줘."),
                ("global", "이 자료 전체에서 출시와 보안 검토의 주요 주제는 무엇인가?"),
            ]:
                print("\\n질의 방식:", method, "| 질문:", question)
                result = subprocess.run(
                    [GRAPHRAG_CLI, "query", question, "--root", str(WORKSPACE), "--method", method],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                )
                if result.returncode:
                    print((result.stderr or result.stdout)[-2500:])
                    raise RuntimeError(f"{method} 질의 실패. 상세 로그: {WORKSPACE / 'logs' / 'query.log'}")
                answer = result.stdout.strip()
                if not answer:
                    raise RuntimeError(f"{method} 질의 응답이 비었습니다. 상세 로그: {WORKSPACE / 'logs' / 'query.log'}")
                display(Markdown(f"### {method.upper()} 답변\\n\\n{answer}"))
                answer_file = WORKSPACE / f"query_{method}_answer.md"
                answer_file.write_text(answer, encoding="utf-8")
                print("답변 저장:", answer_file)
        else:
            print("새 API 질의를 건너뛰고 저장된 답변을 보여줍니다.")
            for method in ("local", "global"):
                answer_file = WORKSPACE / f"query_{method}_answer.md"
                if answer_file.exists():
                    display(Markdown(f"### {method.upper()} 저장 답변\\n\\n{answer_file.read_text(encoding='utf-8')}"))
                    print("읽은 파일:", answer_file)
                else:
                    print(f"{method} 저장 답변이 없습니다. RUN_PAID_QUERIES=True로 한 번 질의하세요.")
        """),
        md("""
        ### 저장된 답변을 읽을 때 확인할 것

        앞 셀에서 `RUN_PAID_QUERIES=False`로 두면 저장된 답변이 있을 때만 이를 다시 보여줍니다. `True`이면 새로 생성한 답변을 표시하고 파일에도 저장합니다.

        답변의 `[Data: ...]` 표시는 참조한 인덱스 자료의 위치를 가리킬 뿐 **문장 전체가 사실이라는 보증은 아닙니다.** D1–D3에는 직접 협업 기록이 없고, D5는 위험 등록부의 **문서 ID**이지 프로젝트 이름이 아닙니다. D6의 일정 변경 이유는 인증 절차 수정 확인이 더 필요하다는 것입니다. 생성 답변이 이를 다르게 말하면 원문과 근거 표를 다시 확인합니다.
        """),
        md("""
        **다음:** `04_llm_wiki.ipynb`에서는 검색 인덱스 대신 사람이 읽을 수 있는 Markdown 지식 페이지가 D6 이후 어떻게 갱신되는지 보여줍니다. 두 방식은 서로 결합할 수도 있습니다.
        """),
    ]


def notebook_04() -> list[dict]:
    return [
        md("""
        # 04. LLM Wiki: 새 자료 D6가 기존 지식을 바꾸는 과정

이 예시는 [Karpathy의 LLM Wiki 원문](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)의 세 층 **raw / wiki / schema(AGENTS.md)**, 세 작업 **ingest / query / lint**를 결제 프로젝트에 적용합니다. `wiki_vault/`는 D1–D5가 반영된 초기 상태입니다. `index.md`는 주제별 지도, `log.md`는 시간순 기록입니다.

기본 실행은 미리 작성한 D6 계획(`fixture`)을 사용해 API 없이 전후 diff를 재현합니다. 아래 선택 셀에서 `llm` 모드로 바꾸면 실제 에이전트가 새 계획을 제안합니다. 둘을 혼동해 설명하지 않습니다.

`wiki_vault/`는 D1–D5 초기 템플릿입니다. 실행하며 바뀌는 파일은 `runs/wiki_notebook_.../vault/`에 저장됩니다. 같은 커널에서 첫 셀을 다시 실행해도 기존 작업 위키를 재사용합니다. 커널을 새로 시작하면 새 복사본이 만들어집니다.
        """),
        code("""
        from pathlib import Path
        from datetime import datetime
        import shutil, sys
        from IPython.display import display, Markdown

        ROOT = Path.cwd().resolve()
        if ROOT.name == "notebooks":
            ROOT = ROOT.parent
        sys.path.insert(0, str(ROOT))
        from session_demo.wiki_cli import plan_ingest, preview, apply_plan, answer_extractively, lint, WIKILINK

        # 같은 커널에서 첫 셀을 다시 눌러도 이미 작업하던 위키를 유지합니다.
        previous_vault = globals().get("VAULT")
        if (
            isinstance(previous_vault, Path)
            and previous_vault.name == "vault"
            and previous_vault.is_dir()
            and previous_vault.parent.parent == ROOT / "runs"
            and previous_vault.parent.name.startswith("wiki_notebook_")
        ):
            VAULT = previous_vault
            RUN = VAULT.parent
            print("기존 실행의 위키 재사용:", VAULT)
        else:
            RUN = ROOT / "runs" / f"wiki_notebook_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
            VAULT = RUN / "vault"
            RUN.mkdir(parents=True)
            shutil.copytree(ROOT / "wiki_vault", VAULT)
            print("새 실행의 위키:", VAULT)
        """),
        md("""
        ## 1. 세 층과 초기 상태

`raw/`는 수정하지 않는 원문, `wiki/`는 새 자료에 맞춰 계속 고치는 지식 페이지, `AGENTS.md`는 두 층을 다루는 규칙입니다. 아래에서 **규칙 파일 전체**를 읽고 ingest·query·lint가 각각 무엇을 해야 하는지 확인합니다. Karpathy의 글은 패턴 제안이며, 이 파일의 문서 ID·검토 절차는 시연 자료에 맞춘 구체화입니다. `Obsidian → Open folder as vault`에서 위 출력 경로를 열면 파일과 링크를 화면으로 볼 수 있습니다.
        """),
        code("""
        print("[구조]")
        for path in sorted(VAULT.rglob("*.md")):
            print("-", path.relative_to(VAULT))
        print("\\n[AGENTS.md: 실제 LLM 작업에 제공되는 운영 규칙 전체]")
        display(Markdown((VAULT / "AGENTS.md").read_text(encoding="utf-8")))
        print("\\n[D6 이전 출시 일정]\\n", (VAULT / "wiki" / "출시 일정.md").read_text(encoding="utf-8"))
        """),
        md("""
        ## 2. Ingest: D6를 넣기 전에 변경 계획과 diff 보기

새 결정 D6는 출시 목표일을 11월 3일에서 11월 10일로 바꿉니다. 처음에는 작성해 둔 **시연용 계획**을 로드합니다. 계획은 원자료와 기존 위키의 해시를 기록해, 검토 후 파일이 바뀌었다면 적용을 거부합니다. 원문은 diff를 확인한 뒤 `raw/`에 보존됩니다.
        """),
        code("""
        source = ROOT / "data" / "project" / "D6_decision.md"
        plan_path = RUN / "D6_plan.json"
        d6_raw = VAULT / "raw" / "D6_decision.md"
        if d6_raw.is_file():
            print("이 작업 위키에는 D6가 이미 적용되어 있습니다:", VAULT)
        else:
            plan = plan_ingest(VAULT, source, mode="fixture", plan_path=plan_path)
            print(preview(VAULT, plan))
        """),
        code("""
        plan_path = RUN / "D6_plan.json"
        d6_raw = VAULT / "raw" / "D6_decision.md"
        if d6_raw.is_file():
            print("D6 적용을 건너뛰었습니다. 이미 이 작업 위키에 있습니다:", VAULT)
        else:
            if not plan_path.is_file():
                raise RuntimeError("현재 위키의 D6 계획이 없습니다. 바로 위 계획·diff 셀을 먼저 실행하세요.")
            changed = apply_plan(VAULT, plan_path)
            print("적용 파일:", changed)
        print("\\n[D6 이후 출시 일정]\\n", (VAULT / "wiki" / "출시 일정.md").read_text(encoding="utf-8"))
        print("\\n[D6 이후 프로그램 개요]\\n", (VAULT / "wiki" / "결제 안정화 프로그램.md").read_text(encoding="utf-8"))
        print("\\n[D6 이후 보안 검토]\\n", (VAULT / "wiki" / "보안 검토.md").read_text(encoding="utf-8"))
        """),
        md("""
        ## 3. Query: 바뀐 현재 사실과 원문 근거 찾기

아래 오프라인 답은 규칙 기반 추출이며 LLM 합성 답이 아닙니다. 관련 위키 페이지를 검색하고, `출시 일정.md`의 현재 날짜와 변경 이유를 표시합니다. 앞의 Ingest 적용 셀을 건너뛴 경우 이 셀은 **준비된 시연용 D6 계획만 자동으로 적용**하고 그 사실을 출력합니다. 실제 LLM 계획은 자동 적용하지 않습니다. LLM 질의는 뒤의 선택 셀에서 할 수 있습니다.
        """),
        code("""
        question = "현재 출시 목표일은 언제이며 왜 바뀌었나?"
        d6_raw = VAULT / "raw" / "D6_decision.md"
        if not d6_raw.is_file():
            # 교육용 고정 fixture만 자동 적용합니다. 실제 LLM 계획은 여기서 적용하지 않습니다.
            fixture_source = ROOT / "data" / "project" / "D6_decision.md"
            fixture_plan_path = RUN / "D6_query_fixture_plan.json"
            fixture_plan = plan_ingest(VAULT, fixture_source, mode="fixture", plan_path=fixture_plan_path)
            changed = apply_plan(VAULT, fixture_plan_path)
            print("[시연용 D6 자료 자동 준비] Ingest 적용 셀이 생략되어 고정 예시 계획을 적용했습니다.")
            print("적용 파일:", changed)
        print("현재 작업 위키:", VAULT)
        print(answer_extractively(VAULT, question))
        print("\\n[D6 원문]\\n", d6_raw.read_text(encoding="utf-8"))
        """),
        md("""
        ## 4. Lint: 깨진 링크·출처·낡은 현재 사실 찾기

첫 번째는 갱신된 실제 위키를 점검합니다. 두 번째는 별도 복사본에 낡은 날짜를 일부러 넣어 **lint가 어떤 문제를 찾는지** 보여줍니다. 원래 위키는 수정하지 않습니다.
        """),
        code("""
        print("[정상 위키 점검]", lint(VAULT) or "발견 항목 없음")
        broken = RUN / f"broken_copy_{datetime.now().strftime('%H%M%S_%f')}"
        shutil.copytree(VAULT, broken)
        schedule = broken / "wiki" / "출시 일정.md"
        schedule.write_text(
            schedule.read_text(encoding="utf-8").replace("현재 출시 목표일: 2025-11-10", "현재 출시 목표일: 2025-11-03"),
            encoding="utf-8",
        )
        print("\\n[의도적으로 낡은 날짜를 넣은 복사본]")
        for issue in lint(broken):
            print("-", issue)
        """),
        md("""
        ## 5. 위키 링크 그래프 보기

이 선은 `[[페이지 링크]]`가 있는 두 페이지를 한 번만 연결한 것입니다. 화면에서는 링크 방향을 생략합니다. Neo4j의 `LEADS`, `PART_OF`, `REVIEWS`처럼 타입과 방향이 확인된 사실 관계는 아닙니다. Obsidian 그래프 뷰에서도 같은 차이를 짚습니다.
        """),
        code("""
        import networkx as nx
        import matplotlib.pyplot as plt
        import textwrap
        from session_demo.plot_fonts import apply_korean_font

        # 위키 페이지 사이에 링크가 있으면 한 선으로 표시합니다. 방향은 여기서 생략합니다.
        link_graph = nx.Graph()
        for page in (VAULT / "wiki").glob("*.md"):
            link_graph.add_node(page.stem)
            for target in WIKILINK.findall(page.read_text(encoding="utf-8")):
                link_graph.add_edge(page.stem, target)
        fig, ax = plt.subplots(figsize=(10, 6))
        pos = nx.spring_layout(link_graph, seed=5, k=1.2)
        nx.draw_networkx_nodes(link_graph, pos, ax=ax, node_color="#f9e0bf", node_size=4200, edgecolors="#c99458")
        nx.draw_networkx_edges(link_graph, pos, ax=ax, edge_color="#b3916c", width=1.7)
        labels = {name: textwrap.fill(name, width=8, break_long_words=False) for name in link_graph}
        nx.draw_networkx_labels(link_graph, pos, labels=labels, ax=ax, font_size=10)
        apply_korean_font(ax)
        ax.margins(0.24)
        ax.axis("off")
        fig.tight_layout()
        display(fig)
        plt.close(fig)
        """),
        md("""
        ## 6. 실제 LLM 에이전트로 계획·질의·의미 lint 실행 (선택)

LLM 의미 lint는 **검토할 제안**입니다. 같은 사실의 반복은 모순이 아니며, 링크가 들어오는 페이지를 고립 페이지라고 부르면 그래프·기계적 lint와 다시 대조합니다.

키가 준비됐다면 새 복사본에서 `llm` 계획을 만들고 diff를 확인합니다. 이 셀은 **계획만 생성하고 적용하지 않습니다.** `apply_plan`에 같은 plan 파일을 넣어야 합니다. 질의·의미 lint도 각각 유료 호출입니다. 모델 계획이 출처 검증에 실패하면 후보 JSON을 저장하고 최대 두 번 다시 제안받습니다(추가 API 호출). 재제안이 일부 파일만 고치면 앞선 계획과 합쳐 전체를 다시 검증합니다. 끝까지 검증을 통과하지 못하면 적용하지 않으며, 질의·lint는 별도로 진행합니다.
        """),
        code("""
        RUN_LLM_INGEST = False
        RUN_LLM_QUERY = False
        RUN_LLM_LINT = False

        if RUN_LLM_INGEST:
            print("\\n[LLM ingest 변경 계획]")
            live_vault = RUN / f"live_agent_vault_{datetime.now().strftime('%H%M%S_%f')}"
            shutil.copytree(ROOT / "wiki_vault", live_vault)
            live_plan_path = RUN / "D6_live_plan.json"
            try:
                live_plan = plan_ingest(live_vault, source, mode="llm", plan_path=live_plan_path)
            except ValueError as exc:
                print("제안이 검증에서 거부됐습니다:", exc)
                print("적용하지 않았습니다. 저장된 candidate JSON과 원문을 대조하세요.")
            else:
                print(preview(live_vault, live_plan))
                print("계획 저장:", live_plan_path)
                print("검토 후 적용 예: apply_plan(live_vault, live_plan_path)")
        if RUN_LLM_QUERY:
            from session_demo.wiki_cli import answer_with_llm
            print("\\n[LLM query: D6 반영 위키]")
            print(answer_with_llm(VAULT, question))
        if RUN_LLM_LINT:
            from session_demo.wiki_cli import qualitative_lint
            print("\\n[LLM 의미 lint: D6 반영 위키]")
            print(qualitative_lint(VAULT))
            print("기계적 lint 대조:", lint(VAULT) or "발견 항목 없음")
        if not any((RUN_LLM_INGEST, RUN_LLM_QUERY, RUN_LLM_LINT)):
            print("LLM 호출을 건너뛰었습니다. 위의 fixture 전후 diff·검색·기계적 lint는 실행되었습니다.")
        """),
        md("""
        **세션 마무리:** GraphRAG에서는 질문 시 관계와 원문 근거를 회수했습니다. LLM Wiki에서는 D6가 들어오자 이미 존재하던 일정·프로그램·보안 페이지를 함께 고쳤습니다. 두 방식 모두 출처와 사람의 검토가 중요합니다.
        """),
    ]


def main() -> None:
    for filename, cells in [
        ("01_vector_rag.ipynb", notebook_01()),
        ("02_graph_neo4j.ipynb", notebook_02()),
        ("03_microsoft_graphrag.ipynb", notebook_03()),
        ("04_llm_wiki.ipynb", notebook_04()),
    ]:
        write(filename, cells)
        print(OUT / filename)


if __name__ == "__main__":
    main()
