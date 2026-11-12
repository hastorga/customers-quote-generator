# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                  # Install/sync dependencies
uv run quote-generator \
  --branch-id <uuid> \
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
│   └── constants.py     # Brand colors, UI strings (Spanish), COMPANY_NAME/COMPANY_TAX_ID, VALIDITY_DAYS
├── services/
│   ├── pdf_service.py   # ReportLab PDF rendering
│   └── fonts.py         # Registers the Nunito Sans faces, falls back to Helvetica
├── supabase_client.py   # Live Supabase access: customers, prices, branches (issuer), quotations
├── utils/
│   ├── pricing.py       # Tax-inclusive pricing calculations and CLP rounding
│   └── formatting.py    # Chilean currency formatters (dots as thousands, commas as decimals)
└── app.py               # Orchestration entry point
```

## Key Concepts

**Tax-inclusive pricing model**: Unit prices in the system already include 19% IVA (VAT), and the quote is anchored on that tax-included price so it agrees with SAP peso for peso — SAP is the source of truth for what the customer is charged. `calculate_pricing()` in `utils/pricing.py` applies the discount to the tax-included unit price via `resolve_discounted_price()`, which rounds to the nearest peso **with ties going down** (SAP drops the half peso). Rounding per unit before multiplying by the quantity is deliberate: carrying an unrounded price into the multiplication makes the line total drift as the quantity grows. The net subtotal is then derived from the line total and the tax is the remainder, so `subtotal + tax == total` always holds exactly.

**Supabase access**: `supabase_client.py` talks to the real database (customers, prices, branches, quotations) and is used by both the API and the CLI. There is no mock layer.

**Per-branch issuer**: the letterhead ("De" block and footer) is the *issuing branch's* identity, not a constant. `fetch_issuer(branch_id)` reads `office_name`, `address`, `phone`, `email` and `footer_legal` off the `branches` row named by the request's required `branch_id`; only `COMPANY_NAME` and `COMPANY_TAX_ID` stay constants, because they are Abastible S.A.'s and hold from any branch. A branch missing any of the four required fields makes the request **fail with a 400** — never a fallback. A quote carrying another branch's name and reply-to address renders perfectly and reaches the customer looking entirely correct, so nothing catches it; not producing the document is the safer failure. `footer_legal` is optional and composes from the office name when unset. The database enforces the same rule from the other side: `branches_active_requires_issuer` (in the `abastible-sales-vue` repo) forbids activating a branch without those four fields.

**All domain models are immutable** (`@dataclass(frozen=True)`). Construct new instances rather than mutating.

**UI strings are in Spanish** — keep all user-visible text in Spanish for the Chilean market.

**Quote layout**: The PDF follows the "Editorial" design direction — a white page with no colour bands, the quote number set large in Abastible blue, a borderless table and the total as the one orange element. Measurements in `pdf_service.py` come from an 816x1056 px artboard (US Letter at 96 dpi) scaled by 72/96 into points; keep that relationship when adjusting the layout.

**Net vs tax-included presentation**: The table is presented **net**, because that is what customers ask for, while the arithmetic stays anchored on the tax-included SAP price. The net unit price prints with two decimals on purpose — rounded to a whole peso it no longer multiplies back to the line's net total (off by up to 13 pesos), which a customer with a calculator will find. `P. unit. c/IVA` sits alongside it as the SAP anchor. Per-line net totals sum exactly to the `Neto` row because both derive from `calculate_pricing().subtotal`.

**Brand colors**: `ABAS_BLUE` (#011689) and `ORANGE` (#FC4F00) are sampled from the official logo files. Do not adjust them by eye.

**Typography**: Nunito Sans (OFL) ships in `assets/fonts/`. `brand_fonts()` registers the faces once per process and falls back to Helvetica if a file is missing, so a bad deploy degrades instead of failing. Keep `!assets/fonts/OFL.txt` in `.gitignore` — the blanket `*.txt` rule would otherwise drop the license.

**Commercial blocks**: `COMMERCIAL_TERMS` in `constants.py` and the branch's transfer details print under the totals. Transfer details are per-branch: `branches.transfer_details` (one line per `|`-separated entry) is read by `fetch_issuer` into `IssuerInfo.transfer_details`. They are optional — a branch with none prints the visible `[BANCO]`-style `TRANSFER_DETAILS_PLACEHOLDER`, and is **never** given another branch's account, because a quote that routes the customer's payment to the wrong account looks entirely correct. This repository is public, so real bank details must never be committed.

**Assets**: The quote header uses `assets/abastible-logo-positivo.png` — the mark in positive on white, which is what the Editorial direction was designed around. The current official lockups in `assets/` are all set on a blue field; dropping one into this layout puts a solid blue block on a page built to be airy, so it was rejected deliberately. Replace this file if the brand manual yields a positive version of the current lockup: `_logo_size()` reads the aspect ratio from the file, so no code changes are needed. Output PDFs are written to `outputs/` (auto-created).

## Releases

**Every merge to `main` is a release**: a version bump, a tag and a GitHub Release.

1. On `dev`, before opening the `dev` → `main` PR, bump `version` in `pyproject.toml` and run `uv lock` so `uv.lock` agrees. Commit as `chore(release): bump version to X.Y.Z`. Semver, pre-1.0: a new capability or a behaviour change is a minor bump, a fix is a patch.
2. Open the PR titled `Release X.Y.Z` and merge it.
3. `.github/workflows/release.yml` then tags `vX.Y.Z` and publishes the Release with generated notes. If the version was not bumped, the workflow fails on purpose ("tag already exists") instead of skipping the release — fix it by bumping on `dev` and merging again.

Do not create tags or releases by hand: the workflow owns them, which keeps the tag and `pyproject.toml` from drifting apart.
