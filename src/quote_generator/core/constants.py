from reportlab.lib import colors

from quote_generator.core.models import IssuerInfo

# Colors
ORANGE = colors.HexColor("#F47920")
ABAS_BLUE = colors.HexColor("#1A3B8A")
DARK_GRAY = colors.HexColor("#3D3D3D")
LIGHT_GRAY = colors.HexColor("#F5F5F5")
MID_GRAY = colors.HexColor("#D0D0D0")
TEXT_GRAY = colors.HexColor("#555555")
WHITE = colors.white

# Issuer Information (from Abastible S.A.)
DEFAULT_ISSUER = IssuerInfo(
    company_name="ABASTIBLE S.A.",
    tax_id="91.806.000-6",
    office_name="Consignacion Abastible Llay Llay",
    address="Balmaceda 473, Llay Llay, Valparaiso",
    phone="34 2611498 - 34 2612637 | +56 9 3006 7765",
    email="hector.astorga_externos@abastible.cl",
)

# PDF Layout Defaults
VALIDITY_DAYS = 10
TAX_RATE = 0.19

# UI / Spanish Translations for PDF
UI_STRINGS = {
    "quote_title": "COTIZACIÓN #",
    "tax_id": "RUT:",
    "to": "SEÑOR(ES):",
    "company": "EMPRESA:",
    "address": "DIRECCIÓN:",
    "city": "CIUDAD:",
    "date": "Fecha:",
    "table_item": "Ítem",
    "table_qty": "Cant.",
    "table_desc": "Descripción",
    "table_unit_price": "Precio Unit.",
    "table_discount": "Desc. (%)",
    "table_total": "Total Línea",
    "subtotal": "Subtotal",
    "tax": "IVA 19%",
    "total": "TOTAL",
    "validity_note": "Esta cotización es válida por hasta {days} días calendario desde la fecha de emisión.",
    "footer_msg": "Gracias por su solicitud.",
}
