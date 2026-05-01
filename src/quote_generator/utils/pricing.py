from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PricingSummary:
    unit_price_net: float
    unit_price_discounted: float
    subtotal: int
    tax: int
    total: int


def calculate_pricing(
    quantity: int,
    unit_price_with_tax: float,
    discount_percent: float,
    tax_rate: float = 0.19,
) -> PricingSummary:
    """Compute totals from a tax-included unit price using CLP integer rounding."""
    unit_price_net = unit_price_with_tax / (1 + tax_rate)
    unit_price_discounted = unit_price_net * (1 - discount_percent)
    subtotal = round(quantity * unit_price_discounted)
    tax = round(subtotal * tax_rate)
    total = subtotal + tax

    return PricingSummary(
        unit_price_net=unit_price_net,
        unit_price_discounted=unit_price_discounted,
        subtotal=subtotal,
        tax=tax,
        total=total,
    )
