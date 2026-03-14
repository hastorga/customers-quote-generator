from __future__ import annotations

from datetime import date
from pathlib import Path

from quote_generator.utils.formatting import format_clp_int
from quote_generator.core.models import ClientInfo, QuoteDocument, QuoteItem
from quote_generator.core.constants import DEFAULT_ISSUER, VALIDITY_DAYS
from quote_generator.services.pdf_service import render_quote_pdf
from quote_generator.services.supabase_service import SupabaseService
from quote_generator.utils.pricing import calculate_pricing


def build_default_quote() -> QuoteDocument:
    quote_number = "001"
    output_name = f"QUOTE_{quote_number}_INGREDION_ABASTIBLE.pdf"

    # Mock DB Fetching
    supabase = SupabaseService()
    client = supabase.get_client_info(client_id="ingredion_123")
    item = supabase.build_quote_item(
        client_id="ingredion_123",
        cylinder_type="Aluminum VM gas load",
        quantity=18,
        description="Delivery to Quilicura",
    )

    return QuoteDocument(
        quote_number=quote_number,
        issue_date=date.today(),
        issuer=DEFAULT_ISSUER,
        client=client,
        item=item,
        logo_path="assets/abastible-logo.png",
        output_path=str(Path("outputs") / output_name),
        validity_days=VALIDITY_DAYS,
    )


def run() -> None:
    quote = build_default_quote()
    pricing = calculate_pricing(
        quantity=quote.item.quantity,
        unit_price_with_tax=quote.item.unit_price_with_tax,
        discount_percent=quote.item.discount_percent,
    )

    Path("outputs").mkdir(parents=True, exist_ok=True)
    render_quote_pdf(quote, pricing)

    print(f"Generated PDF: {quote.output_path}")
    print(f"Subtotal: $ {format_clp_int(pricing.subtotal)}")
    print(f"Tax 19%: $ {format_clp_int(pricing.tax)}")
    print(f"Total: $ {format_clp_int(pricing.total)}")


if __name__ == "__main__":
    run()
