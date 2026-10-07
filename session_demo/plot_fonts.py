"""Select an installed Korean font for Matplotlib graph labels."""

from __future__ import annotations

import os
from pathlib import Path

from matplotlib import font_manager


def korean_font_properties() -> font_manager.FontProperties:
    candidates = [
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "malgun.ttf",
        Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/System/Library/Fonts/AppleGothic.ttf"),
    ]
    for path in candidates:
        if path.is_file():
            return font_manager.FontProperties(fname=str(path))
    supported = ("malgun gothic", "nanumgothic", "noto sans cjk kr", "applegothic")
    for font in font_manager.fontManager.ttflist:
        if font.name.casefold() in supported and Path(font.fname).is_file():
            return font_manager.FontProperties(fname=font.fname)
    raise RuntimeError("한글 글꼴을 찾지 못했습니다. 맑은 고딕, 나눔고딕, Noto Sans CJK 중 하나를 설치하세요.")


def apply_korean_font(ax) -> None:
    """NetworkX가 만든 노드/간선 라벨에 실제 글꼴 파일을 지정한다."""
    font = korean_font_properties()
    for label in ax.texts:
        label.set_fontproperties(font)
