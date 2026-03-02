from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas

from quote_generator.formatting import format_clp_decimal, format_clp_int
from quote_generator.models import QuoteDocument
from quote_generator.pricing import PricingSummary

PAGE_WIDTH, PAGE_HEIGHT = LETTER
MARGIN_LEFT = 2 * cm
MARGIN_RIGHT = 2 * cm

ORANGE = colors.HexColor("#F47920")
ABAS_BLUE = colors.HexColor("#1A3B8A")
DARK_GRAY = colors.HexColor("#3D3D3D")
LIGHT_GRAY = colors.HexColor("#F5F5F5")
MID_GRAY = colors.HexColor("#D0D0D0")
TEXT_GRAY = colors.HexColor("#555555")
WHITE = colors.white


def render_quote_pdf(document: QuoteDocument, pricing: PricingSummary) -> None:
    pdf = canvas.Canvas(document.output_path, pagesize=LETTER)

    context = _draw_header(pdf, document)
    table_context = _draw_product_table(pdf, document, pricing, context["content_top"])
    totals_bottom = _draw_totals(pdf, pricing, table_context)
    _draw_validity_note(pdf, document.validity_days, totals_bottom)
    _draw_footer(pdf)

    pdf.save()


def _draw_header(pdf: canvas.Canvas, document: QuoteDocument) -> dict[str, float]:
    bar_height = 10 * mm
    header_bottom = PAGE_HEIGHT - 46 * mm

    pdf.setFillColor(ORANGE)
    pdf.rect(0, PAGE_HEIGHT - bar_height, PAGE_WIDTH, bar_height, fill=1, stroke=0)

    pdf.drawImage(
        document.logo_path,
        x=MARGIN_LEFT,
        y=header_bottom + 4 * mm,
        width=50 * mm,
        height=28 * mm,
        preserveAspectRatio=True,
        mask="auto",
    )

    pdf.setFont("Helvetica-Bold", 22)
    pdf.setFillColor(DARK_GRAY)
    pdf.drawRightString(PAGE_WIDTH - MARGIN_RIGHT, header_bottom + 18 * mm, f"QUOTE # {document.quote_number}")

    pdf.setStrokeColor(ORANGE)
    pdf.setLineWidth(2.5)
    line_end = PAGE_WIDTH - MARGIN_RIGHT
    pdf.line(line_end - 9.5 * cm, header_bottom + 14 * mm, line_end, header_bottom + 14 * mm)

    separator_y = header_bottom - 2 * mm
    pdf.setStrokeColor(MID_GRAY)
    pdf.setLineWidth(0.5)
    pdf.line(MARGIN_LEFT, separator_y, PAGE_WIDTH - MARGIN_RIGHT, separator_y)

    issuer_bottom = _draw_issuer_block(pdf, document, separator_y)
    client_bottom = _draw_client_block(pdf, document, separator_y)

    return {"content_top": min(issuer_bottom, client_bottom) - 8 * mm}


def _draw_issuer_block(pdf: canvas.Canvas, document: QuoteDocument, separator_y: float) -> float:
    top_y = separator_y - 5 * mm
    issuer = document.issuer

    pdf.setFont("Helvetica-Bold", 9)
    pdf.setFillColor(ABAS_BLUE)
    pdf.drawString(MARGIN_LEFT, top_y, issuer.company_name)

    lines = [
        f"Tax ID: {issuer.tax_id}",
        issuer.office_name,
        issuer.address,
        issuer.phone,
        issuer.email,
    ]
    pdf.setFont("Helvetica", 7.5)
    pdf.setFillColor(TEXT_GRAY)

    line_gap = 5.5 * mm
    for idx, line in enumerate(lines):
        pdf.drawString(MARGIN_LEFT, top_y - (idx + 1) * line_gap, line)

    return top_y - len(lines) * line_gap


