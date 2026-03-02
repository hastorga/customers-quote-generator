# Customers Quote Generator

Generate customer quote PDFs using ReportLab.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

## Development Environment (uv)

1. Create and sync the virtual environment:

```bash
uv sync
```

2. Run the project:

```bash
uv run python main.py
```

Or use the script entrypoint:

```bash
uv run quote-generator
```

## Project Structure

- `main.py`: thin entrypoint.
- `src/quote_generator/models.py`: quote data models.
- `src/quote_generator/pricing.py`: pricing and tax calculations.
- `src/quote_generator/formatting.py`: Chilean number formatting helpers.
- `src/quote_generator/pdf_renderer.py`: PDF layout and rendering logic.
- `src/quote_generator/app.py`: application orchestration.
- `assets/`: static files such as logos.
- `outputs/`: generated quote PDFs.

## Notes

- Pricing calculations assume unit price includes VAT (19%).
- Intermediate values keep full precision; subtotal and tax are rounded to integer CLP.
