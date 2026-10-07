"""오프라인 실행 경로를 한 번에 점검한다. 외부 API/Neo4j에는 접속하지 않는다."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from session_demo.data import project_documents, relation_coverage
from session_demo.graph import facts, local_graph, relation_path, validate_facts
from session_demo.vector import ChromaTfidfIndex
from session_demo.wiki_cli import answer_extractively, apply_plan, lint, plan_ingest


def main() -> None:
    docs = project_documents(("D1", "D2", "D3"))
    index = ChromaTfidfIndex(docs)
    q = "오헤슬과 보안팀은 어떤 관계인가?"
    top2 = index.search(q, 2)
    top3 = index.search(q, 3)
    assert not relation_coverage([h.id for h in top2])["complete"]
    assert relation_coverage([h.id for h in top3])["complete"]

    model = facts()
    validate_facts(model)
    path = relation_path(local_graph(model))
    assert [edge["source_id"] for edge in path] == ["D1", "D2", "D3"]

    scratch = ROOT / "runs"
    scratch.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=scratch) as tmp:
        work = Path(tmp)
        vault = work / "vault"
        shutil.copytree(ROOT / "wiki_vault", vault)
        assert not lint(vault), lint(vault)
        plan_path = work / "plan.json"
        plan_ingest(vault, ROOT / "data" / "project" / "D6_decision.md", "fixture", plan_path)
        changed = apply_plan(vault, plan_path)
        assert "wiki/출시 일정.md" in changed
        assert not lint(vault), lint(vault)
        assert "2025-11-10" in answer_extractively(vault, "현재 출시 목표일은 언제이며 왜 바뀌었나?")

    for path in sorted((ROOT / "notebooks").glob("*.ipynb")):
        notebook = json.loads(path.read_text(encoding="utf-8"))
        assert notebook["nbformat"] == 4
        for number, cell in enumerate(notebook["cells"], start=1):
            if cell["cell_type"] == "code":
                source = "".join(cell["source"]) if isinstance(cell["source"], list) else cell["source"]
                compile(source, f"{path.name}:cell{number}", "exec")
    print("오프라인 사전 점검 완료: Chroma 근거 범위, 그래프 출처, 위키 D6 전후, 노트북 코드 문법")


if __name__ == "__main__":
    main()
