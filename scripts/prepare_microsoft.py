"""GraphRAG 3.2.0 CLI 작업공간을 만들고 D1–D6 입력을 준비한다."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))


def compare_pdf_text(input_dir: Path) -> None:
    """PDF 변환 결과에 원문의 문장들이 남아 있는지 확인한다."""
    from markitdown import MarkItDown

    converter = MarkItDown()
    for source in sorted((ROOT / "data" / "project").glob("D*_*.md")):
        pdf = input_dir / source.with_suffix(".pdf").name
        extracted = "".join(converter.convert(str(pdf)).text_content.split())
        lines = [line.removeprefix("# ") for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
        lost = [line for line in lines if "".join(line.split()) not in extracted]
        if lost:
            raise RuntimeError(f"PDF 변환에서 원문 일부를 찾지 못했습니다: {pdf.name}: {lost}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=["text", "pdf"], default="text")
    parser.add_argument("--destination", type=Path, default=ROOT / "runs" / "microsoft")
    args = parser.parse_args()
    destination = args.destination.resolve()
    if destination.exists():
        raise FileExistsError(f"작업공간이 이미 있습니다: {destination}. 새 --destination을 사용하세요.")
    local_cli = Path(sys.executable).parent / ("Scripts/graphrag.exe" if os.name == "nt" else "bin/graphrag")
    cli = str(local_cli) if local_cli.is_file() else shutil.which("graphrag")
    if not cli:
        raise RuntimeError("graphrag CLI가 없습니다. python -m pip install -r requirements-microsoft.txt")
    load_dotenv(ROOT / ".env", override=False)
    chat_model = os.getenv("GRAPHRAG_CHAT_MODEL", "gpt-4o-mini")
    embed_model = os.getenv("GRAPHRAG_EMBED_MODEL", "text-embedding-3-small")
    destination.mkdir(parents=True)
    subprocess.run(
        [cli, "init", "--root", str(destination), "--model", chat_model, "--embedding", embed_model],
        check=True,
    )
    input_dir = destination / "input"
    input_dir.mkdir(exist_ok=True)
    if args.format == "text":
        for path in sorted((ROOT / "data" / "project").glob("D*_*.md")):
            (input_dir / path.with_suffix(".txt").name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        from make_pdf import make_pdfs

        make_pdfs(input_dir)
        compare_pdf_text(input_dir)
    config_path = destination / "settings.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if args.format == "pdf":
        config.setdefault("input", {})["type"] = "markitdown"
        config["input"]["file_pattern"] = r".*[.]pdf\Z"
    # 기본 템플릿의 person/organization/geo/event만으로는 이 자료의 프로젝트와
    # 프로그램을 놓치기 쉽다. 추출 대상 유형을 명시하되, 실제 결과는 원문과 대조한다.
    config["completion_models"]["default_completion_model"]["api_key"] = "${OPENAI_API_KEY}"
    config["embedding_models"]["default_embedding_model"]["api_key"] = "${OPENAI_API_KEY}"
    config.setdefault("extract_graph", {})["entity_types"] = [
        "person", "project", "program", "team", "organization", "event"
    ]
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    key = os.getenv("OPENAI_API_KEY", "").strip()
    (destination / ".env").unlink(missing_ok=True)  # CLI init의 중복 .env는 사용하지 않음
    print(f"입력 준비 완료: {input_dir}")
    if args.format == "pdf":
        print("PDF의 MarkItDown 변환 결과가 D1-D6 문장을 포함하는지 확인했습니다.")
    print("다음: python scripts/microsoft_cli.py index --root", destination, "--method standard --dry-run --skip-validation")
    if not key:
        print(f"API 키 없음: {ROOT / '.env'}에 OPENAI_API_KEY를 설정하세요.")


if __name__ == "__main__":
    main()
