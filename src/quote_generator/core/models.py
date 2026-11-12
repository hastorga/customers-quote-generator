from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class IssuerInfo:
    """Who is issuing the quote.

    ``company_name`` and ``tax_id`` are Abastible S.A.'s and are correct from any
    branch; everything below them is the issuing office's own identity and comes
    from the ``branches`` row named by the request's ``branch_id``.

    ``footer_legal`` is optional: an empty value makes the PDF compose the footer
    line from the company and office names, so a branch that never had one set
    still prints an attributable document.

    ``transfer_details`` is this branch's own bank account, one printed line per
    entry. It is optional and empty means "not on file": the PDF then prints
    visible placeholders. It is never borrowed from another branch, because a
    quote that routes the customer's payment to the wrong account looks entirely
    correct.
    """

    company_name: str
    tax_id: str
    office_name: str
    address: str
    phone: str
    email: str
    footer_legal: str = ""
    transfer_details: tuple[str, ...] = ()


@dataclass(frozen=True)
class ClientInfo:
    company_name: str
    tax_id: str
    contact_name: str = ""
    is_company: bool = True


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
    notes: str = ""
