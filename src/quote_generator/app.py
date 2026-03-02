from __future__ import annotations

from datetime import date
from pathlib import Path

from quote_generator.formatting import format_clp_int
from quote_generator.models import ClientInfo, IssuerInfo, QuoteDocument, QuoteItem
from quote_generator.pdf_renderer import render_quote_pdf
from quote_generator.pricing import calculate_pricing


def build_default_quote() -> QuoteDocument:
    quote_number = "001"
    output_name = f"QUOTE_{quote_number}_INGREDION_ABASTIBLE.pdf"

    return QuoteDocument(
        quote_number=quote_number,
        issue_date=date.today(),
        issuer=IssuerInfo(
            company_name="ABASTIBLE S.A.",
            tax_id="91.806.000-6",
            office_name="Consignacion Abastible Llay Llay",
            address="Balmaceda 473, Llay Llay, Valparaiso",
            phone="34 2611498 - 34 2612637 | +56 9 3006 7765",
            email="hector.astorga_externos@abastible.cl",
        ),
        client=ClientInfo(
            contact_name="JUAN MANUEL AREVALO",
            company_name="INGREDION CHILE S.A.",
            tax_id="96.845.100-6",
            address="AVDA. CANAVERAL 240",
            city="SANTIAGO",
        ),
        item=QuoteItem(
            name="Aluminum VM gas load",
            quantity=18,
            description="Delivery to Quilicura",
            unit_price_with_tax=34450,
            discount_percent=20,
        ),
        logo_path="assets/abastible-logo.png",
        output_path=str(Path("outputs") / output_name),
        validity_days=10,
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
