from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from quote_generator.core.constants import DEFAULT_ISSUER, VALIDITY_DAYS
from quote_generator.core.models import ClientInfo, QuoteDocument, QuoteItem
from quote_generator.utils.customers import detect_is_company
from quote_generator.services.pdf_service import render_quote_pdf
from quote_generator.supabase_client import _get_client, fetch_customer, resolve_items, save_quotation
from quote_generator.utils.formatting import format_clp_int
from quote_generator.utils.pricing import calculate_pricing


def run() -> None:
    parser = argparse.ArgumentParser(description="Genera una cotización PDF desde Supabase")
    parser.add_argument("--customer-id", required=True, help="UUID del cliente en Supabase")
    parser.add_argument("--contact-name", required=True, help="Nombre del contacto")
    parser.add_argument("--list-price-id", required=True, help="UUID del precio en list_prices")
    parser.add_argument("--quantity", type=int, required=True, help="Cantidad de unidades")
    parser.add_argument("--description", required=True, help="Descripción del ítem en el PDF")
    parser.add_argument("--notes", default=None, help="Notas opcionales para la cotización")
    args = parser.parse_args()

    today = date.today()

    customer = fetch_customer(args.customer_id)
    resolved = resolve_items(
        args.customer_id,
        [{"list_price_id": args.list_price_id, "quantity": args.quantity, "description": args.description}],
        today,
    )

    rpc_result = _get_client().rpc("nextval_for_quote", {}).execute()
    quote_number = int(rpc_result.data)  # type: ignore

    first = resolved[0]
    client_info = ClientInfo(
        company_name=customer.name,
        tax_id=customer.rut,
        contact_name=args.contact_name,
        is_company=detect_is_company(customer.rut, customer.name),
    )
    quote_item = QuoteItem(
        name=first.format_code,
        quantity=first.quantity,
        description=first.description,
        unit_price_with_tax=first.unit_price_with_tax,
        discount_percent=first.discount_pct,
    )
    pricing = calculate_pricing(
        quantity=quote_item.quantity,
        unit_price_with_tax=quote_item.unit_price_with_tax,
        discount_percent=quote_item.discount_percent,
    )

    Path("outputs").mkdir(parents=True, exist_ok=True)
    customer_slug = customer.name.lower().replace(" ", "-")
    output_path = str(Path("outputs") / f"quotation-{quote_number}-{customer_slug}.pdf")

    document = QuoteDocument(
        quote_number=str(quote_number).zfill(3),
        issue_date=today,
        issuer=DEFAULT_ISSUER,
        client=client_info,
        items=[quote_item],
        logo_path="assets/abastible-logo.png",
        output_path=output_path,
        validity_days=VALIDITY_DAYS,
    )
    render_quote_pdf(document, pricing)
    save_quotation(quote_number, args.customer_id, args.contact_name, resolved, args.notes)

    print(f"PDF generado: {output_path}")
    print(f"Subtotal: $ {format_clp_int(pricing.subtotal)}")
    print(f"IVA 19%:  $ {format_clp_int(pricing.tax)}")
    print(f"Total:    $ {format_clp_int(pricing.total)}")


if __name__ == "__main__":
    run()
