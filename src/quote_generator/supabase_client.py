from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date

from supabase import Client, create_client


def _get_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


@dataclass
class CustomerData:
    name: str
    rut: str
    address: str
    city: str


@dataclass
class ResolvedItem:
    list_price_id: str
    format_code: str
    description: str
    quantity: int
    unit_price_with_tax: int  # list_prices.price — already includes 19% VAT
    discount_pct: float       # customer_discounts.discount, defaults to 0.0


def fetch_customer(customer_id: str) -> CustomerData:
    client = _get_client()
    row = (
        client.table("customers")
        .select("name, rut, address, city")
        .eq("id", customer_id)
        .single()
        .execute()
    )
    d = row.data
    return CustomerData(name=d["name"], rut=d["rut"], address=d["address"], city=d["city"])


def resolve_items(
    customer_id: str,
    items: list[dict],
    reference_date: date,
) -> list[ResolvedItem]:
    """Resolve list prices and customer discounts for each requested item."""
    client = _get_client()
    ref = reference_date.isoformat()
    resolved = []

    for item in items:
        list_price_id = item["list_price_id"]
        quantity = item["quantity"]
        description = item["description"]

        lp_row = (
            client.table("list_prices")
            .select("id, format_code, price")
            .eq("id", list_price_id)
            .lte("valid_from", ref)
            .or_(f"valid_until.is.null,valid_until.gte.{ref}")
            .single()
            .execute()
        )
        lp = lp_row.data
        format_code = lp["format_code"]
        unit_price = lp["price"]

        disc_rows = (
            client.table("customer_discounts")
            .select("discount")
            .eq("customer_id", customer_id)
            .eq("format_code", format_code)
            .lte("valid_from", ref)
            .or_(f"valid_until.is.null,valid_until.gte.{ref}")
            .execute()
        )
        discount_pct = float(disc_rows.data[0]["discount"]) if disc_rows.data else 0.0

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
    customer_id: str,
    contact_name: str,
    resolved_items: list[ResolvedItem],
    notes: str | None,
) -> str:
    """Insert quotation and its items into Supabase, returning the new quotation id."""
    client = _get_client()
    today = date.today().isoformat()

    q_row = (
        client.table("quotations")
        .insert({
            "number": number,
            "date": today,
            "customer_id": customer_id,
            "contact_name": contact_name,
            "status": "draft",
            "notes": notes or "",
        })
        .execute()
    )
    quotation_id = q_row.data[0]["id"]

    qi_rows = [
        {
            "quotation_id": quotation_id,
            "list_price_id": item.list_price_id,
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
