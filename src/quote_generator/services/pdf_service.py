from __future__ import annotations

from dataclasses import dataclass

from reportlab.lib.colors import Color
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from quote_generator.core.constants import (
    ABAS_BLUE, COMMERCIAL_TERMS, INK, LINE, LINE_SOFT, MUTED, ORANGE,
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

# The design lets a row grow with its content, so a line carrying a description
# is taller than one that is only a name. A single fixed height cramped the
# description against the row rule below it.
ROW_HEIGHT = 36.55
ROW_HEIGHT_WITH_DESCRIPTION = 49.54
ROW_NAME_BASELINE = 21.11
ROW_DESCRIPTION_BASELINE = 34.76
TABLE_LABEL_BASELINE = 6.45
TABLE_HEADER_HEIGHT = 16.57

# Terms, transfer details, the signature line and the footer, measured from the
# block's top rule. The footer belongs to this group rather than being pinned to
# the page foot, where it read as orphaned under a short quote.
CLOSING_LABEL_BASELINE = 23.70
CLOSING_TEXT_BASELINE = 39.34
CLOSING_TEXT_STEP = 12.60
CLOSING_SIGNATURE_RULE = 55.20
CLOSING_CAPTION_BASELINE = 68.40
CLOSING_FOOTER_BASELINE = 102.50
CLOSING_BLOCK = 123.14

# Gap between major blocks (34px in the design).
SECTION_GAP = 25.5

# Header, right-hand column.
HEADER_LABEL_BASELINE = 6.45
HEADER_NUMBER_BASELINE = 43.05
HEADER_DATE_BASELINE = 63.09
HEADER_RULE = 91.50

# Issuer and client block, measured from the block top. The step from the tax id
# to the first address line is wider than the step between address lines: the
# design separates them as two groups, and collapsing both to one spacing was
# the most visible of the rhythm errors.
PARTY_NAME_BASELINE = 21.11
PARTY_TAX_ID_BASELINE = 35.89
PARTY_FIRST_LINE_BASELINE = 56.91
PARTY_LINE_STEP = 14.29
PARTY_DESCENT = 3.68

# Totals block.
TOTALS_WIDTH = 211.5
TOTALS_NET_BASELINE = 9.86
TOTALS_TAX_BASELINE = 29.91
TOTALS_RULE = 42.35
TOTALS_TOTAL_BASELINE = 73.32
TOTALS_HEIGHT = 80.47

# The logo is sized by height and its width follows the file's own aspect
# ratio, so swapping the asset cannot silently stretch it. The width cap keeps
# an unexpectedly wide file from running into the quote number.
LOGO_HEIGHT = 46.5
LOGO_MAX_WIDTH = 190.0

# Type sizes, all the design's px values scaled by 72/96.
LABEL_SIZE = 6.375          # 8.5px
LABEL_TRACKING = 0.7        # 0.11em
QUOTE_NUMBER_SIZE = 39.0    # 52px
QUOTE_NUMBER_TRACKING = -0.78   # -0.02em
BODY_SIZE = 8.25            # 11px
NAME_SIZE = 9.75            # 13px
ROW_SIZE = 9.75             # 13px
GROSS_SIZE = 9.0            # 12px
DISCOUNT_SIZE = 8.25        # 11px
SMALL_SIZE = 7.875          # 10.5px
TOTALS_LABEL_SIZE = 8.625   # 11.5px
TOTAL_LABEL_SIZE = 7.5      # 10px
TOTAL_LABEL_TRACKING = 0.9  # 0.12em
TOTAL_VALUE_SIZE = 20.25    # 27px
CAPTION_SIZE = 7.125        # 9.5px
FOOTER_SIZE = 7.5           # 10px


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

    # Rows fill the page, and it is the closing group that moves when it no
    # longer fits. Reserving its height under the last row instead pushed a
    # single row onto the next page and left most of this one blank.
    if y - TOTALS_HEIGHT - SECTION_GAP - CLOSING_BLOCK < BOTTOM:
        pdf.showPage()
        y = _draw_continuation_header(pdf, document)

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
    logo_top = TOP
    logo_width, logo_height = _logo_size(document.logo_path)

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

    _label(pdf, UI_STRINGS["quote_title"], CONTENT_RIGHT, logo_top - HEADER_LABEL_BASELINE, align="R")

    _tracked(
        pdf, document.quote_number, CONTENT_RIGHT, logo_top - HEADER_NUMBER_BASELINE,
        fonts.light, QUOTE_NUMBER_SIZE, ABAS_BLUE, QUOTE_NUMBER_TRACKING, align="R",
    )

    pdf.setFont(fonts.regular, BODY_SIZE)
    pdf.setFillColor(TEXT_GRAY)
    pdf.drawRightString(
        CONTENT_RIGHT, logo_top - HEADER_DATE_BASELINE, _format_date(document.issue_date)
    )

    rule_y = logo_top - HEADER_RULE
    pdf.setStrokeColor(ABAS_BLUE)
    pdf.setLineWidth(1.5)
    pdf.line(MARGIN, rule_y, CONTENT_RIGHT, rule_y)

    return rule_y - SECTION_GAP


def _logo_size(path: str) -> tuple[float, float]:
    """Logo box at LOGO_HEIGHT, keeping the file's aspect ratio and the width cap."""
    width_px, height_px = ImageReader(path).getSize()
    ratio = width_px / height_px
    height = LOGO_HEIGHT
    width = height * ratio
    if width > LOGO_MAX_WIDTH:
        width = LOGO_MAX_WIDTH
        height = width / ratio
    return width, height


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
    return min(left_bottom, right_bottom) - SECTION_GAP


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
    y = top - PARTY_NAME_BASELINE
    pdf.setFont(fonts.bold, NAME_SIZE)
    pdf.setFillColor(INK)
    wrapped = _wrap(pdf, name, fonts.bold, NAME_SIZE, column_width)
    for index, line in enumerate(wrapped):
        if index:
            y -= PARTY_LINE_STEP
        pdf.drawString(x, y, line)

    extra = (len(wrapped) - 1) * PARTY_LINE_STEP
    y = top - PARTY_TAX_ID_BASELINE - extra
    pdf.setFont(fonts.regular, BODY_SIZE)
    pdf.setFillColor(TEXT_GRAY)
    pdf.drawString(x, y, f"{UI_STRINGS['tax_id']} {tax_id}")

    pdf.setFillColor(MUTED)
    y = top - PARTY_FIRST_LINE_BASELINE - extra
    for index, line in enumerate(lines):
        pdf.drawString(x, y - index * PARTY_LINE_STEP, _fit(pdf, line, fonts.regular, BODY_SIZE, column_width))
    if lines:
        y -= (len(lines) - 1) * PARTY_LINE_STEP
    return y - PARTY_DESCENT


def _draw_table(
    pdf: canvas.Canvas,
    document: QuoteDocument,
    rows: list[_Row],
    top: float,
) -> float:
    y = _draw_table_header(pdf, top)

    for row in rows:
        if y - _row_height(row) < BOTTOM:
            pdf.showPage()
            y = _draw_table_header(pdf, _draw_continuation_header(pdf, document))
        y = _draw_row(pdf, row, y)

    return y - SECTION_GAP


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
        _label(pdf, text, _anchor(x, width, align), top - TABLE_LABEL_BASELINE, align=align)
        x += width

    rule_y = top - TABLE_HEADER_HEIGHT
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


def _row_height(row: _Row) -> float:
    return ROW_HEIGHT_WITH_DESCRIPTION if row.description else ROW_HEIGHT


def _draw_row(pdf: canvas.Canvas, row: _Row, top: float) -> float:
    fonts = brand_fonts()
    baseline = top - ROW_NAME_BASELINE

    pdf.setFont(fonts.semibold, ROW_SIZE)
    pdf.setFillColor(INK)
    pdf.drawString(MARGIN, baseline, _fit(pdf, row.name, fonts.semibold, ROW_SIZE, COL_DETAIL - 12))

    if row.description:
        pdf.setFont(fonts.regular, SMALL_SIZE)
        pdf.setFillColor(MUTED)
        pdf.drawString(
            MARGIN, top - ROW_DESCRIPTION_BASELINE,
            _fit(pdf, row.description, fonts.regular, SMALL_SIZE, COL_DETAIL - 12),
        )

    cells = (
        (str(row.quantity), COL_QTY, "C", fonts.regular, ROW_SIZE, TEXT_GRAY),
        (row.unit_net, COL_UNIT_NET, "R", fonts.semibold, ROW_SIZE, INK),
        (row.unit_gross, COL_UNIT_GROSS, "R", fonts.regular, GROSS_SIZE, MUTED),
        (row.discount, COL_DISCOUNT, "C", fonts.bold, DISCOUNT_SIZE, ORANGE),
        (row.line_net, COL_LINE_NET, "R", fonts.bold, ROW_SIZE, INK),
    )
    x = MARGIN + COL_DETAIL
    for text, width, align, font, size, color in cells:
        pdf.setFont(font, size)
        pdf.setFillColor(color)
        _aligned(pdf, text, _anchor(x, width, align), baseline, align)
        x += width

    bottom = top - _row_height(row)
    pdf.setStrokeColor(LINE_SOFT)
    pdf.setLineWidth(0.6)
    pdf.line(MARGIN, bottom, CONTENT_RIGHT, bottom)
    return bottom


def _draw_totals(pdf: canvas.Canvas, totals: PricingSummary, top: float) -> float:
    fonts = brand_fonts()
    left = CONTENT_RIGHT - TOTALS_WIDTH

    for offset, label, value in (
        (TOTALS_NET_BASELINE, UI_STRINGS["subtotal"], totals.subtotal),
        (TOTALS_TAX_BASELINE, UI_STRINGS["tax"], totals.tax),
    ):
        y = top - offset
        pdf.setFont(fonts.regular, TOTALS_LABEL_SIZE)
        pdf.setFillColor(MUTED)
        pdf.drawString(left, y, label)
        pdf.setFont(fonts.regular, ROW_SIZE)
        pdf.setFillColor(TEXT_GRAY)
        pdf.drawRightString(CONTENT_RIGHT, y, f"$ {format_clp_int(value)}")

    rule_y = top - TOTALS_RULE
    pdf.setStrokeColor(LINE)
    pdf.setLineWidth(0.6)
    pdf.line(left, rule_y, CONTENT_RIGHT, rule_y)

    total_y = top - TOTALS_TOTAL_BASELINE
    _tracked(
        pdf, UI_STRINGS["total"], left, total_y, fonts.extrabold,
        TOTAL_LABEL_SIZE, INK, TOTAL_LABEL_TRACKING,
    )
    pdf.setFont(fonts.extrabold, TOTAL_VALUE_SIZE)
    pdf.setFillColor(ORANGE)
    pdf.drawRightString(CONTENT_RIGHT, total_y, f"$ {format_clp_int(totals.total)}")

    return top - TOTALS_HEIGHT - SECTION_GAP


def _draw_closing(pdf: canvas.Canvas, document: QuoteDocument, top: float) -> None:
    """Terms, transfer details and the signature line.

    These flow directly under the totals rather than being pinned to the foot:
    on a one-line quote, pinning them opens a hole in the middle of the page,
    which reads as a mistake. The clamp keeps them off the footer when the page
    is full.
    """
    fonts = brand_fonts()
    top = max(top, BOTTOM + CLOSING_BLOCK)

    pdf.setStrokeColor(LINE)
    pdf.setLineWidth(0.6)
    pdf.line(MARGIN, top, CONTENT_RIGHT, top)

    column_width = (CONTENT_WIDTH - 2 * 22.5) / 3
    columns = (
        (UI_STRINGS["commercial_terms"],
         [line.format(days=document.validity_days) for line in COMMERCIAL_TERMS]),
        (UI_STRINGS["transfer_details"], list(TRANSFER_DETAILS)),
    )

    x = MARGIN
    for label, lines in columns:
        _label(pdf, label, x, top - CLOSING_LABEL_BASELINE)
        pdf.setFont(fonts.regular, SMALL_SIZE)
        pdf.setFillColor(TEXT_GRAY)
        for index, line in enumerate(lines):
            pdf.drawString(
                x, top - CLOSING_TEXT_BASELINE - index * CLOSING_TEXT_STEP,
                _fit(pdf, line, fonts.regular, SMALL_SIZE, column_width),
            )
        x += column_width + 22.5

    _label(pdf, UI_STRINGS["signature"], x, top - CLOSING_LABEL_BASELINE)
    signature_y = top - CLOSING_SIGNATURE_RULE
    pdf.setStrokeColor(INK)
    pdf.setLineWidth(0.6)
    pdf.line(x, signature_y, x + column_width, signature_y)
    pdf.setFont(fonts.regular, CAPTION_SIZE)
    pdf.setFillColor(MUTED)
    pdf.drawString(x, top - CLOSING_CAPTION_BASELINE, UI_STRINGS["signature_caption"])

    # The validity window is already stated in the commercial terms column, so
    # the separate note the old template printed would only repeat it.
    footer_y = top - CLOSING_FOOTER_BASELINE
    pdf.setFont(fonts.regular, FOOTER_SIZE)
    pdf.setFillColor(MUTED)
    pdf.drawString(MARGIN, footer_y, UI_STRINGS["footer_msg"])
    pdf.drawRightString(CONTENT_RIGHT, footer_y, UI_STRINGS["footer_legal"])


def _label(
    pdf: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    align: str = "L",
    color: Color = MUTED,
) -> None:
    """Small uppercase tracked label — the eyebrow used throughout the layout."""
    _tracked(
        pdf, text.upper(), x, y, brand_fonts().bold, LABEL_SIZE, color,
        LABEL_TRACKING, align=align,
    )


def _tracked(
    pdf: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    font_name: str,
    font_size: float,
    color: Color,
    tracking: float,
    align: str = "L",
) -> None:
    """Draw letter-spaced text. Spacing only exists on a text object, and text
    objects have no aligned draw, so the start point is computed from the
    tracked width."""
    width = pdf.stringWidth(text, font_name, font_size) + tracking * max(len(text) - 1, 0)

    if align == "R":
        start = x - width
    elif align == "C":
        start = x - width / 2
    else:
        start = x

    obj = pdf.beginText(start, y)
    obj.setFont(font_name, font_size)
    obj.setFillColor(color)
    obj.setCharSpace(tracking)
    obj.textOut(text)
    # Tc is graphics state, not text-object state: it survives ET and would
    # apply to every later drawString on the page. Reset it inside this object.
    obj.setCharSpace(0)
    pdf.drawText(obj)


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
