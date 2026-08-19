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
│   ├── fonts.py         # Registers the Nunito Sans faces, falls back to Helvetica
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

**Quote layout**: The PDF follows the "Editorial" design direction — a white page with no colour bands, the quote number set large in Abastible blue, a borderless table and the total as the one orange element. Measurements in `pdf_service.py` come from an 816x1056 px artboard (US Letter at 96 dpi) scaled by 72/96 into points; keep that relationship when adjusting the layout.

**Net vs tax-included presentation**: The table is presented **net**, because that is what customers ask for, while the arithmetic stays anchored on the tax-included SAP price. The net unit price prints with two decimals on purpose — rounded to a whole peso it no longer multiplies back to the line's net total (off by up to 13 pesos), which a customer with a calculator will find. `P. unit. c/IVA` sits alongside it as the SAP anchor. Per-line net totals sum exactly to the `Neto` row because both derive from `calculate_pricing().subtotal`.

**Brand colors**: `ABAS_BLUE` (#011689) and `ORANGE` (#FC4F00) are sampled from the official logo files. Do not adjust them by eye.

**Typography**: Nunito Sans (OFL) ships in `assets/fonts/`. `brand_fonts()` registers the faces once per process and falls back to Helvetica if a file is missing, so a bad deploy degrades instead of failing. Keep `!assets/fonts/OFL.txt` in `.gitignore` — the blanket `*.txt` rule would otherwise drop the license.

**Commercial blocks**: `COMMERCIAL_TERMS` and `TRANSFER_DETAILS` in `constants.py` print under the totals. Transfer details come from the `QUOTE_TRANSFER_DETAILS` environment variable — this repository is public, so the real bank details must never be committed; without it the quote prints visible `[BANCO]`-style placeholders.

**Assets**: The quote header uses `assets/abastible-logo-positivo.png` — the mark in positive on white, which is what the Editorial direction was designed around. The current official lockups in `assets/` are all set on a blue field; dropping one into this layout puts a solid blue block on a page built to be airy, so it was rejected deliberately. Replace this file if the brand manual yields a positive version of the current lockup: `_logo_size()` reads the aspect ratio from the file, so no code changes are needed. Output PDFs are written to `outputs/` (auto-created).
