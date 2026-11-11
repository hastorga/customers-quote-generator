from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from typing import Any, cast

from postgrest import SyncPostgrestClient
from postgrest.exceptions import APIError
from supabase import Client, create_client


def _get_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


class CallerRejected(Exception):
    """The caller's token was refused, or it does not reach the requested rows."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


# PostgREST codes for a missing, malformed, expired or badly signed JWT.
_TOKEN_ERROR_CODES = {"PGRST301", "PGRST302", "PGRST303"}


def authorize_caller(
    access_token: str,
    customer_id: str | None,
    list_price_ids: list[str],
    cylinder_ids: list[int],
) -> str:
    """Ask the database, as the caller, whether they may quote these rows.

    The request goes out with the caller's own token (and the anon key), so
    PostgREST verifies the signature and expiry and authorize_quotation() runs
    as that user: it checks the role matrix and that the customer, list prices
    and cylinders belong to the caller's branch. Returns that branch id, which
    is the only one the service writes under.
    """
    url = os.environ["SUPABASE_URL"]
    anon_key = os.environ["SUPABASE_ANON_KEY"]
    client = SyncPostgrestClient(
        f"{url}/rest/v1",
        headers={
            "apikey": anon_key,
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        result = client.rpc(
            "authorize_quotation",
            {
                "p_customer_id": customer_id,
                "p_list_price_ids": list_price_ids,
                "p_cylinder_ids": cylinder_ids,
            },
        ).execute()
    except APIError as error:
        code = error.code or ""
        if code in _TOKEN_ERROR_CODES or "JWT" in (error.message or ""):
            raise CallerRejected(401, "sesión inválida o expirada") from error
        if code == "42501":
            raise CallerRejected(403, "sin permiso para generar cotizaciones") from error
        if code == "P0002":
            raise CallerRejected(404, "cliente, precio o cilindro no encontrado en la sucursal") from error
        if code == "22P02":
            raise CallerRejected(400, "identificador inválido") from error
        raise
    finally:
        client.session.close()

    branch_id = result.data
    if not branch_id:
        raise CallerRejected(403, "sin permiso para generar cotizaciones")
    return str(branch_id)


@dataclass
class CustomerData:
    name: str
    rut: str


@dataclass
class CylinderData:
    id: int
    name: str
    cylinder_price: int
    format_code: str


@dataclass
class ResolvedItem:
    list_price_id: str | None
    format_code: str
    description: str
    quantity: int
    unit_price_with_tax: int  # list_prices.price or cylinders.cylinder_price — already includes 19% VAT
    discount_pct: float       # 0.0 for cylinders; customer_discounts.discount or request value for refills
    cylinder_id: int | None = None
    display_name: str = ""    # human-readable name for PDF; empty = fall back to ITEM_NAMES lookup


def fetch_customer(customer_id: str) -> CustomerData:
    client = _get_client()
    row = (
        client.table("customers")
        .select("name, rut")
        .eq("id", customer_id)
        .single()
        .execute()
    )
    d = cast(dict[str, Any], row.data)
    return CustomerData(name=str(d["name"]), rut=str(d["rut"]))


def fetch_cylinder(cylinder_id: int) -> CylinderData:
    """Fetch a cylinder by ID. Raises ValueError if cylinder_price is not set."""
    client = _get_client()
    row = (
        client.table("cylinders")
        .select("id, name, cylinder_price, format_code")
        .eq("id", cylinder_id)
        .single()
        .execute()
    )
    d = cast(dict[str, Any], row.data)
    if d["cylinder_price"] is None:
        raise ValueError(f"El cilindro {cylinder_id} no tiene precio de envase definido")
    return CylinderData(
        id=int(d["id"]),
        name=str(d["name"]),
        cylinder_price=int(d["cylinder_price"]),
        format_code=str(d["format_code"]),
    )


def resolve_items(
    customer_id: str | None,
    items: list[dict[str, Any]],
    reference_date: date,
    is_prospect: bool = False,
) -> list[ResolvedItem]:
    """Resolve prices and discounts for each item.

    Item types:
    - "refill" (default): looks up list_prices; discount from customer_discounts or request.
    - "cylinder": looks up cylinders.cylinder_price; discount is always 0.
    """
    client = _get_client()
    ref = reference_date.isoformat()
    resolved = []

    for item in items:
        item_type = str(item.get("type") or "refill")
        quantity = int(item["quantity"])
        description = str(item.get("description") or "")

        if item_type == "cylinder":
            cylinder = fetch_cylinder(int(item["cylinder_id"]))
            resolved.append(ResolvedItem(
                list_price_id=None,
                format_code=cylinder.format_code,
                description=description,
                quantity=quantity,
                unit_price_with_tax=cylinder.cylinder_price,
                discount_pct=0.0,
                cylinder_id=cylinder.id,
                display_name=f"Cilindro {cylinder.name}",
            ))
            continue

        # refill item
        list_price_id = str(item["list_price_id"])

        lp_row = (
            client.table("list_prices")
            .select("id, format_code, price")
            .eq("id", list_price_id)
            .lte("valid_from", ref)
            .or_(f"valid_until.is.null,valid_until.gt.{ref}")
            .single()
            .execute()
        )
        lp = cast(dict[str, Any], lp_row.data)
        format_code = str(lp["format_code"])
        unit_price = int(lp["price"])

        if is_prospect:
            discount_pct = float(item["discount_pct"])
        else:
            disc_rows = (
                client.table("customer_discounts")
                .select("discount")
                .eq("customer_id", customer_id)
                .eq("format_code", format_code)
                .lte("valid_from", ref)
                .or_(f"valid_until.is.null,valid_until.gt.{ref}")
                .order("valid_from", desc=True)
                .limit(1)
                .execute()
            )
            disc_data = cast(list[dict[str, Any]], disc_rows.data)
            discount_pct = float(disc_data[0]["discount"]) if disc_data else 0.0

        resolved.append(ResolvedItem(
            list_price_id=list_price_id,
            format_code=format_code,
            description=description,
            quantity=quantity,
            unit_price_with_tax=unit_price,
            discount_pct=discount_pct,
        ))

    return resolved


def save_quotation(
    number: int,
    customer_id: str | None,
    contact_name: str,
    resolved_items: list[ResolvedItem],
    notes: str | None,
    *,
    branch_id: str,
    prospect_name: str | None = None,
    prospect_rut: str | None = None,
) -> str:
    """Insert quotation and its items into Supabase, returning the new quotation id.

    ``branch_id`` must be supplied explicitly: this service inserts with the
    service-role key (no authenticated user), so the ``branch_id`` column default
    ``current_branch_id()`` resolves to NULL and violates the NOT NULL constraint.
    """
    client = _get_client()
    today = date.today().isoformat()

    q_payload: dict[str, Any] = {
        "number": number,
        "date": today,
        "branch_id": branch_id,
        "customer_id": customer_id,
        "contact_name": contact_name,
        "status": "draft",
        "notes": notes or "",
    }
    if prospect_name is not None:
        q_payload["prospect_name"] = prospect_name
    if prospect_rut is not None:
        q_payload["prospect_rut"] = prospect_rut

    q_row = client.table("quotations").insert(q_payload).execute()
    q_data = cast(list[dict[str, Any]], q_row.data)
    quotation_id = str(q_data[0]["id"])

    qi_rows: list[Any] = [
        {
            "quotation_id": quotation_id,
            "branch_id": branch_id,
            "list_price_id": item.list_price_id,
            "cylinder_id": item.cylinder_id,
            "position": idx + 1,
            "format_code": item.format_code,
            "description": item.description,
            "quantity": item.quantity,
            "unit_price": item.unit_price_with_tax,
            "discount_pct": item.discount_pct,
        }
        for idx, item in enumerate(resolved_items)
    ]
    client.table("quotation_items").insert(qi_rows).execute()

    return quotation_id
