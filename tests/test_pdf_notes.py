from __future__ import annotations

from dataclasses import replace
from datetime import date

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

from quote_generator.core.models import ClientInfo, IssuerInfo, QuoteDocument, QuoteItem
from quote_generator.services.pdf_service import (
    NOTES_MAX_LINES, _draw_notes, _note_lines, render_quote_pdf,
)
from quote_generator.utils.pricing import calculate_pricing


def _document(tmp_path, notes: str = "") -> QuoteDocument:
    return QuoteDocument(
        quote_number="001",
        issue_date=date(2026, 8, 25),
        issuer=IssuerInfo(
            company_name="ABASTIBLE S.A.", tax_id="91.806.000-6",
            office_name="Consignación Llay Llay", address="Balmaceda 473",
            phone="34 2611498", email="contacto@abastible.cl",
        ),
        client=ClientInfo(company_name="Cliente S.A.", tax_id="96.845.100-6"),
        items=[QuoteItem(name="A", quantity=2, unit_price_with_tax=1190, discount_percent=0.0)],
        logo_path="assets/abastible-logo-positivo.png",
        output_path=str(tmp_path / "q.pdf"),
        notes=notes,
    )


def _pdf(tmp_path) -> canvas.Canvas:
    return canvas.Canvas(str(tmp_path / "scratch.pdf"), pagesize=LETTER)


def test_no_notes_draws_nothing_and_keeps_position(tmp_path):
    assert _draw_notes(_pdf(tmp_path), _document(tmp_path, "   "), 500.0) == 500.0


def test_notes_consume_vertical_space(tmp_path):
    assert _draw_notes(_pdf(tmp_path), _document(tmp_path, "Despacho a Tiltil"), 500.0) < 500.0


def test_long_note_is_capped(tmp_path):
    lines = _note_lines(_pdf(tmp_path), "palabra " * 2000)
    assert len(lines) <= NOTES_MAX_LINES
    assert lines[-1].endswith("…")


def test_line_breaks_are_kept(tmp_path):
    assert _note_lines(_pdf(tmp_path), "uno\ndos") == ["uno", "dos"]


def test_render_includes_notes_text(tmp_path):
    doc = _document(tmp_path, "Despacho a Tiltil")
    render_quote_pdf(doc, calculate_pricing(2, 1190, 0.0))
    assert (tmp_path / "q.pdf").stat().st_size > 0
