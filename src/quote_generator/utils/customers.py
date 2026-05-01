from __future__ import annotations

_COMPANY_SUFFIXES = ("s.a.", "spa", "ltda", "e.i.r.l", "s.r.l", "cía", "corp", "s.c.")


def detect_is_company(rut: str, name: str) -> bool:
    number = int(rut.split("-")[0].replace(".", "").replace(" ", ""))
    if number >= 50_000_000:
        return True
    return any(s in name.lower() for s in _COMPANY_SUFFIXES)
