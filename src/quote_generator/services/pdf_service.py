from __future__ import annotations

from dataclasses import dataclass

from reportlab.lib.colors import Color
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

from quote_generator.core.constants import (
    ABAS_BLUE, INK, LINE, LINE_SOFT, MUTED, ORANGE, PAYMENT_TERMS,
    TRANSFER_DETAILS, TEXT_GRAY, UI_STRINGS, ITEM_NAMES,
)
from quote_generator.core.models import QuoteDocument
from quote_generator.services.fonts import brand_fonts
from quote_generator.utils.formatting import format_clp_decimal, format_clp_int
from quote_generator.utils.pricing import PricingSummary, calculate_pricing

PAGE_WIDTH, PAGE_HEIGHT = LETTER

# The layout was drawn on an 816x1056 px artboard (US Letter at 96 dpi); every
# measurement below is that design value scaled by 72/96 into points.
MARGIN = 48.0
TOP = PAGE_HEIGHT - 46.5
BOTTOM = 48.0
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN
CONTENT_RIGHT = PAGE_WIDTH - MARGIN

# Table columns, left to right. They sum to CONTENT_WIDTH exactly.
COL_DETAIL = 225.0
COL_QTY = 33.0
COL_UNIT_NET = 76.5
COL_UNIT_GROSS = 67.5
COL_DISCOUNT = 34.5
COL_LINE_NET = 79.5

ROW_HEIGHT = 33.0
TABLE_HEADER_HEIGHT = 16.0

# The validity note and footer line always sit at the very bottom of the page.
FOOTER_ZONE = 40.0
# Terms, transfer details and the signature line, measured from their top rule.
CLOSING_BLOCK = 110.0
# What the last row must leave free below it: totals, closing block and footer.
CLOSING_HEIGHT = 236.0

LABEL_SIZE = 6.4
LABEL_TRACKING = 0.7
BODY_SIZE = 8.25
ROW_SIZE = 9.75
SMALL_SIZE = 7.9


@dataclass(frozen=True)
class _Row:
    """One printable table line, already priced."""

    name: str
    description: str
    quantity: int
    unit_net: str
    unit_gross: str
    discount: str
    line_net: str


def render_quote_pdf(document: QuoteDocument, totals: PricingSummary) -> None:
    pdf = canvas.Canvas(document.output_path, pagesize=LETTER)
    pdf.setTitle(f"{UI_STRINGS['quote_title']} N° {document.quote_number}")

    rows = [_price_row(item) for item in document.items]

    y = _draw_header(pdf, document)
    y = _draw_parties(pdf, document, y)
    y = _draw_table(pdf, document, rows, y)
    y = _draw_totals(pdf, totals, y)
    _draw_closing(pdf, document, y)

    pdf.save()


def _price_row(item) -> _Row:
    pricing = calculate_pricing(item.quantity, item.unit_price_with_tax, item.discount_percent)
    return _Row(
        name=ITEM_NAMES.get(item.name, item.name),
        description=item.description,
        quantity=item.quantity,
        unit_net=format_clp_decimal(pricing.unit_price_net_discounted),
        unit_gross=format_clp_int(pricing.unit_price_gross_discounted),
        discount="—" if item.discount_percent == 0.0 else f"{item.discount_percent * 100:g}%",
        line_net=format_clp_int(pricing.subtotal),
    )


def _draw_header(pdf: canvas.Canvas, document: QuoteDocument) -> float:
    fonts = brand_fonts()
    logo_width = 150.0
    logo_height = logo_width / 3.70  # the lockup's aspect ratio
    logo_top = TOP

    pdf.drawImage(
        document.logo_path,
        x=MARGIN,
        y=logo_top - logo_height,
        width=logo_width,
        height=logo_height,
        preserveAspectRatio=True,
        anchor="nw",
        mask="auto",
    )

    _label(pdf, UI_STRINGS["quote_title"], CONTENT_RIGHT, logo_top - 6, align="R")

    pdf.setFont(fonts.light, 39)
    pdf.setFillColor(ABAS_BLUE)
    pdf.drawRightString(CONTENT_RIGHT, logo_top - 43, document.quote_number)

    pdf.setFont(fonts.regular, BODY_SIZE)
    pdf.setFillColor(TEXT_GRAY)
    pdf.drawRightString(CONTENT_RIGHT, logo_top - 56, _format_date(document.issue_date))

    rule_y = logo_top - 72
    pdf.setStrokeColor(ABAS_BLUE)
    pdf.setLineWidth(1.5)
    pdf.line(MARGIN, rule_y, CONTENT_RIGHT, rule_y)

    return rule_y - 26


