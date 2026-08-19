from __future__ import annotations

from dataclasses import dataclass

# Discounts are stored as numeric(4,2) — whole percentage points — so scaling by
# 10 000 always lands on an integer and keeps the arithmetic below it exact.
DISCOUNT_SCALE = 10_000


@dataclass(frozen=True)
class PricingSummary:
    unit_price_net: float
    unit_price_gross_discounted: int
    subtotal: int
    tax: int
    total: int
    # Net unit price *after* the discount. Quotes are presented net because that
    # is what customers ask for, and this is the only net figure that multiplies
    # back to the line's net total — the list-price `unit_price_net` above does
    # not. Defaults to 0.0 so callers that build a document-level summary by
    # summing lines (api/index.py) need not supply a per-unit value.
    unit_price_net_discounted: float = 0.0


def resolve_discounted_price(unit_price_with_tax: float, discount_percent: float) -> int:
    """Tax-included unit price after the customer's discount, rounded like SAP.

    Rounds to the nearest peso with ties going down, because SAP is the source of
    truth for these prices and it drops the half peso. List prices are multiples
    of 50 and discounts whole percentage points, so the tie is the case that
    actually comes up; other fractions round to the nearest peso rather than
    being floored, which would drop up to a peso for no reason.

    The arithmetic stays on integers: working from `price * (1 - discount)` in
    floating point mis-rounds (`1000 * (1 - 0.07)` is `929.9999999999999`).
    """
    list_price = int(round(unit_price_with_tax))
    scaled_discount = int(round(discount_percent * DISCOUNT_SCALE))
    scaled_price = list_price * (DISCOUNT_SCALE - scaled_discount)
    pesos, remainder = divmod(scaled_price, DISCOUNT_SCALE)
    return pesos + 1 if remainder * 2 > DISCOUNT_SCALE else pesos


def calculate_pricing(
    quantity: int,
    unit_price_with_tax: float,
    discount_percent: float,
    tax_rate: float = 0.19,
) -> PricingSummary:
    """Compute line totals from a tax-included unit price using CLP integer rounding.

    Anchored on the tax-included discounted unit price, so the quote agrees with
    SAP peso for peso. Rounding per unit before multiplying also keeps the line
    total from drifting as the quantity grows, which is what happens when an
    unrounded price is carried into the multiplication.

    The net subtotal is then derived from that line total and the tax is the
    remainder, so `subtotal + tax == total` always holds exactly.
    """
    unit_price_gross_discounted = resolve_discounted_price(unit_price_with_tax, discount_percent)
    total = unit_price_gross_discounted * quantity
    subtotal = round(total / (1 + tax_rate))
    tax = total - subtotal

    return PricingSummary(
        unit_price_net=unit_price_with_tax / (1 + tax_rate),
        unit_price_gross_discounted=unit_price_gross_discounted,
        subtotal=subtotal,
        tax=tax,
        total=total,
        unit_price_net_discounted=unit_price_gross_discounted / (1 + tax_rate),
    )
