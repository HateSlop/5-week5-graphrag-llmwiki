"""수업용 LLM Wiki CLI: prepare, ingest, apply, query, lint.

Karpathy의 작업 이름을 이 예시에 맞춰 구현했다. 원문의 표준 CLI가 아니다.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import shutil
from datetime import date
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer

from . import DATA, ROOT
from .llm import client_and_model

SOURCE_ID = re.compile(r"^(D\d+)_.*\.md$")
WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
CITATION = re.compile(r"(?<!\[)\[([^\[\]]+)\](?!\])")
CURRENT_DATE = re.compile(r"현재 출시 목표일:\s*(\d{4}-\d{2}-\d{2})")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def vault_files(vault: Path) -> list[Path]:
    required = [vault / "AGENTS.md", vault / "index.md", vault / "log.md", vault / "raw", vault / "wiki"]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"위키 구조가 없습니다: {missing}")
    return sorted((vault / "wiki").glob("*.md"))


def source_id(path: Path) -> str:
    match = SOURCE_ID.fullmatch(path.name)
    if not match:
        raise ValueError("원자료 파일명은 D6_decision.md처럼 D번호_설명.md 형식이어야 합니다.")
    return match.group(1)


def update_target(vault: Path, relative: str) -> Path:
    """에이전트 계획이 raw/나 상위 디렉터리를 수정하지 못하게 한다."""
    path = Path(relative)
    valid = path == Path("index.md") or (len(path.parts) == 2 and path.parts[0] == "wiki" and path.suffix == ".md")
    if path.is_absolute() or ".." in path.parts or not valid:
        raise ValueError(f"허용하지 않은 갱신 경로: {relative}")
    target = (vault / path).resolve()
    if not target.is_relative_to(vault.resolve()):
        raise ValueError(f"vault 밖의 경로: {relative}")
    return target


def known_ids(vault: Path, incoming: str | None = None) -> set[str]:
    ids = {source_id(path) for path in (vault / "raw").glob("D*_*.md")}
    if incoming:
        ids.add(incoming)
    return ids


def cited_ids(text: str) -> set[str]:
    return {match for bracket in CITATION.findall(text) for match in re.findall(r"D\d+", bracket)}


def prompt_snapshot(vault: Path, incoming: Path) -> str:
    parts = [f"[AGENTS.md]\n{read(vault / 'AGENTS.md')}", f"[새 원자료 {incoming.name}]\n{read(incoming)}"]
    for raw in sorted((vault / "raw").glob("*.md")):
        parts.append(f"[raw/{raw.name}]\n{read(raw)}")
    parts.append(f"[index.md]\n{read(vault / 'index.md')}")
    for page in vault_files(vault):
        parts.append(f"[wiki/{page.name}]\n{read(page)}")
    return "\n\n".join(parts)


def propose_with_llm(
    vault: Path, incoming: Path, sid: str,
    previous: dict | None = None, validation_error: str | None = None,
) -> dict:
    client, model = client_and_model()
    messages = [
        {
            "role": "system",
                "content": (
                    "너는 Markdown 위키 편집 계획을 만드는 에이전트다. AGENTS.md 규칙을 지켜라. "
                    "원자료를 고치지 말고 근거 없는 사실을 쓰지 마라. "
                    "JSON 객체만 반환하라. 필드: source_id(문자열), summary(문자열), "
                    "questions(문자열 배열), updates({path,content} 배열), log_entry(문자열). "
                    "updates의 path는 index.md 또는 wiki/*.md만 허용한다. content는 해당 파일의 완전한 새 내용이다. "
                    "D6에서는 출시 일정·결제 안정화 프로그램·보안 검토·index.md를 갱신하고, "
                    "11월 3일은 이전 목표일, 11월 10일은 현재 목표일로 정확히 구분하라. "
                    "출시 일정과 결제 안정화 프로그램 페이지에는 현재 2025-11-10과 이전 2025-11-03을 함께 남겨라. "
                    "보안 검토 페이지에는 D6에 나온 보안팀의 수정 사항 재검토 결정을 [D6]과 함께 적어라. "
                    "index.md의 보안 검토 항목에도 D6를 포함하라. "
                    "갱신하는 위키 페이지마다 새 결정의 사실 문장에 [D6]을 붙이고, 다른 사실 문장도 근거 ID를 유지하라. "
                    "log_entry는 기존 log.md 끝에 추가할 새 섹션만 써라."
                ),
            },
        {"role": "user", "content": f"새 자료 ID: {sid}\n\n{prompt_snapshot(vault, incoming)}"},
    ]
    if previous is not None and validation_error is not None:
        messages.append({
            "role": "user",
            "content": (
                f"직전 계획은 검증에서 거부되었습니다: {validation_error}\n"
                "원문에 근거한 부분만 고치세요. 오류가 난 파일만 updates로 반환해도 되며 "
                "나머지 파일의 기존 제안은 코드가 보존해 병합합니다. "
                "검증을 피하려고 근거 표기만 임의로 붙이지 마세요. "
                "보안 검토 페이지 오류라면 D6 원문에 있는 보안팀의 수정 사항 재검토 결정을 "
                "해당 페이지에 사실 문장으로 반영하고 [D6]을 붙이세요. "
                "기존 페이지를 그대로 반환하면 다시 거부됩니다.\n"
                f"직전 계획: {json.dumps(previous, ensure_ascii=False)}"
            ),
        })
    response = client.chat.completions.create(
        model=model, temperature=0, response_format={"type": "json_object"},
        messages=messages,
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("모델이 빈 계획을 반환했습니다.")
    return json.loads(content)


def validate_body(body: dict, vault: Path, sid: str) -> None:
    if body.get("source_id") != sid:
        raise ValueError("계획의 source_id가 입력 문서와 다릅니다.")
    updates = body.get("updates")
    if not isinstance(updates, list) or not updates:
        raise ValueError("updates 배열이 비어 있습니다.")
    names: set[str] = set()
    allowed_citations = known_ids(vault, sid)
    for item in updates:
        relative, content = item.get("path"), item.get("content")
        if not isinstance(relative, str) or not isinstance(content, str):
            raise ValueError("updates 항목에는 문자열 path와 content가 필요합니다.")
        update_target(vault, relative)
        if relative in names:
            raise ValueError(f"중복 갱신 파일: {relative}")
        names.add(relative)
        unknown = cited_ids(content) - allowed_citations
        if unknown:
            raise ValueError(f"존재하지 않는 원문 ID {sorted(unknown)}: {relative}")
        if relative.startswith("wiki/") and sid not in cited_ids(content):
            raise ValueError(f"새 자료 [{sid}] 출처가 없는 위키 갱신: {relative}")
    if "index.md" not in names:
        raise ValueError("index.md 갱신이 빠졌습니다.")
    if sid == "D6":
        required = {"wiki/출시 일정.md", "wiki/결제 안정화 프로그램.md", "wiki/보안 검토.md"}
        if not required <= names:
            raise ValueError(f"D6의 영향 페이지가 빠졌습니다: {sorted(required - names)}")
        schedule = next(item["content"] for item in updates if item["path"] == "wiki/출시 일정.md")
        current = re.search(r"현재\s*출시\s*목표일:\s*2025-11-10", schedule)
        previous = re.search(r"이전(?:\s*출시)?\s*목표일:\s*2025-11-03", schedule)
        if not (current and previous):
            raise ValueError("D6의 출시 일정 페이지에 현재·이전 목표일이 올바르게 구분되지 않았습니다.")
        program = next(item["content"] for item in updates if item["path"] == "wiki/결제 안정화 프로그램.md")
        if not (re.search(r"현재\s*출시\s*목표일:\s*2025-11-10", program)
                and re.search(r"이전(?:\s*출시)?\s*목표일(?:은)?:?\s*2025-11-03", program)):
            raise ValueError("D6의 결제 안정화 프로그램 페이지에 현재·이전 목표일을 모두 남겨야 합니다.")
        security = next(item["content"] for item in updates if item["path"] == "wiki/보안 검토.md")
        if not any("보안팀" in line and "재검토" in line and sid in cited_ids(line)
                   for line in security.splitlines()):
            raise ValueError("D6의 보안 검토 페이지에 보안팀의 수정 사항 재검토와 [D6] 근거가 필요합니다.")
        index = next(item["content"] for item in updates if item["path"] == "index.md")
        if not any("[[보안 검토]]" in line and "D6" in line for line in index.splitlines()):
            raise ValueError("index.md의 보안 검토 항목에 D6를 표시해야 합니다.")
    if not isinstance(body.get("log_entry"), str) or f"{sid}" not in body["log_entry"]:
        raise ValueError("새 원문을 언급하는 log_entry가 필요합니다.")


def plan_ingest(vault: Path, incoming: Path, mode: str, plan_path: Path) -> dict:
    vault_files(vault)
    incoming = incoming.resolve()
    if not incoming.is_file():
        raise FileNotFoundError(incoming)
    sid = source_id(incoming)
    if sid in known_ids(vault):
        raise ValueError(f"{sid}는 이미 raw/에 있습니다. 다른 작업공간을 준비하세요.")
    if mode == "fixture":
        if sid != "D6":
            raise ValueError("준비된 예시 계획은 D6에만 사용할 수 있습니다.")
        body = json.loads(read(ROOT / "fixtures" / "wiki_plan_D6.json"))
    elif mode == "llm":
        previous = None
        validation_error = None
        for attempt in (1, 2, 3):
            body = propose_with_llm(vault, incoming, sid, previous, validation_error)
            candidate = plan_path.with_name(f"{plan_path.stem}.candidate_{attempt}.json")
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            if previous is not None:
                if body.get("source_id") != sid or not isinstance(body.get("updates"), list):
                    raise ValueError(f"재제안의 자료 ID 또는 updates가 잘못됐습니다: {candidate}")
                combined_updates = {item["path"]: item for item in previous["updates"]}
                for item in body["updates"]:
                    if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                        raise ValueError(f"재제안의 updates 항목이 잘못됐습니다: {candidate}")
                    combined_updates[item["path"]] = item
                body = {**previous, **{key: value for key, value in body.items() if key != "updates"},
                        "updates": list(combined_updates.values())}
                merged = plan_path.with_name(f"{plan_path.stem}.merged_{attempt}.json")
                merged.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            try:
                validate_body(body, vault, sid)
                break
            except ValueError as exc:
                if attempt == 3:
                    raise ValueError(f"LLM 계획이 검증을 통과하지 못했습니다: {exc}. 제안 파일: {candidate}") from exc
                previous, validation_error = body, str(exc)
    else:
        raise ValueError(mode)
    validate_body(body, vault, sid)
    base = {item["path"]: sha256(update_target(vault, item["path"]).read_bytes()) if update_target(vault, item["path"]).exists() else None for item in body["updates"]}
    body["source_path"] = str(incoming)
    body["source_sha256"] = sha256(incoming.read_bytes())
    body["base_sha256"] = base
    body["log_sha256"] = sha256((vault / "log.md").read_bytes())
    body["mode"] = mode
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return body


def preview(vault: Path, body: dict) -> str:
    blocks = [f"계획: {body['summary']}", f"새 원문: raw/{Path(body['source_path']).name}"]
    for item in body["updates"]:
        target = update_target(vault, item["path"])
        before = read(target).splitlines(keepends=True) if target.exists() else []
        after = item["content"].splitlines(keepends=True)
        blocks.append("".join(difflib.unified_diff(before, after, fromfile=f"before/{item['path']}", tofile=f"after/{item['path']}")))
    blocks.append("[log.md에 추가]\n" + body["log_entry"])
    if body.get("questions"):
        blocks.append("[확인 필요]\n" + "\n".join(f"- {q}" for q in body["questions"]))
    return "\n".join(blocks)


def apply_plan(vault: Path, plan_path: Path) -> list[str]:
    vault_files(vault)
    body = json.loads(read(plan_path))
    incoming = Path(body["source_path"]).resolve()
    sid = source_id(incoming)
    if not incoming.is_file() or sha256(incoming.read_bytes()) != body["source_sha256"]:
        raise ValueError("계획을 만든 뒤 원자료가 바뀌었습니다. 다시 계획을 만드세요.")
    if sid in known_ids(vault):
        raise ValueError(f"raw/에 이미 {sid}가 있습니다. 중복 ingest를 중단합니다.")
    validate_body(body, vault, sid)
    for relative, expected_hash in body["base_sha256"].items():
        target = update_target(vault, relative)
        current = sha256(target.read_bytes()) if target.exists() else None
        if current != expected_hash:
            raise ValueError(f"계획을 검토한 뒤 {relative}이(가) 바뀌었습니다. 계획을 다시 만드세요.")
    if sha256((vault / "log.md").read_bytes()) != body["log_sha256"]:
        raise ValueError("log.md가 계획 이후 바뀌었습니다.")
    raw_target = vault / "raw" / incoming.name
    if raw_target.exists():
        raise FileExistsError(raw_target)
    shutil.copy2(incoming, raw_target)
    changed = [f"raw/{incoming.name}"]
    for item in body["updates"]:
        target = update_target(vault, item["path"])
        target.write_text(item["content"], encoding="utf-8")
        changed.append(item["path"])
    with (vault / "log.md").open("a", encoding="utf-8") as handle:
        handle.write("\n" + body["log_entry"].rstrip() + "\n")
    changed.append("log.md")
    return changed


def retrieve_pages(vault: Path, question: str, k: int = 3) -> list[tuple[Path, float]]:
    pages = vault_files(vault)
    texts = [read(page) for page in pages]
    vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(2, 4))
    matrix = vectorizer.fit_transform(texts)
    scores = (matrix @ vectorizer.transform([question]).T).toarray().ravel()
    order = sorted(range(len(pages)), key=lambda i: (-scores[i], pages[i].name))[:k]
    return [(pages[i], float(scores[i])) for i in order]


def answer_extractively(vault: Path, question: str) -> str:
    """오프라인 리허설: 검색된 페이지와 D6 근거를 표시한다. LLM 답변이 아니다."""
    found = retrieve_pages(vault, question)
    lines = ["[검색된 위키 페이지]", *[f"- {page.name} (유사도 {score:.3f})" for page, score in found]]
    schedule = read(vault / "wiki" / "출시 일정.md")
    match_date = CURRENT_DATE.search(schedule)
    match_date_citation = re.search(r"현재 출시 목표일:\s*\d{4}-\d{2}-\d{2}[^\n]*\[(D\d+)\]", schedule)
    match_reason = re.search(r"변경 이유:\s*(.+?)\s*\[(D\d+)\]", schedule)
    if match_date and ("출시" in question or "목표일" in question):
        citation = f" [{match_date_citation.group(1)}]" if match_date_citation else " (출처 확인 필요)"
        lines.append(f"[위키에서 추출한 답] 현재 출시 목표일은 {match_date.group(1)}입니다.{citation}")
        if match_reason:
            lines.append(f"변경 이유: {match_reason.group(1)} [{match_reason.group(2)}]")
        lines.append("이 답은 규칙 기반 추출입니다. LLM 합성 답은 --mode llm로 별도로 실행합니다.")
    else:
        lines.append("자동 추출 답을 정의하지 않은 질문입니다. 위 페이지를 읽거나 --mode llm을 사용하세요.")
    return "\n".join(lines)


def answer_with_llm(vault: Path, question: str) -> str:
    client, model = client_and_model()
    found = retrieve_pages(vault, question)
    pages = "\n\n".join(f"[wiki/{path.name}]\n{read(path)}" for path, _ in found)
    ids = {id_ for path, _ in found for id_ in cited_ids(read(path))}
    raw = "\n\n".join(f"[raw/{path.name}]\n{read(path)}" for path in (vault / "raw").glob("*.md") if source_id(path) in ids)
    response = client.chat.completions.create(
        model=model, temperature=0,
        messages=[
            {"role": "system", "content": read(vault / "AGENTS.md") + "\n답변에 사용한 원문 ID를 표시하고 확인되지 않은 사실은 추측하지 마라."},
            {"role": "user", "content": f"[index.md]\n{read(vault / 'index.md')}\n\n{pages}\n\n{raw}\n\n질문: {question}"},
        ],
    )
    return response.choices[0].message.content or "(빈 응답)"


def lint(vault: Path) -> list[str]:
    pages = vault_files(vault)
    page_names = {page.stem for page in pages}
    raw_ids = known_ids(vault)
    findings: list[str] = []
    inbound = {name: 0 for name in page_names}
    for path in [vault / "index.md", *pages]:
        text = read(path)
        for name in WIKILINK.findall(text):
            if name not in page_names:
                findings.append(f"{path.relative_to(vault)}: 없는 페이지 링크 [[{name}]]")
            else:
                inbound[name] += 1
        if path.parent == vault / "wiki":
            for line_no, line in enumerate(text.splitlines(), start=1):
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or stripped.startswith("관련 페이지:"):
                    continue
                if not cited_ids(stripped):
                    findings.append(f"{path.relative_to(vault)}:{line_no}: 사실 문장에 출처 ID가 없습니다")
                unknown = cited_ids(stripped) - raw_ids
                if unknown:
                    findings.append(f"{path.relative_to(vault)}:{line_no}: 없는 원문 ID {sorted(unknown)}")
    for name, count in inbound.items():
        if count == 0:
            findings.append(f"wiki/{name}.md: 들어오는 링크가 없는 고립 페이지")
    current: dict[str, str] = {}
    for page in pages:
        match = CURRENT_DATE.search(read(page))
        if match:
            current[page.name] = match.group(1)
    if len(set(current.values())) > 1:
        findings.append(f"현재 출시 목표일이 페이지마다 다릅니다: {current}")
    if "D6" in raw_ids and any(value == "2025-11-03" for value in current.values()):
        findings.append("D6가 들어왔는데 2025-11-03이 현재 목표일로 남아 있습니다")
    for raw in sorted((vault / "raw").glob("D*_*.md")):
        original = DATA / "project" / raw.name
        if original.exists() and raw.read_bytes() != original.read_bytes():
            findings.append(f"raw/{raw.name}: 원자료가 원본 fixture와 달라졌습니다")
    return sorted(set(findings))


def qualitative_lint(vault: Path) -> str:
    client, model = client_and_model()
    pages = "\n\n".join(f"[{path.relative_to(vault)}]\n{read(path)}" for path in vault_files(vault))
    raws = "\n\n".join(f"[{path.relative_to(vault)}]\n{read(path)}" for path in sorted((vault / "raw").glob("*.md")))
    link_map = {path.name: WIKILINK.findall(read(path)) for path in vault_files(vault)}
    mechanical = lint(vault)
    response = client.chat.completions.create(
        model=model, temperature=0,
        messages=[
            {"role": "system", "content": read(vault / "AGENTS.md") + "\n수정하지 말고 모순·낡은 주장·출처 공백·조사 공백을 파일과 근거 ID를 붙여 보고하라. "
             "같은 날짜를 두 페이지에 적은 것은 모순이 아니다. 고립 페이지는 들어오는 위키 링크가 전혀 없을 때만 지적한다. "
             "이미 불확실하다고 쓴 문장을 미확인 표시가 없다고 지적하지 마라. 확실한 문제와 확인이 필요한 제안을 구분하라."},
            {"role": "user", "content": f"[기계적 lint 결과]\n{mechanical}\n\n[페이지 링크 지도]\n{link_map}\n\n[index.md]\n{read(vault / 'index.md')}\n\n{pages}\n\n{raws}"},
        ],
    )
    return response.choices[0].message.content or "(빈 응답)"


def record(vault: Path, operation: str, detail: str) -> None:
    with (vault / "log.md").open("a", encoding="utf-8") as handle:
        handle.write(f"\n## [{date.today().isoformat()}] {operation} | {detail}\n\n- 세션에서 실행했다.\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare", help="초기 D1–D5 vault를 새 위치에 복사")
    prepare.add_argument("--destination", type=Path, default=ROOT / "runs" / "wiki_demo")
    ingest = sub.add_parser("ingest", help="새 자료의 변경 계획을 만들고 diff 표시")
    ingest.add_argument("--vault", type=Path, required=True)
    ingest.add_argument("--source", type=Path, required=True)
    ingest.add_argument("--mode", choices=["fixture", "llm"], default="fixture")
    ingest.add_argument("--plan", type=Path, default=ROOT / "runs" / "D6_plan.json")
    apply = sub.add_parser("apply", help="검토한 plan 파일 그대로 반영")
    apply.add_argument("--vault", type=Path, required=True)
    apply.add_argument("--plan", type=Path, required=True)
    query = sub.add_parser("query", help="위키 페이지를 찾아 질문")
    query.add_argument("--vault", type=Path, required=True)
    query.add_argument("--question", required=True)
    query.add_argument("--mode", choices=["extractive", "llm"], default="extractive")
    query.add_argument("--record", action="store_true")
    check = sub.add_parser("lint", help="출처·링크·일정 충돌 점검")
    check.add_argument("--vault", type=Path, required=True)
    check.add_argument("--llm", action="store_true", help="추가 의미 점검은 모델 호출")
    check.add_argument("--record", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        if args.destination.exists():
            raise FileExistsError(f"이미 존재합니다: {args.destination}. 새 경로를 지정하세요.")
        args.destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(ROOT / "wiki_vault", args.destination)
        print(f"초기 위키 준비: {args.destination.resolve()}")
    elif args.command == "ingest":
        body = plan_ingest(args.vault, args.source, args.mode, args.plan)
        print(preview(args.vault, body))
        print(f"\n계획 저장: {args.plan.resolve()}\n검토 후 apply --plan에 같은 파일을 전달하세요.")
    elif args.command == "apply":
        print("반영한 파일:\n" + "\n".join(f"- {name}" for name in apply_plan(args.vault, args.plan)))
    elif args.command == "query":
        print(answer_extractively(args.vault, args.question) if args.mode == "extractive" else answer_with_llm(args.vault, args.question))
        if args.record:
            record(args.vault, "query", args.question)
    elif args.command == "lint":
        findings = lint(args.vault)
        print("[기계적 점검]" if not findings else "[기계적 점검 결과]")
        print("발견 항목 없음" if not findings else "\n".join(f"- {item}" for item in findings))
        if args.llm:
            print("\n[에이전트 의미 점검]\n" + qualitative_lint(args.vault))
        if args.record:
            record(args.vault, "lint", f"발견 {len(findings)}건")


if __name__ == "__main__":
    main()
