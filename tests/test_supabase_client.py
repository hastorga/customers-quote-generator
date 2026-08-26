from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from quote_generator.core.constants import COMPANY_NAME, COMPANY_TAX_ID
from quote_generator.supabase_client import (
    CustomerData,
    CylinderData,
    ResolvedItem,
    fetch_customer,
    fetch_cylinder,
    fetch_issuer,
    resolve_items,
    save_quotation,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(data: object) -> MagicMock:
    """Build a minimal APIResponse-like mock."""
    resp = MagicMock()
    resp.data = data
    return resp


def _mock_chain(final_response: MagicMock) -> MagicMock:
    """Return a builder mock where every chained call returns itself
    and .execute() returns *final_response*."""
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.lte.return_value = chain
    chain.or_.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.single.return_value = chain
    chain.insert.return_value = chain
    chain.execute.return_value = final_response
    return chain


# ---------------------------------------------------------------------------
# fetch_customer
# ---------------------------------------------------------------------------

class TestFetchCustomer:
    def test_maps_row_to_customer_data(self):
        row_data = {"name": "Ingredion Chile S.A.", "rut": "96.845.100-6"}
        mock_client = MagicMock()
        mock_client.table.return_value = _mock_chain(_make_response(row_data))

        with patch("quote_generator.supabase_client._get_client", return_value=mock_client):
            result = fetch_customer("uuid-123")

        assert isinstance(result, CustomerData)
        assert result.name == "Ingredion Chile S.A."
        assert result.rut == "96.845.100-6"

    def test_queries_correct_table_and_id(self):
        row_data = {"name": "X", "rut": "1-9"}
        mock_client = MagicMock()
        chain = _mock_chain(_make_response(row_data))
        mock_client.table.return_value = chain

        with patch("quote_generator.supabase_client._get_client", return_value=mock_client):
            fetch_customer("my-uuid")

        mock_client.table.assert_called_once_with("customers")
        chain.select.assert_called_once_with("name, rut")
        chain.eq.assert_called_once_with("id", "my-uuid")


# ---------------------------------------------------------------------------
# fetch_issuer
# ---------------------------------------------------------------------------

class TestFetchIssuer:
    _COMPLETE = {
        "name": "Llay Llay",
        "office_name": "Consignación Abastible Llay Llay",
        "address": "Balmaceda 473, Llay Llay, Valparaíso",
        "phone": "34 2611498",
        "email": "contacto@abastible.cl",
        "footer_legal": "Abastible S.A. · Consignación Llay Llay · abastible.cl",
    }

    def _client_returning(self, rows: list) -> MagicMock:
        mock_client = MagicMock()
        mock_client.table.return_value = _mock_chain(_make_response(rows))
        return mock_client

    def test_maps_branch_row_to_issuer(self):
        mock_client = self._client_returning([self._COMPLETE])

        with patch("quote_generator.supabase_client._get_client", return_value=mock_client):
            issuer = fetch_issuer("branch-uuid")

        assert issuer.office_name == "Consignación Abastible Llay Llay"
        assert issuer.address == "Balmaceda 473, Llay Llay, Valparaíso"
        assert issuer.phone == "34 2611498"
        assert issuer.email == "contacto@abastible.cl"
        assert issuer.footer_legal == "Abastible S.A. · Consignación Llay Llay · abastible.cl"

    def test_company_identity_stays_constant(self):
        """company_name and tax_id are Abastible S.A.'s, not the branch's."""
        mock_client = self._client_returning([self._COMPLETE])

        with patch("quote_generator.supabase_client._get_client", return_value=mock_client):
            issuer = fetch_issuer("branch-uuid")

        assert issuer.company_name == COMPANY_NAME
        assert issuer.tax_id == COMPANY_TAX_ID

    def test_queries_the_requested_branch(self):
        mock_client = MagicMock()
        chain = _mock_chain(_make_response([self._COMPLETE]))
        mock_client.table.return_value = chain

        with patch("quote_generator.supabase_client._get_client", return_value=mock_client):
            fetch_issuer("branch-uuid")

        mock_client.table.assert_called_once_with("branches")
        chain.eq.assert_called_once_with("id", "branch-uuid")

    def test_missing_footer_legal_is_allowed(self):
        row = {**self._COMPLETE, "footer_legal": None}
        mock_client = self._client_returning([row])

        with patch("quote_generator.supabase_client._get_client", return_value=mock_client):
            issuer = fetch_issuer("branch-uuid")

        assert issuer.footer_legal == ""

    @pytest.mark.parametrize("field", ["office_name", "address", "phone", "email"])
    @pytest.mark.parametrize("empty", [None, "", "   "], ids=["null", "blank", "whitespace"])
    def test_refuses_when_an_issuer_field_is_missing(self, field: str, empty):
        """Whitespace counts as missing: " " is truthy, and a quote with a blank
        address line is exactly the unattributable document the refusal exists for."""
        row = {**self._COMPLETE, field: empty}
        mock_client = self._client_returning([row])

        with patch("quote_generator.supabase_client._get_client", return_value=mock_client):
            with pytest.raises(ValueError, match="datos de emisor"):
                fetch_issuer("branch-uuid")

    def test_trims_surrounding_whitespace(self):
        row = {**self._COMPLETE, "office_name": "  Oficina X  ", "footer_legal": "   "}
        mock_client = self._client_returning([row])

        with patch("quote_generator.supabase_client._get_client", return_value=mock_client):
            issuer = fetch_issuer("branch-uuid")

        assert issuer.office_name == "Oficina X"
        # A whitespace-only footer must reach the PDF as absent, so the composed
        # fallback wins instead of printing a blank line.
        assert issuer.footer_legal == ""

    def test_refuses_when_branch_does_not_exist(self):
        mock_client = self._client_returning([])

        with patch("quote_generator.supabase_client._get_client", return_value=mock_client):
            with pytest.raises(ValueError, match="no existe"):
                fetch_issuer("branch-uuid")


# ---------------------------------------------------------------------------
# fetch_cylinder
# ---------------------------------------------------------------------------

class TestFetchCylinder:
    def test_maps_row_to_cylinder_data(self):
        row_data = {"id": 2, "name": "11 Kg", "cylinder_price": 85000, "format_code": "GAS11N"}
        mock_client = MagicMock()
        mock_client.table.return_value = _mock_chain(_make_response(row_data))

        with patch("quote_generator.supabase_client._get_client", return_value=mock_client):
            result = fetch_cylinder(2)

        assert isinstance(result, CylinderData)
        assert result.id == 2
        assert result.name == "11 Kg"
        assert result.cylinder_price == 85000
        assert result.format_code == "GAS11N"

    def test_raises_when_cylinder_price_is_null(self):
        row_data = {"id": 3, "name": "15 Kg", "cylinder_price": None, "format_code": "GAS15N"}
        mock_client = MagicMock()
        mock_client.table.return_value = _mock_chain(_make_response(row_data))

        with patch("quote_generator.supabase_client._get_client", return_value=mock_client):
            with pytest.raises(ValueError, match="no tiene precio de envase"):
                fetch_cylinder(3)


# ---------------------------------------------------------------------------
# resolve_items
# ---------------------------------------------------------------------------

class TestResolveItems:
    _REF = date(2026, 4, 24)

    def _setup_client(self, lp_data: dict, disc_data: list) -> MagicMock:
        mock_client = MagicMock()

        lp_chain = _mock_chain(_make_response(lp_data))
        disc_chain = _mock_chain(_make_response(disc_data))

        # First call → list_prices, second call → customer_discounts
        mock_client.table.side_effect = [lp_chain, disc_chain]
        return mock_client

    def test_resolves_price_and_discount(self):
        lp_data = {"id": "lp-1", "format_code": "GAS-45", "price": 34450}
        disc_data = [{"discount": "20.5"}]
        mock_client = self._setup_client(lp_data, disc_data)

        with patch("quote_generator.supabase_client._get_client", return_value=mock_client):
            result = resolve_items(
                "cust-1",
                [{"list_price_id": "lp-1", "quantity": 10, "description": "Despacho"}],
                self._REF,
            )

        assert len(result) == 1
        item = result[0]
        assert isinstance(item, ResolvedItem)
        assert item.format_code == "GAS-45"
        assert item.unit_price_with_tax == 34450
        assert item.discount_pct == 20.5
        assert item.quantity == 10
        assert item.description == "Despacho"
        assert item.cylinder_id is None

    def test_defaults_discount_to_zero_when_no_row(self):
        lp_data = {"id": "lp-2", "format_code": "GAS-11", "price": 11900}
        mock_client = self._setup_client(lp_data, disc_data=[])

        with patch("quote_generator.supabase_client._get_client", return_value=mock_client):
            result = resolve_items(
                "cust-no-discount",
                [{"list_price_id": "lp-2", "quantity": 1, "description": "Test"}],
                self._REF,
            )

        assert result[0].discount_pct == 0.0

    def test_resolves_multiple_items(self):
        mock_client = MagicMock()
        lp1 = _mock_chain(_make_response({"id": "lp-1", "format_code": "A", "price": 1000}))
        disc1 = _mock_chain(_make_response([]))
        lp2 = _mock_chain(_make_response({"id": "lp-2", "format_code": "B", "price": 2000}))
        disc2 = _mock_chain(_make_response([{"discount": "10"}]))
        mock_client.table.side_effect = [lp1, disc1, lp2, disc2]

        with patch("quote_generator.supabase_client._get_client", return_value=mock_client):
            result = resolve_items(
                "cust-1",
                [
                    {"list_price_id": "lp-1", "quantity": 5, "description": "Item A"},
                    {"list_price_id": "lp-2", "quantity": 3, "description": "Item B"},
                ],
                self._REF,
            )

        assert len(result) == 2
        assert result[0].format_code == "A"
        assert result[1].format_code == "B"
        assert result[1].discount_pct == 10.0

    def test_prospect_refill_uses_request_discount(self):
        lp_data = {"id": "lp-1", "format_code": "GAS11N", "price": 11900}
        mock_client = MagicMock()
        mock_client.table.return_value = _mock_chain(_make_response(lp_data))

        with patch("quote_generator.supabase_client._get_client", return_value=mock_client):
            result = resolve_items(
                None,
                [{"type": "refill", "list_price_id": "lp-1", "quantity": 5, "discount_pct": 0.12, "description": "Gas"}],
                self._REF,
                is_prospect=True,
            )

        assert result[0].discount_pct == 0.12
        # customer_discounts should NOT have been queried (only list_prices table)
        mock_client.table.assert_called_once_with("list_prices")

    def test_cylinder_item_resolved_from_cylinders_table(self):
        cyl_data = {"id": 2, "name": "11 Kg", "cylinder_price": 85000, "format_code": "GAS11N"}
        mock_client = MagicMock()
        mock_client.table.return_value = _mock_chain(_make_response(cyl_data))

        with patch("quote_generator.supabase_client._get_client", return_value=mock_client):
            result = resolve_items(
                None,
                [{"type": "cylinder", "cylinder_id": 2, "quantity": 1, "description": "Cilindro nuevo"}],
                self._REF,
            )

        item = result[0]
        assert item.unit_price_with_tax == 85000
        assert item.discount_pct == 0.0
        assert item.cylinder_id == 2
        assert item.list_price_id is None
        assert item.format_code == "GAS11N"

    def test_discount_query_excludes_same_day_closed_records(self):
        # Regression: when a discount is changed today, the old row is closed with
        # valid_until = today and a new row opens with valid_from = today. The query
        # must treat valid_until as exclusive (gt, not gte) and pick the newest open
        # row, otherwise the stale discount leaks into the quotation.
        lp_data = {"id": "lp-1", "format_code": "GAS05N", "price": 16400}
        disc_chain = _mock_chain(_make_response([{"discount": "0.20"}]))
        lp_chain = _mock_chain(_make_response(lp_data))
        mock_client = MagicMock()
        mock_client.table.side_effect = [lp_chain, disc_chain]

        ref = date(2026, 5, 27)
        with patch("quote_generator.supabase_client._get_client", return_value=mock_client):
            result = resolve_items(
                "cust-panquehue",
                [{"list_price_id": "lp-1", "quantity": 1, "description": "Recarga 5kg"}],
                ref,
            )

        assert result[0].discount_pct == 0.20
        # valid_until must be exclusive so a row closed today is not considered active.
        disc_chain.or_.assert_called_once_with(f"valid_until.is.null,valid_until.gt.{ref.isoformat()}")
        disc_chain.order.assert_called_once_with("valid_from", desc=True)
        disc_chain.limit.assert_called_once_with(1)

    def test_list_price_query_uses_exclusive_valid_until(self):
        lp_data = {"id": "lp-1", "format_code": "GAS05N", "price": 16400}
        lp_chain = _mock_chain(_make_response(lp_data))
        disc_chain = _mock_chain(_make_response([]))
        mock_client = MagicMock()
        mock_client.table.side_effect = [lp_chain, disc_chain]

        ref = date(2026, 5, 27)
        with patch("quote_generator.supabase_client._get_client", return_value=mock_client):
            resolve_items(
                "cust-1",
                [{"list_price_id": "lp-1", "quantity": 1, "description": "Recarga"}],
                ref,
            )

        lp_chain.or_.assert_called_once_with(f"valid_until.is.null,valid_until.gt.{ref.isoformat()}")

    def test_cylinder_raises_when_price_not_set(self):
        cyl_data = {"id": 3, "name": "15 Kg", "cylinder_price": None, "format_code": "GAS15N"}
        mock_client = MagicMock()
        mock_client.table.return_value = _mock_chain(_make_response(cyl_data))

        with patch("quote_generator.supabase_client._get_client", return_value=mock_client):
            with pytest.raises(ValueError, match="no tiene precio de envase"):
                resolve_items(
                    None,
                    [{"type": "cylinder", "cylinder_id": 3, "quantity": 1}],
                    self._REF,
                )


# ---------------------------------------------------------------------------
# save_quotation
# ---------------------------------------------------------------------------

class TestSaveQuotation:
    def test_returns_quotation_id(self):
        mock_client = MagicMock()
        q_chain = _mock_chain(_make_response([{"id": "quot-uuid-1"}]))
        qi_chain = _mock_chain(_make_response([]))
        mock_client.table.side_effect = [q_chain, qi_chain]

        items = [
            ResolvedItem("lp-1", "GAS-45", "Despacho", 5, 34450, 10.0),
        ]

        with patch("quote_generator.supabase_client._get_client", return_value=mock_client):
            qid = save_quotation(42, "cust-1", "Juan", items, notes=None, branch_id="branch-1")

        assert qid == "quot-uuid-1"

    def test_inserts_correct_quotation_fields(self):
        mock_client = MagicMock()
        q_chain = _mock_chain(_make_response([{"id": "q-id"}]))
        qi_chain = _mock_chain(_make_response([]))
        mock_client.table.side_effect = [q_chain, qi_chain]

        items = [ResolvedItem("lp-1", "GAS-45", "Desc", 2, 10000, 0.0)]

        with patch("quote_generator.supabase_client._get_client", return_value=mock_client):
            save_quotation(7, "cust-7", "María", items, notes="nota", branch_id="branch-7")

        inserted = q_chain.insert.call_args[0][0]
        assert inserted["number"] == 7
        assert inserted["customer_id"] == "cust-7"
        assert inserted["contact_name"] == "María"
        assert inserted["status"] == "draft"
        assert inserted["notes"] == "nota"
        assert inserted["branch_id"] == "branch-7"

    def test_inserts_quotation_items_with_positions(self):
        mock_client = MagicMock()
        q_chain = _mock_chain(_make_response([{"id": "q-id"}]))
        qi_chain = _mock_chain(_make_response([]))
        mock_client.table.side_effect = [q_chain, qi_chain]

        items = [
            ResolvedItem(list_price_id="lp-1", format_code="A", quantity=1, unit_price_with_tax=1000, discount_pct=0.0, description="Desc A"),
            ResolvedItem(list_price_id="lp-2", format_code="B", quantity=2, unit_price_with_tax=2000, discount_pct=5.0, description="Desc B"),
        ]

        with patch("quote_generator.supabase_client._get_client", return_value=mock_client):
            save_quotation(1, "cust-1", "X", items, notes=None, branch_id="branch-1")

        qi_inserted = qi_chain.insert.call_args[0][0]
        assert qi_inserted[0]["position"] == 1
        assert qi_inserted[1]["position"] == 2
        assert qi_inserted[0]["format_code"] == "A"
        assert qi_inserted[1]["discount_pct"] == 5.0
        assert qi_inserted[0]["branch_id"] == "branch-1"
        assert qi_inserted[1]["branch_id"] == "branch-1"

    def test_notes_defaults_to_empty_string_when_none(self):
        mock_client = MagicMock()
        q_chain = _mock_chain(_make_response([{"id": "q-id"}]))
        qi_chain = _mock_chain(_make_response([]))
        mock_client.table.side_effect = [q_chain, qi_chain]

        with patch("quote_generator.supabase_client._get_client", return_value=mock_client):
            save_quotation(1, "c", "X", [ResolvedItem(list_price_id="lp-1", format_code="A", description="", quantity=1, unit_price_with_tax=100, discount_pct=0.0)], notes=None, branch_id="branch-1")

        inserted = q_chain.insert.call_args[0][0]
        assert inserted["notes"] == ""

    def test_prospect_quotation_saves_name_and_rut(self):
        mock_client = MagicMock()
        q_chain = _mock_chain(_make_response([{"id": "q-id"}]))
        qi_chain = _mock_chain(_make_response([]))
        mock_client.table.side_effect = [q_chain, qi_chain]

        items = [ResolvedItem(list_price_id="lp-1", format_code="GAS11N", description="Gas 11 kg", quantity=5, unit_price_with_tax=11900, discount_pct=0.12)]

        with patch("quote_generator.supabase_client._get_client", return_value=mock_client):
            save_quotation(
                10, None, "Juan", items, notes=None,
                branch_id="branch-1",
                prospect_name="Comercio El Roble",
                prospect_rut="12.345.678-9",
            )

        inserted = q_chain.insert.call_args[0][0]
        assert inserted["customer_id"] is None
        assert inserted["prospect_name"] == "Comercio El Roble"
        assert inserted["prospect_rut"] == "12.345.678-9"

    def test_cylinder_item_saves_cylinder_id(self):
        mock_client = MagicMock()
        q_chain = _mock_chain(_make_response([{"id": "q-id"}]))
        qi_chain = _mock_chain(_make_response([]))
        mock_client.table.side_effect = [q_chain, qi_chain]

        items = [ResolvedItem(list_price_id=None, format_code="GAS11N", description="Cilindro nuevo", quantity=1, unit_price_with_tax=85000, discount_pct=0.0, cylinder_id=2)]

        with patch("quote_generator.supabase_client._get_client", return_value=mock_client):
            save_quotation(5, "cust-1", "X", items, notes=None, branch_id="branch-1")

        qi_inserted = qi_chain.insert.call_args[0][0]
        assert qi_inserted[0]["cylinder_id"] == 2
        assert qi_inserted[0]["list_price_id"] is None
