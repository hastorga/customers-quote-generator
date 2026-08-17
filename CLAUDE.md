# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                  # Install/sync dependencies
uv run quote-generator \
  --customer-id <uuid> \
  --contact-name "Nombre" \
  --list-price-id <uuid> \
  --quantity 10 \
  --description "Despacho a Tiltil" \
  [--notes "texto opcional"]   # Generate PDF via CLI (requires SUPABASE_URL + SUPABASE_SERVICE_KEY)
pytest                   # Run all tests
pytest tests/test_pricing.py  # Run a single test file
```

## Architecture

This is a Python PDF quote generator for Abastible S.A. (Chilean gas distributor). It produces customer quotation PDFs using ReportLab.

```
src/quote_generator/
├── core/
│   ├── models.py        # Frozen dataclasses: IssuerInfo, ClientInfo, QuoteItem, QuoteDocument
│   └── constants.py     # Brand colors, UI strings (Spanish), default issuer, VALIDITY_DAYS
├── services/
│   ├── pdf_service.py   # ReportLab PDF rendering
│   └── supabase_service.py  # Data fetching — currently mocked, not wired to real API
├── utils/
│   ├── pricing.py       # Tax-inclusive pricing calculations and CLP rounding
│   └── formatting.py    # Chilean currency formatters (dots as thousands, commas as decimals)
└── app.py               # Orchestration entry point
```

## Key Concepts

**Tax-inclusive pricing model**: Unit prices in the system already include 19% IVA (VAT), and the quote is anchored on that tax-included price so it agrees with SAP peso for peso — SAP is the source of truth for what the customer is charged. `calculate_pricing()` in `utils/pricing.py` applies the discount to the tax-included unit price via `resolve_discounted_price()`, which rounds to the nearest peso **with ties going down** (SAP drops the half peso). Rounding per unit before multiplying by the quantity is deliberate: carrying an unrounded price into the multiplication makes the line total drift as the quantity grows. The net subtotal is then derived from the line total and the tax is the remainder, so `subtotal + tax == total` always holds exactly.

**Supabase service**: `SupabaseService` returns mock data and is not connected to a real database. It's designed to be swapped for a live implementation.

**All domain models are immutable** (`@dataclass(frozen=True)`). Construct new instances rather than mutating.

**UI strings are in Spanish** — keep all user-visible text in Spanish for the Chilean market.

**Assets**: Logo lives at `assets/abastible-logo.png`. Output PDFs are written to `outputs/` (auto-created).
