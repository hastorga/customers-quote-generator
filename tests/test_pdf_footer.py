from __future__ import annotations

from datetime import date

from quote_generator.core.constants import TRANSFER_DETAILS_PLACEHOLDER
from quote_generator.core.models import ClientInfo, IssuerInfo, QuoteDocument
from quote_generator.services.pdf_service import _footer_legal, _transfer_lines


def _issuer(footer_legal: str = "", transfer_details: tuple[str, ...] = ()) -> IssuerInfo:
    return IssuerInfo(
        company_name="ABASTIBLE S.A.",
        tax_id="91.806.000-6",
        office_name="Consignación Abastible Llay Llay",
        address="Balmaceda 473, Llay Llay, Valparaíso",
        phone="34 2611498",
        email="contacto@abastible.cl",
        footer_legal=footer_legal,
        transfer_details=transfer_details,
    )


def _document(issuer: IssuerInfo) -> QuoteDocument:
    return QuoteDocument(
        quote_number="001",
        issue_date=date(2026, 8, 25),
        issuer=issuer,
        client=ClientInfo(company_name="Cliente S.A.", tax_id="96.845.100-6"),
        items=[],
        logo_path="assets/abastible-logo-positivo.png",
        output_path="outputs/unused.pdf",
    )


class TestFooterLegal:
    def test_uses_the_branch_value_verbatim(self):
        issuer = _issuer("Abastible S.A. · Consignación Llay Llay · abastible.cl")
        assert (
            _footer_legal(_document(issuer))
            == "Abastible S.A. · Consignación Llay Llay · abastible.cl"
        )

    def test_composes_one_from_the_office_name_when_unset(self):
        """The one issuer field a branch may omit: it degrades, it does not fail."""
        composed = _footer_legal(_document(_issuer()))
        assert "Consignación Abastible Llay Llay" in composed
        assert "{" not in composed


class TestTransferLines:
    def test_prints_the_issuing_branchs_own_details(self):
        lines = ("Titular X · 1-9", "Banco Y · Cta. 123")
        assert _transfer_lines(_document(_issuer(transfer_details=lines))) == lines

    def test_prints_visible_placeholders_when_the_branch_has_none(self):
        """Never another branch's account, and never a silently empty block."""
        assert _transfer_lines(_document(_issuer())) == TRANSFER_DETAILS_PLACEHOLDER
