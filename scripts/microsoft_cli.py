"""Run Microsoft GraphRAG with the project's single OPENAI_API_KEY setting."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    load_dotenv(ROOT / ".env", override=False)
    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise RuntimeError(f"{ROOT / '.env'}에 OPENAI_API_KEY를 설정하세요.")
    local_cli = Path(sys.executable).parent / ("Scripts/graphrag.exe" if os.name == "nt" else "bin/graphrag")
    cli = str(local_cli) if local_cli.is_file() else shutil.which("graphrag")
    if not cli:
        raise RuntimeError("GraphRAG CLI가 없습니다. requirements-microsoft.txt를 설치하세요.")
    subprocess.run([cli, *sys.argv[1:]], env=os.environ.copy(), check=True)


if __name__ == "__main__":
    main()
