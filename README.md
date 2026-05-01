# Customers Quote Generator

Flask REST API that generates quote PDFs for Abastible S.A. (Chilean gas distributor).
Customer data, list prices, and discounts are fetched from Supabase; the resulting PDF is returned directly in the HTTP response.
Deployed as a serverless function on Vercel.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- A Supabase project with the required environment variables

## Environment variables

Create a `.env` file at the project root (not committed):

```
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_KEY=<service_role_key>
```

## Installation

```bash
uv sync
```

## Running locally

> macOS reserves port 5000 for AirPlay Receiver. Use port 5001 instead.

```bash
uv run python api/index.py
```

The API will be available at `http://localhost:5001`.

### Generate a quote

```bash
curl -X POST http://localhost:5001/generate_quotation \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "<uuid>",
    "contact_name": "Contact Name",
    "notes": "Optional notes",
    "items": [
      {
        "list_price_id": "<uuid>",
        "quantity": 10,
        "description": "11 kg refill"
      }
    ]
  }' \
  --output quote.pdf
```

The response is the PDF as `application/pdf`.

## Project structure

```
api/
└── index.py              # Flask app — entry point for Vercel and local development

src/quote_generator/
├── core/
│   ├── models.py         # Frozen dataclasses: IssuerInfo, ClientInfo, QuoteItem, QuoteDocument
│   └── constants.py      # Brand colors, Spanish UI strings, default issuer, validity days
├── services/
│   └── pdf_service.py    # PDF layout and rendering with ReportLab
├── utils/
│   ├── pricing.py        # Tax-inclusive pricing calculations and CLP rounding
│   └── formatting.py     # Chilean currency formatters (dot thousands, comma decimal)
├── supabase_client.py    # Fetches customers, prices, discounts; saves quotations
└── app.py                # CLI entry point (quote-generator)

assets/
└── abastible-logo.png

tests/
├── test_pricing.py
└── test_supabase_client.py

vercel.json               # Serverless deployment configuration
```

## Tests

```bash
pytest
pytest tests/test_pricing.py   # single file
```

## Deploying to Vercel

`vercel.json` configures `api/index.py` as a Python function and bundles `src/` and `assets/`.
The environment variables (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`) must be set in the Vercel project settings.

```bash
vercel deploy --prod
```

## Pricing model

Unit prices stored in Supabase already include 19% VAT. `calculate_pricing()` extracts the net price by dividing by 1.19, applies the customer discount on the net, then recomputes VAT on top. Only the final subtotal and tax amounts are rounded to integer CLP.