def _draw_client_block(pdf: canvas.Canvas, document: QuoteDocument, separator_y: float) -> float:
    rows = [
        ("TO:", document.client.contact_name),
        ("COMPANY:", document.client.company_name),
        ("TAX ID:", document.client.tax_id),
        ("ADDRESS:", document.client.address),
        ("CITY:", document.client.city),
    ]

    row_height = 5.8 * mm
    date_height = 7 * mm
    padding = 3 * mm
    box_height = date_height + len(rows) * row_height + padding * 2

    box_x = PAGE_WIDTH / 2 + 5 * mm
    box_width = PAGE_WIDTH - MARGIN_RIGHT - box_x
    box_y = separator_y - box_height - 3 * mm

    pdf.setFillColor(LIGHT_GRAY)
    pdf.roundRect(box_x, box_y, box_width, box_height, 4, fill=1, stroke=0)

    pdf.setFillColor(ORANGE)
    pdf.rect(box_x, box_y, 3.5, box_height, fill=1, stroke=0)

    inner_x = box_x + 8
    label_width = 23 * mm
    value_x = inner_x + label_width

    date_y = box_y + box_height - padding - date_height / 2 - 1
    pdf.setFont("Helvetica-Bold", 7.5)
    pdf.setFillColor(TEXT_GRAY)
    pdf.drawString(inner_x, date_y, "Date:")

    pdf.setFont("Helvetica", 7.5)
    pdf.setFillColor(DARK_GRAY)
    pdf.drawString(value_x, date_y, document.issue_date.strftime("%d/%m/%Y"))

    divider_y = box_y + box_height - padding - date_height
    pdf.setStrokeColor(MID_GRAY)
    pdf.setLineWidth(0.4)
    pdf.line(inner_x, divider_y, box_x + box_width - 4, divider_y)

    for idx, (label, value) in enumerate(rows):
        row_y = divider_y - (idx + 0.7) * row_height
        pdf.setFont("Helvetica-Bold", 7.5)
        pdf.setFillColor(TEXT_GRAY)
        pdf.drawString(inner_x, row_y, label)
        pdf.setFillColor(DARK_GRAY)
        pdf.drawString(value_x, row_y, value)

    return box_y


def _draw_product_table(
    pdf: canvas.Canvas,
    document: QuoteDocument,
    pricing: PricingSummary,
    table_top: float,
) -> dict[str, float]:
    column_widths = [135, 38, 120, 82, 65, 58]
    table_x = MARGIN_LEFT
    table_width = sum(column_widths)
    row_height = 9 * mm

    headers = ["Item", "Qty", "Description", "Unit Price", "Discount (%)", "Line Total"]
    alignments = ["L", "C", "L", "R", "C", "R"]

    pdf.setFillColor(ABAS_BLUE)
    pdf.rect(table_x, table_top - row_height, table_width, row_height, fill=1, stroke=0)

    pdf.setFont("Helvetica-Bold", 7.5)
    pdf.setFillColor(WHITE)
    current_x = table_x
    for label, alignment, width in zip(headers, alignments, column_widths):
        _draw_aligned_text(pdf, label, alignment, current_x, table_top - row_height + 3 * mm, width)
        current_x += width

    data_y = table_top - 2 * row_height
    pdf.setFillColor(WHITE)
    pdf.rect(table_x, data_y, table_width, row_height, fill=1, stroke=0)
    pdf.setStrokeColor(MID_GRAY)
    pdf.setLineWidth(0.5)
    pdf.rect(table_x, data_y, table_width, row_height, fill=0, stroke=1)

    row_values = [
        document.item.name,
        str(document.item.quantity),
        document.item.description,
        format_clp_decimal(pricing.unit_price_net),
        f"{document.item.discount_percent}%",
        format_clp_decimal(pricing.unit_price_discounted),
    ]

    pdf.setFont("Helvetica", 8)
    pdf.setFillColor(DARK_GRAY)
    current_x = table_x
    for value, alignment, width in zip(row_values, alignments, column_widths):
        _draw_aligned_text(pdf, value, alignment, current_x, data_y + 3 * mm, width)
        current_x += width

    pdf.setStrokeColor(colors.HexColor("#BBBBBB"))
    pdf.setLineWidth(0.3)
    separator_x = table_x
    for width in column_widths[:-1]:
        separator_x += width
        pdf.line(separator_x, table_top, separator_x, data_y)

    return {
        "table_x": table_x,
        "table_width": table_width,
        "data_y": data_y,
        "column_widths": column_widths,
    }


