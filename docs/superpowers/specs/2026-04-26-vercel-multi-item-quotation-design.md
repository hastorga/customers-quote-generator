# Vercel Serverless — Cotización Multi-Ítem

**Fecha:** 2026-04-26
**Estado:** Aprobado

## Contexto

El generador de cotizaciones PDF (Python + ReportLab) existe como base de código con soporte para un solo ítem. Se necesita:

1. Refactorizar el modelo y el renderer para soportar múltiples líneas de producto.
2. Exponer la función como serverless en Vercel, invocada desde el frontend **Abastible-sales**.

El flujo está dividido en dos fases deliberadas:

- **Fase 1** — el frontend lee clientes y precios directamente desde Supabase (reads simples, sin lógica de negocio Python).
- **Fase 2** — al confirmar, el frontend envía solo IDs al serverless. Python resuelve precios vigentes, aplica descuentos, genera el número de cotización, construye el PDF y guarda el snapshot. El frontend recibe el blob y dispara la descarga.

Los precios se confirman en el momento de generación, no en el preview — comportamiento correcto para auditoría.

## Alcance de cambios

| Archivo | Cambio |
|---|---|
| `core/models.py` | `QuoteDocument.item: QuoteItem` → `items: list[QuoteItem]` |
| `services/pdf_service.py` | Reemplaza el bloque de un producto por `_draw_items_table()` usando `reportlab.platypus.Table`; totales al pie |
| `api/generate_quotation.py` | Loop sobre todos los `resolved`, pricing acumulado, CORS restringido a `https://abastible-sales.vercel.app` |
| `app.py` | Ajuste mínimo: empaqueta el ítem CLI en `items=[...]` al construir `QuoteDocument` |
| `vercel.json` | Agrega `maxDuration: 30` |

Sin archivos nuevos. Sin abstracciones adicionales.

## Contrato de la API

**Endpoint:** `POST /api/generate_quotation`

**Request body:**
```json
{
  "customer_id": "uuid",
  "contact_name": "Rodrigo Muñoz",
  "notes": "Despacho a Til-Til (opcional)",
  "items": [
    {
      "list_price_id": "uuid",
      "quantity": 10,
      "description": "Gas licuado 45 kg"
    }
  ]
}
```

**Response (200):**
- `Content-Type: application/pdf`
- `Content-Disposition: attachment; filename="cotizacion_042.pdf"`
- Body: bytes del PDF

**Response (error):**
```json
{ "error": "descripción del problema" }
```
Status 400 para inputs inválidos, 500 para fallos internos.

**Validaciones:**
- `items` no vacío → 400
- Cada ítem: `list_price_id` presente, `quantity > 0`, `description` no vacía → 400
- `resolve_items` sin precio vigente → 500 con mensaje descriptivo

**CORS:** `Access-Control-Allow-Origin: https://abastible-sales.vercel.app`

## Tabla PDF

Columnas (en orden):

| # | Cantidad | Descripción | Precio Unit. (neto) | Dto% | Total Línea |
|---|---|---|---|---|---|

- **#** — número de fila secuencial (1, 2, 3…)
- **Precio Unit. neto** = `round(unit_price_with_tax / 1.19)` — entero CLP, se formatea con `format_clp_int`
- **Total Línea** = `calculate_pricing(qty, unit_price_with_tax, discount).subtotal` — equivale a `round(precio_unit_neto × qty × (1 − dto/100))`; se reutiliza la función existente directamente
- **Subtotal** = suma de los `subtotal` de cada `calculate_pricing` call
- **IVA 19%** = `round(subtotal × 0.19)`
- **TOTAL** = Subtotal + IVA

La tabla se dibuja con `reportlab.platypus.Table` sobre el canvas existente (`table.wrapOn` + `table.drawOn`). Max ~10 ítems, caben en una página A4 — no se necesita paginación automática.

## Lógica de pricing

`calculate_pricing()` se llama una vez por ítem. Los `subtotal` se acumulan en el handler; IVA y total se calculan sobre el acumulado final. Sin cambio al módulo `utils/pricing.py`.

## Configuración Vercel

**`vercel.json`:**
```json
{
  "functions": {
    "api/*.py": {
      "runtime": "python3.11",
      "maxDuration": 30
    }
  }
}
```

**Variables de entorno** (Settings → Environment Variables en el dashboard):
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`

**Creación del proyecto:**
1. Importar repo GitHub en vercel.com
2. Framework preset: Other
3. Root directory: `/`
4. Build command: vacío
5. Install command: `pip install -r api/requirements.txt`
6. Agregar las dos env vars

## Decisiones descartadas

- **SimpleDocTemplate con flowables:** innecesario con max ~10 ítems en A4. El canvas existente más `Table.drawOn` es suficiente.
- **QuoteOrchestrator:** el handler ya es delgado y el flujo es lineal. Abstracción sin beneficio tangible ahora.
- **API key adicional:** CORS restringido al dominio es suficiente para esta etapa.
