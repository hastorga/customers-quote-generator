from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from quote_generator.supabase_client import (
    CustomerData,
    ResolvedItem,
    fetch_customer,
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
            qid = save_quotation(42, "cust-1", "Juan", items, notes=None)

        assert qid == "quot-uuid-1"

    def test_inserts_correct_quotation_fields(self):
        mock_client = MagicMock()
        q_chain = _mock_chain(_make_response([{"id": "q-id"}]))
        qi_chain = _mock_chain(_make_response([]))
        mock_client.table.side_effect = [q_chain, qi_chain]

        items = [ResolvedItem("lp-1", "GAS-45", "Desc", 2, 10000, 0.0)]

        with patch("quote_generator.supabase_client._get_client", return_value=mock_client):
            save_quotation(7, "cust-7", "María", items, notes="nota")

        inserted = q_chain.insert.call_args[0][0]
        assert inserted["number"] == 7
        assert inserted["customer_id"] == "cust-7"
        assert inserted["contact_name"] == "María"
        assert inserted["status"] == "draft"
        assert inserted["notes"] == "nota"

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
            save_quotation(1, "cust-1", "X", items, notes=None)

        qi_inserted = qi_chain.insert.call_args[0][0]
        assert qi_inserted[0]["position"] == 1
        assert qi_inserted[1]["position"] == 2
        assert qi_inserted[0]["format_code"] == "A"
        assert qi_inserted[1]["discount_pct"] == 5.0

    def test_notes_defaults_to_empty_string_when_none(self):
        mock_client = MagicMock()
        q_chain = _mock_chain(_make_response([{"id": "q-id"}]))
        qi_chain = _mock_chain(_make_response([]))
        mock_client.table.side_effect = [q_chain, qi_chain]

        with patch("quote_generator.supabase_client._get_client", return_value=mock_client):
            save_quotation(1, "c", "X", [ResolvedItem(list_price_id="lp-1", format_code="A", quantity=1, unit_price_with_tax=100, discount_pct=0.0)], notes=None)

        inserted = q_chain.insert.call_args[0][0]
        assert inserted["notes"] == ""
