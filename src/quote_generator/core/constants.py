import os

from dotenv import load_dotenv
from reportlab.lib import colors

from quote_generator.core.models import IssuerInfo

# Makes a local .env work the way the deployed environment already does, where
# Vercel injects these directly. Existing environment variables win.
load_dotenv()


def _lines_from_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    """Read a block of printed lines from the environment, one line per entry.

    Falls back to the bracketed placeholders rather than to nothing: an
    unconfigured deploy should print something visibly wrong on the quote, not
    silently drop the seller's bank details.
    """
    raw = os.environ.get(name, "")
    lines = tuple(line.strip() for line in raw.splitlines() if line.strip())
    return lines or default

# Brand colors, sampled from the official logo files in assets/. Do not eyeball
# these: #011689 and #FC4F00 are the exact values the lockup is drawn in.
ABAS_BLUE = colors.HexColor("#011689")
ORANGE = colors.HexColor("#FC4F00")

# Neutrals. Cool-toned so they sit with the blue; INK is deliberately not pure
# black, which prints harsh.
INK = colors.HexColor("#141A2E")
TEXT_GRAY = colors.HexColor("#5A6178")
MUTED = colors.HexColor("#9AA0B4")
LINE = colors.HexColor("#DDE1EC")
LINE_SOFT = colors.HexColor("#EDEFF5")

# Issuer Information (from Abastible S.A.)
DEFAULT_ISSUER = IssuerInfo(
    company_name="ABASTIBLE S.A.",
    tax_id="91.806.000-6",
    office_name="Consignación Abastible Llay Llay",
    address="Balmaceda 473, Llay Llay, Valparaíso",
    phone="34 2611498 - 34 2612637 | +56 9 3006 7765",
    email="hector.astorga_externos@abastible.cl",
)

# PDF Layout Defaults
VALIDITY_DAYS = 10
TAX_RATE = 0.19

# Commercial blocks printed under the totals.
COMMERCIAL_TERMS: tuple[str, ...] = (
    "Precios en CLP con descuento aplicado.",
    "Validez: {days} días calendario.",
)
# Kept out of the source tree: this repository is public, and git history
# outlives any later edit. Set QUOTE_TRANSFER_DETAILS in .env and in Vercel.
TRANSFER_DETAILS: tuple[str, ...] = _lines_from_env(
    "QUOTE_TRANSFER_DETAILS",
    default=(
        "[TITULAR] · [RUT]",
        "[BANCO] · Cta. [N° DE CUENTA]",
        "[CORREO DE CONFIRMACIÓN]",
    ),
)

ITEM_NAMES: dict[str, str] = {
    "GAS05N": "Recarga 5 kilos",
    "GAS11N": "Recarga 11 kilos",
    "GAS15N": "Recarga 15 kilos",
    "GAS45N": "Recarga 45 kilos",
    "GAS15VMA": "Recarga VM Aluminio",
}

# UI / Spanish Translations for PDF
UI_STRINGS = {
    "quote_title": "Cotización",
    "continued": "Cotización N° {number} · continuación",
    "tax_id": "RUT",
    "issuer": "De",
    "to": "Para",
    "attention": "At.",
    "natural_person": "NOMBRE:",
    "company": "EMPRESA:",
    "address": "DIRECCIÓN:",
    "city": "CIUDAD:",
    "date": "Fecha:",
    "table_item": "Detalle",
    "table_qty": "Cant.",
    "table_unit_net": "P. unit. neto",
    "table_unit_gross": "P. unit. c/IVA",
    "table_discount": "Dcto.",
    "table_line_net": "Total neto",
    "subtotal": "Neto",
    "tax": "IVA 19%",
    "total": "TOTAL",
    "commercial_terms": "Condiciones comerciales",
    "transfer_details": "Datos de transferencia",
    "signature": "Acepta y firma",
    "signature_caption": "Nombre, RUT y fecha",
    "validity_note": "Esta cotización es válida por hasta {days} días calendario desde la fecha de emisión.",
    "footer_msg": "Gracias por su solicitud.",
    "footer_legal": "Abastible S.A. · Consignación Llay Llay · abastible.cl",
}