def _draw_totals(pdf: canvas.Canvas, pricing: PricingSummary, table_context: dict[str, float]) -> float:
    table_x = table_context["table_x"]
    table_width = table_context["table_width"]
    data_y = table_context["data_y"]
    column_widths = table_context["column_widths"]

    totals_width = column_widths[-2] + column_widths[-1]
    totals_x = table_x + table_width - totals_width
    totals_right = table_x + table_width

    row_height = 8 * mm
    top_y = data_y - 2 * mm

    rows = [
        ("Subtotal", format_clp_int(pricing.subtotal), False),
        ("Tax 19%", format_clp_int(pricing.tax), False),
        ("TOTAL", format_clp_int(pricing.total), True),
    ]

    for idx, (label, value, highlight) in enumerate(rows):
        y = top_y - idx * row_height
        rect_y = y - row_height + 2
        if highlight:
            pdf.setFillColor(ORANGE)
            pdf.rect(totals_x, rect_y, totals_width, row_height - 2, fill=1, stroke=0)
            pdf.setFont("Helvetica-Bold", 9)
            pdf.setFillColor(WHITE)
        else:
            pdf.setFillColor(LIGHT_GRAY)
            pdf.rect(totals_x, rect_y, totals_width, row_height - 2, fill=1, stroke=0)
            pdf.setStrokeColor(MID_GRAY)
            pdf.setLineWidth(0.4)
            pdf.rect(totals_x, rect_y, totals_width, row_height - 2, fill=0, stroke=1)
            pdf.setFont("Helvetica-Bold", 8.5)
            pdf.setFillColor(TEXT_GRAY)

        pdf.drawString(totals_x + 5, rect_y + 2.5 * mm, label)
        pdf.setFillColor(WHITE if highlight else DARK_GRAY)
        pdf.setFont("Helvetica-Bold" if highlight else "Helvetica", 9 if highlight else 8.5)
        pdf.drawRightString(totals_right - 4, rect_y + 2.5 * mm, f"$ {value}")

    return top_y - len(rows) * row_height


def _draw_validity_note(pdf: canvas.Canvas, validity_days: int, totals_bottom: float) -> None:
    pdf.setFont("Helvetica-Oblique", 7.5)
    pdf.setFillColor(colors.HexColor("#999999"))
    pdf.drawString(
        MARGIN_LEFT,
        totals_bottom - 8 * mm,
        f"This quote is valid for up to {validity_days} calendar days from the issue date.",
    )


def _draw_footer(pdf: canvas.Canvas) -> None:
    footer_height = 18 * mm
    pdf.setFillColor(DARK_GRAY)
    pdf.rect(0, 0, PAGE_WIDTH, footer_height, fill=1, stroke=0)
    pdf.setFillColor(ORANGE)
    pdf.rect(0, footer_height, PAGE_WIDTH, 2.5, fill=1, stroke=0)

    pdf.setFont("Helvetica-Bold", 8.5)
    pdf.setFillColor(WHITE)
    pdf.drawCentredString(PAGE_WIDTH / 2, footer_height - 6 * mm, "Thank you for your request.")


def _draw_aligned_text(
    pdf: canvas.Canvas,
    text: str,
    alignment: str,
    x: float,
    y: float,
    width: float,
) -> None:
    if alignment == "R":
        pdf.drawRightString(x + width - 4, y, text)
    elif alignment == "C":
        pdf.drawCentredString(x + width / 2, y, text)
    else:
        pdf.drawString(x + 4, y, text)
