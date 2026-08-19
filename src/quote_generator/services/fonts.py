from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# <repo>/src/quote_generator/services/fonts.py -> <repo>
FONT_DIR = Path(__file__).resolve().parents[3] / "assets" / "fonts"

# Nunito Sans is the closest open face to the Abastible wordmark: geometric,
# rounded terminals, open apertures. Shipped under the OFL (see OFL.txt).
_FACES = (
    ("NunitoSans", "NunitoSans-Regular.ttf", "Helvetica"),
    ("NunitoSans-Bold", "NunitoSans-Bold.ttf", "Helvetica-Bold"),
    ("NunitoSans-Light", "NunitoSans-Light.ttf", "Helvetica"),
)


@dataclass(frozen=True)
class Fonts:
    regular: str
    bold: str
    light: str

    @property
    def is_branded(self) -> bool:
        return self.regular.startswith("NunitoSans")


@lru_cache(maxsize=1)
def brand_fonts() -> Fonts:
    """Register the brand faces, falling back to Helvetica if a file is missing.

    A missing font file must not take a quote down: the deploy still renders,
    just in the built-in face. Registration is cached because ReportLab keeps
    fonts in a process-wide registry and re-registering on every request would
    reparse the TTFs.
    """
    resolved: list[str] = []
    for name, filename, fallback in _FACES:
        path = FONT_DIR / filename
        try:
            pdfmetrics.registerFont(TTFont(name, str(path)))
            resolved.append(name)
        except Exception:
            resolved.append(fallback)
    return Fonts(*resolved)
