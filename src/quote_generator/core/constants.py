from reportlab.lib import colors

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover
    # Reading .env is a local-development convenience; the deployed function
    # gets its configuration injected by the platform. Missing the package must
    # never be able to take the service down at import time, as it once did.
    def load_dotenv() -> None:
        return None


# Makes a local .env work the way the deployed environment already does, where
# Vercel injects these directly. Existing environment variables win.
load_dotenv()


def split_print_lines(raw: str | None) -> tuple[str, ...]:
    """Split a stored block of printed lines into its lines.

    Accepts "|" as well as real newlines: a multi-line value survives poorly
    through a dashboard field or a CLI, while a single line split on "|" is
    verifiable and safe to edit anywhere. Blank lines are dropped.
    """
    text = (raw or "").replace("|", "\n")
    return tuple(line.strip() for line in text.splitlines() if line.strip())

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

# The only issuer facts that hold from any branch: the company behind every
# consignment office. The office's own name, address, phone and email are
# per-branch and live on the `branches` row (see fetch_issuer); there is
# deliberately no default for them. A constant here would be one branch's
# letterhead printed on another branch's quote — a document that looks entirely
# correct in a customer's hands and sends the reply to the wrong inbox.
COMPANY_NAME = "ABASTIBLE S.A."
COMPANY_TAX_ID = "91.806.000-6"

# PDF Layout Defaults
VALIDITY_DAYS = 10
TAX_RATE = 0.19

# Commercial blocks printed under the totals.
COMMERCIAL_TERMS: tuple[str, ...] = (
    "Precios en CLP con descuento aplicado.",
    "Validez: {days} días calendario.",
)
# Shown when a branch has no transfer details on file. Deliberately visible on
# the page: a quote that silently dropped the block, or borrowed another
# branch's account, would send the customer's payment to the wrong place. The
# real details live on the `branches` row (transfer_details) — this repository
# is public, so they are never committed.
TRANSFER_DETAILS_PLACEHOLDER: tuple[str, ...] = (
    "[TITULAR] · [RUT]",
    "[BANCO] · Cta. [N° DE CUENTA]",
    "[CORREO DE CONFIRMACIÓN]",
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
    "notes": "Notas",
    "commercial_terms": "Condiciones comerciales",
    "transfer_details": "Datos de transferencia",
    "signature": "Acepta y firma",
    "signature_caption": "Nombre, RUT y fecha",
    "footer_msg": "Gracias por su solicitud.",
    # Fallback when the branch has no footer_legal of its own. The stored value
    # wins verbatim when there is one; this keeps the line attributable either way.
    # Title case here, not COMPANY_NAME: the footer is set small and the all-caps
    # form the header uses reads as shouting at that size.
    "footer_legal": "Abastible S.A. · {office_name} · abastible.cl",
}
