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

**Tax-inclusive pricing model**: Unit prices in the system already include 19% IVA (VAT). `calculate_pricing()` in `utils/pricing.py` extracts the net price by dividing by 1.19, applies discounts on the net price, then recomputes IVA on top. Only the final subtotal and tax amounts are rounded to integer CLP (no decimal pesos).

**Supabase service**: `SupabaseService` returns mock data and is not connected to a real database. It's designed to be swapped for a live implementation.

**All domain models are immutable** (`@dataclass(frozen=True)`). Construct new instances rather than mutating.

**UI strings are in Spanish** — keep all user-visible text in Spanish for the Chilean market.

**Assets**: Logo lives at `assets/abastible-logo.png`. Output PDFs are written to `outputs/` (auto-created).
