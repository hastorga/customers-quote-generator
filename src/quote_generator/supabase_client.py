from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from typing import Any, cast

from supabase import Client, create_client


def _get_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


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
            .or_(f"valid_until.is.null,valid_until.gte.{ref}")
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
                .or_(f"valid_until.is.null,valid_until.gte.{ref}")
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
    prospect_name: str | None = None,
    prospect_rut: str | None = None,
) -> str:
    """Insert quotation and its items into Supabase, returning the new quotation id."""
    client = _get_client()
    today = date.today().isoformat()

    q_payload: dict[str, Any] = {
        "number": number,
        "date": today,
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
