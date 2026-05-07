from __future__ import annotations

import logging
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

from flask import Flask, Response, jsonify, request

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from quote_generator.core.constants import DEFAULT_ISSUER, VALIDITY_DAYS
from quote_generator.core.models import ClientInfo, QuoteDocument, QuoteItem
from quote_generator.services.pdf_service import render_quote_pdf
from quote_generator.utils.customers import detect_is_company
from quote_generator.supabase_client import (
    _get_client,
    fetch_customer,
    resolve_items,
    save_quotation,
)
from quote_generator.utils.pricing import PricingSummary, calculate_pricing

LOGO_PATH = str(Path(__file__).parent.parent / "assets" / "abastible-logo.png")
ALLOWED_ORIGINS = {
    "https://abastible-llayllay.vercel.app",
    "https://abastible-sales-vue-hastorgas-projects.vercel.app",
    "https://abastible-sales-vue-git-main-hastorgas-projects.vercel.app",
    "http://localhost:5173",
    "http://localhost:5001",
    "http://localhost:3000",
}

app = Flask(__name__)


def _allowed_origin() -> str:
    origin = request.headers.get("Origin", "")
    return origin if origin in ALLOWED_ORIGINS else next(iter(ALLOWED_ORIGINS))


@app.before_request
def _log_request() -> None:
    logger.info("→ %s %s", request.method, request.path)


@app.after_request
def _log_response(response: Response) -> Response:
    logger.info("← %s %s %s", request.method, request.path, response.status_code)
    response.headers["Access-Control-Allow-Origin"] = _allowed_origin()
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.errorhandler(404)
def _not_found(e: Exception) -> tuple[Response, int]:
    logger.warning("404 %s %s", request.method, request.path)
    return jsonify({"error": "ruta no encontrada"}), 404


@app.errorhandler(405)
def _method_not_allowed(e: Exception) -> tuple[Response, int]:
    logger.warning("405 %s %s", request.method, request.path)
    return jsonify({"error": "método no permitido"}), 405


def _cors(response: Response) -> Response:
    response.headers["Access-Control-Allow-Origin"] = _allowed_origin()
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


def _validate_items(items: list[dict], is_prospect: bool) -> str | None:
    if not items:
        return "items debe ser una lista no vacía"
    for i, it in enumerate(items):
        item_type = str(it.get("type") or "refill")
        if item_type not in ("refill", "cylinder"):
            return f"items[{i}]: type debe ser 'refill' o 'cylinder'"

        try:
            qty = int(it.get("quantity", 0))
        except (TypeError, ValueError):
            return f"items[{i}]: quantity debe ser un entero"
        if qty <= 0:
            return f"items[{i}]: quantity debe ser > 0"

        if item_type == "refill":
            if "list_price_id" not in it:
                return f"items[{i}]: falta list_price_id"
            if is_prospect and "discount_pct" not in it:
                return f"items[{i}]: falta discount_pct (requerido para prospectos)"
        elif item_type == "cylinder":
            if "cylinder_id" not in it:
                return f"items[{i}]: falta cylinder_id"
            try:
                int(it["cylinder_id"])
            except (TypeError, ValueError):
                return f"items[{i}]: cylinder_id debe ser un entero"
    return None


@app.route("/generate_quotation", methods=["OPTIONS"])
def options():
    return _cors(Response())


@app.route("/generate_quotation", methods=["POST"])
def generate_quotation():
    try:
        body = request.get_json(force=True)
        customer_id: str | None = body.get("customer_id") or None
        prospect_name: str | None = body.get("prospect_name") or None
        prospect_rut: str | None = body.get("prospect_rut") or None
        contact_name: str = body.get("contact_name") or ""
        notes: str | None = body.get("notes")
        items: list[dict] = body.get("items") or []

        is_prospect = customer_id is None

        if is_prospect and not (prospect_name and prospect_rut):
            return _cors(jsonify({"error": "se requiere customer_id o (prospect_name + prospect_rut)"})), 400
        if not is_prospect and (prospect_name or prospect_rut):
            return _cors(jsonify({"error": "no se puede enviar customer_id junto a prospect_name/prospect_rut"})), 400

        error = _validate_items(items, is_prospect)
        if error:
            return _cors(jsonify({"error": error})), 400
    except (KeyError, TypeError) as e:
        return _cors(jsonify({"error": str(e)})), 400

    try:
        today = date.today()

        if is_prospect:
            client_info = ClientInfo(
                company_name=prospect_name,  # type: ignore[arg-type]
                tax_id=prospect_rut,         # type: ignore[arg-type]
                contact_name=contact_name,
                is_company=detect_is_company(prospect_rut, prospect_name),  # type: ignore[arg-type]
            )
            customer_slug = prospect_name.lower().replace(" ", "-")  # type: ignore[union-attr]
        else:
            customer = fetch_customer(customer_id)  # type: ignore[arg-type]
            client_info = ClientInfo(
                company_name=customer.name,
                tax_id=customer.rut,
                contact_name=contact_name,
                is_company=detect_is_company(customer.rut, customer.name),
            )
            customer_slug = customer.name.lower().replace(" ", "-")

        resolved = resolve_items(customer_id, items, today, is_prospect=is_prospect)

        rpc_result = _get_client().rpc("nextval_for_quote", {}).execute()
        quote_number = int(rpc_result.data)  # type: ignore

        quote_items: list[QuoteItem] = []
        total_subtotal = 0
        for r in resolved:
            qi = QuoteItem(
                name=r.display_name or r.format_code,
                quantity=r.quantity,
                description=r.description,
                unit_price_with_tax=r.unit_price_with_tax,
                discount_percent=r.discount_pct,
            )
            total_subtotal += calculate_pricing(
                qi.quantity, qi.unit_price_with_tax, qi.discount_percent
            ).subtotal
            quote_items.append(qi)

        total_tax = round(total_subtotal * 0.19)
        totals = PricingSummary(
            unit_price_net=0.0,
            unit_price_discounted=0.0,
            subtotal=total_subtotal,
            tax=total_tax,
            total=total_subtotal + total_tax,
        )

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        document = QuoteDocument(
            quote_number=str(quote_number).zfill(3),
            issue_date=today,
            issuer=DEFAULT_ISSUER,
            client=client_info,
            items=quote_items,
            logo_path=LOGO_PATH,
            output_path=tmp_path,
            validity_days=VALIDITY_DAYS,
        )
        render_quote_pdf(document, totals)
        with open(tmp_path, "rb") as f:
            pdf_bytes = f.read()
        os.unlink(tmp_path)

        save_quotation(
            quote_number,
            customer_id,
            contact_name,
            resolved,
            notes,
            prospect_name=prospect_name,
            prospect_rut=prospect_rut,
        )

        filename = f"quotation-{quote_number}-{customer_slug}.pdf"
        response = Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
        return _cors(response)

    except ValueError as e:
        return _cors(jsonify({"error": str(e)})), 400
    except Exception as e:
        logger.exception("Error generando cotización: %s", e)
        return _cors(jsonify({"error": str(e)})), 500


if __name__ == "__main__":
    app.run(port=5001, debug=True)