def _draw_parties(pdf: canvas.Canvas, document: QuoteDocument, top: float) -> float:
    issuer, client = document.issuer, document.client
    right_x = MARGIN + CONTENT_WIDTH / 2 + 18

    issuer_lines = [
        issuer.office_name,
        issuer.address,
        issuer.phone,
        issuer.email,
    ]
    client_lines = [line for line in (
        f"{UI_STRINGS['attention']} {client.contact_name}" if client.contact_name else "",
    ) if line]

    left_bottom = _party_block(
        pdf, MARGIN, top, UI_STRINGS["issuer"], issuer.company_name,
        issuer.tax_id, issuer_lines, MUTED,
    )
    right_bottom = _party_block(
        pdf, right_x, top, UI_STRINGS["to"], client.company_name,
        client.tax_id, client_lines, ORANGE,
    )
    return min(left_bottom, right_bottom) - 26


def _party_block(
    pdf: canvas.Canvas,
    x: float,
    top: float,
    label: str,
    name: str,
    tax_id: str,
    lines: list[str],
    label_color: Color,
) -> float:
    fonts = brand_fonts()
    column_width = CONTENT_WIDTH / 2 - 18
    _label(pdf, label, x, top, color=label_color)

    # A legal name wraps rather than truncating: cutting a company's registered
    # name short on a commercial document is not an acceptable failure mode.
    y = top - 15
    pdf.setFont(fonts.bold, 9.75)
    pdf.setFillColor(INK)
    for index, line in enumerate(_wrap(pdf, name, fonts.bold, 9.75, column_width)):
        if index:
            y -= 11
        pdf.drawString(x, y, line)

    y -= 11
    pdf.setFont(fonts.regular, BODY_SIZE)
    pdf.setFillColor(TEXT_GRAY)
    pdf.drawString(x, y, f"{UI_STRINGS['tax_id']} {tax_id}")

    pdf.setFillColor(MUTED)
    for line in lines:
        y -= 10.5
        pdf.drawString(x, y, _fit(pdf, line, fonts.regular, BODY_SIZE, column_width))
    return y


def _draw_table(
    pdf: canvas.Canvas,
    document: QuoteDocument,
    rows: list[_Row],
    top: float,
) -> float:
    y = _draw_table_header(pdf, top)

    for index, row in enumerate(rows):
        remaining = len(rows) - index
        # The closing blocks only have to fit under the last row, so reserve
        # their height only while this is the row that would end the table.
        floor = BOTTOM + (CLOSING_HEIGHT if remaining == 1 else 0)
        if y - ROW_HEIGHT < floor:
            pdf.showPage()
            y = _draw_table_header(pdf, _draw_continuation_header(pdf, document))
        y = _draw_row(pdf, row, y)

    return y - 20


def _draw_table_header(pdf: canvas.Canvas, top: float) -> float:
    columns = (
        (UI_STRINGS["table_item"], COL_DETAIL, "L"),
        (UI_STRINGS["table_qty"], COL_QTY, "C"),
        (UI_STRINGS["table_unit_net"], COL_UNIT_NET, "R"),
        (UI_STRINGS["table_unit_gross"], COL_UNIT_GROSS, "R"),
        (UI_STRINGS["table_discount"], COL_DISCOUNT, "C"),
        (UI_STRINGS["table_line_net"], COL_LINE_NET, "R"),
    )
    x = MARGIN
    for text, width, align in columns:
        _label(pdf, text, _anchor(x, width, align), top, align=align)
        x += width

    rule_y = top - TABLE_HEADER_HEIGHT + 9
    pdf.setStrokeColor(INK)
    pdf.setLineWidth(1.1)
    pdf.line(MARGIN, rule_y, CONTENT_RIGHT, rule_y)
    return rule_y


