"""D1–D6을 각 1쪽 PDF로 만들어 MarkItDown 입력을 연습한다."""

from __future__ import annotations

import os
from pathlib import Path

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

ROOT = Path(__file__).resolve().parents[1]


def korean_font() -> Path:
    override = os.getenv("KOREAN_FONT_PATH")
    candidates = [Path(override)] if override else []
    candidates += [Path(r"C:\Windows\Fonts\malgun.ttf"), Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf")]
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError("한글 TTF 글꼴이 필요합니다. KOREAN_FONT_PATH를 설정하세요.")


def make_pdfs(destination: Path) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    pdfmetrics.registerFont(TTFont("SessionKorean", str(korean_font())))
    paths: list[Path] = []
    for source in sorted((ROOT / "data" / "project").glob("D*_*.md")):
        target = destination / source.with_suffix(".pdf").name
        page = Canvas(str(target), pagesize=A4)
        page.setTitle(source.stem)
        page.setFont("SessionKorean", 12)
        x, y = 50, A4[1] - 60
        for line in source.read_text(encoding="utf-8").splitlines():
            if not line:
                y -= 15
                continue
            remaining = line.removeprefix("# ")
            while remaining:
                cut = len(remaining)
                while cut > 1 and pdfmetrics.stringWidth(remaining[:cut], "SessionKorean", 12) > A4[0] - x - 50:
                    cut -= 1
                if cut < len(remaining):
                    space = remaining.rfind(" ", 0, cut + 1)
                    if space > 0:
                        cut = space
                page.drawString(x, y, remaining[:cut])
                remaining = remaining[cut:].lstrip()
                y -= 26
        page.save()
        extracted = "\n".join(page.extract_text() or "" for page in PdfReader(target).pages)
        if "결제" not in extracted and "보안" not in extracted and "오헤슬" not in extracted:
            raise RuntimeError(f"생성한 PDF에서 한글 원문을 확인하지 못했습니다: {target}")
        paths.append(target)
    return paths


if __name__ == "__main__":
    output = ROOT / "runs" / "pdf_input"
    for path in make_pdfs(output):
        print(path)
