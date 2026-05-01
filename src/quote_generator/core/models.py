from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class IssuerInfo:
    company_name: str
    tax_id: str
    office_name: str
    address: str
    phone: str
    email: str


@dataclass(frozen=True)
class ClientInfo:
    contact_name: str
    company_name: str
    tax_id: str


@dataclass(frozen=True)
class QuoteItem:
    name: str
    quantity: int
    unit_price_with_tax: int
    discount_percent: float
    description: str = ""


@dataclass(frozen=True)
class QuoteDocument:
    quote_number: str
    issue_date: date
    issuer: IssuerInfo
    client: ClientInfo
    items: list[QuoteItem]
    logo_path: str
    output_path: str
    validity_days: int = 10