def _draw_continuation_header(pdf: canvas.Canvas, document: QuoteDocument) -> float:
    fonts = brand_fonts()
    pdf.setFont(fonts.bold, BODY_SIZE)
    pdf.setFillColor(ABAS_BLUE)
    pdf.drawString(MARGIN, TOP - 10, UI_STRINGS["continued"].format(number=document.quote_number))
    return TOP - 34


def _draw_row(pdf: canvas.Canvas, row: _Row, top: float) -> float:
    fonts = brand_fonts()
    baseline = top - 15

    pdf.setFont(fonts.bold, ROW_SIZE)
    pdf.setFillColor(INK)
    pdf.drawString(MARGIN, baseline, _fit(pdf, row.name, fonts.bold, ROW_SIZE, COL_DETAIL - 12))

    if row.description:
        pdf.setFont(fonts.regular, SMALL_SIZE)
        pdf.setFillColor(MUTED)
        pdf.drawString(
            MARGIN, baseline - 10,
            _fit(pdf, row.description, fonts.regular, SMALL_SIZE, COL_DETAIL - 12),
        )

    cells = (
        (str(row.quantity), COL_QTY, "C", fonts.regular, ROW_SIZE, TEXT_GRAY),
        (row.unit_net, COL_UNIT_NET, "R", fonts.bold, ROW_SIZE, INK),
        (row.unit_gross, COL_UNIT_GROSS, "R", fonts.regular, 9.0, MUTED),
        (row.discount, COL_DISCOUNT, "C", fonts.bold, 8.25, ORANGE),
        (row.line_net, COL_LINE_NET, "R", fonts.bold, ROW_SIZE, INK),
    )
    x = MARGIN + COL_DETAIL
    for text, width, align, font, size, color in cells:
        pdf.setFont(font, size)
        pdf.setFillColor(color)
        _aligned(pdf, text, _anchor(x, width, align), baseline, align)
        x += width

    bottom = top - ROW_HEIGHT
    pdf.setStrokeColor(LINE_SOFT)
    pdf.setLineWidth(0.6)
    pdf.line(MARGIN, bottom, CONTENT_RIGHT, bottom)
    return bottom


def _draw_totals(pdf: canvas.Canvas, totals: PricingSummary, top: float) -> float:
    fonts = brand_fonts()
    block_width = 211.5
    left = CONTENT_RIGHT - block_width
    y = top

    for label, value in (
        (UI_STRINGS["subtotal"], totals.subtotal),
        (UI_STRINGS["tax"], totals.tax),
    ):
        pdf.setFont(fonts.regular, BODY_SIZE)
        pdf.setFillColor(MUTED)
        pdf.drawString(left, y, label)
        pdf.setFont(fonts.regular, ROW_SIZE)
        pdf.setFillColor(TEXT_GRAY)
        pdf.drawRightString(CONTENT_RIGHT, y, f"$ {format_clp_int(value)}")
        y -= 15

    rule_y = y + 5
    pdf.setStrokeColor(LINE)
    pdf.setLineWidth(0.6)
    pdf.line(left, rule_y, CONTENT_RIGHT, rule_y)

    # Clear of the rule: at 20.25pt the digits rise ~14.5pt above the baseline,
    # so a smaller drop lets a seven-figure total cross the line above it.
    y -= 20
    _label(pdf, UI_STRINGS["total"], left, y + 4, color=INK)
    pdf.setFont(fonts.bold, 20.25)
    pdf.setFillColor(ORANGE)
    pdf.drawRightString(CONTENT_RIGHT, y, f"$ {format_clp_int(totals.total)}")

    return y - 30


