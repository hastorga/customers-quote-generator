from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import date
from http.server import BaseHTTPRequestHandler
from pathlib import Path

# Make the src package importable in Vercel's serverless runtime
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from quote_generator.core.constants import DEFAULT_ISSUER, VALIDITY_DAYS
from quote_generator.core.models import ClientInfo, QuoteDocument, QuoteItem
from quote_generator.services.pdf_service import render_quote_pdf
from quote_generator.supabase_client import (
    _get_client,
    fetch_customer,
    resolve_items,
    save_quotation,
)
from quote_generator.utils.pricing import calculate_pricing

LOGO_PATH = str(Path(__file__).parent.parent / "assets" / "abastible-logo.png")

_CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        for k, v in _CORS.items():
            self.send_header(k, v)
        self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            customer_id: str = body["customer_id"]
            contact_name: str = body["contact_name"]
            notes: str | None = body.get("notes")
            items: list[dict] = body["items"]
            if not items:
                raise ValueError("items must be a non-empty list")
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            self._error(400, str(e))
            return

        try:
            today = date.today()

            customer = fetch_customer(customer_id)
            resolved = resolve_items(customer_id, items, today)

            rpc_result = _get_client().rpc("nextval_for_quote", {}).execute()
            quote_number = int(rpc_result.data)

            # PDF renderer supports one item per document; use the first
            first = resolved[0]
            client_info = ClientInfo(
                contact_name=contact_name,
                company_name=customer.name,
                tax_id=customer.rut,
                address=customer.address,
                city=customer.city,
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

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp_path = tmp.name

            document = QuoteDocument(
                quote_number=str(quote_number).zfill(3),
                issue_date=today,
                issuer=DEFAULT_ISSUER,
                client=client_info,
                item=quote_item,
                logo_path=LOGO_PATH,
                output_path=tmp_path,
                validity_days=VALIDITY_DAYS,
            )
            render_quote_pdf(document, pricing)
            with open(tmp_path, "rb") as f:
                pdf_bytes = f.read()
            os.unlink(tmp_path)

            save_quotation(quote_number, customer_id, contact_name, resolved, notes)

            filename = f"cotizacion_{str(quote_number).zfill(3)}.pdf"
            self.send_response(200)
            for k, v in _CORS.items():
                self.send_header(k, v)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(pdf_bytes)))
            self.end_headers()
            self.wfile.write(pdf_bytes)

        except Exception as e:
            self._error(500, str(e))

    def _error(self, status: int, message: str) -> None:
        body = json.dumps({"error": message}).encode()
        self.send_response(status)
        for k, v in _CORS.items():
            self.send_header(k, v)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
