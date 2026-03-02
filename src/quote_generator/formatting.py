from __future__ import annotations


def format_clp_int(value: int | float) -> str:
    """Format a number with Chilean thousand separators and no decimals."""
    return f"{int(value):,}".replace(",", ".")


def format_clp_decimal(value: int | float) -> str:
    """Format a number with Chilean thousand separators and 2 decimals."""
    whole, decimal = f"{value:,.2f}".split(".")
    return f"{whole.replace(',', '.')},{decimal}"