def _draw_closing(pdf: canvas.Canvas, document: QuoteDocument, top: float) -> None:
    """Terms, transfer details and the signature line.

    These flow directly under the totals rather than being pinned to the foot:
    on a one-line quote, pinning them opens a hole in the middle of the page,
    which reads as a mistake. The clamp keeps them off the footer when the page
    is full.
    """
    fonts = brand_fonts()
    top = max(top, BOTTOM + FOOTER_ZONE + CLOSING_BLOCK)

    pdf.setStrokeColor(LINE)
    pdf.setLineWidth(0.6)
    pdf.line(MARGIN, top, CONTENT_RIGHT, top)

    column_width = (CONTENT_WIDTH - 2 * 22.5) / 3
    columns = (
        (UI_STRINGS["payment_terms"],
         [line.format(days=document.validity_days) for line in PAYMENT_TERMS]),
        (UI_STRINGS["transfer_details"], list(TRANSFER_DETAILS)),
    )

    x = MARGIN
    for label, lines in columns:
        _label(pdf, label, x, top - 17)
        y = top - 30
        pdf.setFont(fonts.regular, SMALL_SIZE)
        pdf.setFillColor(TEXT_GRAY)
        for line in lines:
            pdf.drawString(x, y, _fit(pdf, line, fonts.regular, SMALL_SIZE, column_width))
            y -= 10.5
        x += column_width + 22.5

    _label(pdf, UI_STRINGS["signature"], x, top - 17)
    signature_y = top - 62
    pdf.setStrokeColor(INK)
    pdf.setLineWidth(0.6)
    pdf.line(x, signature_y, x + column_width, signature_y)
    pdf.setFont(fonts.regular, 7.1)
    pdf.setFillColor(MUTED)
    pdf.drawString(x, signature_y - 10, UI_STRINGS["signature_caption"])

    pdf.setFont(fonts.regular, SMALL_SIZE)
    pdf.setFillColor(MUTED)
    pdf.drawString(
        MARGIN, BOTTOM + 18,
        UI_STRINGS["validity_note"].format(days=document.validity_days),
    )

    pdf.setFont(fonts.regular, 7.5)
    pdf.setFillColor(MUTED)
    pdf.drawString(MARGIN, BOTTOM, UI_STRINGS["footer_msg"])
    pdf.drawRightString(CONTENT_RIGHT, BOTTOM, UI_STRINGS["footer_legal"])


def _label(
    pdf: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    align: str = "L",
    color: Color = MUTED,
) -> None:
    """Small uppercase tracked label — the eyebrow used throughout the layout.

    Letter spacing only exists on a text object, and text objects have no
    aligned draw, so the start point is computed from the tracked width.
    """
    fonts = brand_fonts()
    text = text.upper()
    width = pdf.stringWidth(text, fonts.bold, LABEL_SIZE) + LABEL_TRACKING * max(len(text) - 1, 0)

    if align == "R":
        start = x - width
    elif align == "C":
        start = x - width / 2
    else:
        start = x

    label = pdf.beginText(start, y)
    label.setFont(fonts.bold, LABEL_SIZE)
    label.setFillColor(color)
    label.setCharSpace(LABEL_TRACKING)
    label.textOut(text)
    pdf.drawText(label)


def _anchor(x: float, width: float, align: str) -> float:
    if align == "R":
        return x + width
    if align == "C":
        return x + width / 2
    return x


def _aligned(pdf: canvas.Canvas, text: str, x: float, y: float, align: str) -> None:
    if align == "R":
        pdf.drawRightString(x, y, text)
    elif align == "C":
        pdf.drawCentredString(x, y, text)
    else:
        pdf.drawString(x, y, text)


def _format_date(value) -> str:
    months = (
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    )
    return f"{value.day} de {months[value.month - 1]} de {value.year}"


def _wrap(
    pdf: canvas.Canvas,
    text: str,
    font_name: str,
    font_size: float,
    max_width: float,
    max_lines: int = 2,
) -> list[str]:
    """Break text on word boundaries, eliding only once the line budget is spent."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and pdf.stringWidth(candidate, font_name, font_size) > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    lines.append(current)

    if len(lines) <= max_lines:
        return lines
    kept = lines[: max_lines - 1]
    kept.append(_fit(pdf, " ".join(lines[max_lines - 1:]), font_name, font_size, max_width))
    return kept


def _fit(pdf: canvas.Canvas, text: str, font_name: str, font_size: float, max_width: float) -> str:
    if pdf.stringWidth(text, font_name, font_size) <= max_width:
        return text
    while text and pdf.stringWidth(text + "…", font_name, font_size) > max_width:
        text = text[:-1]
    return text + "…"
