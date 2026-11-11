from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from postgrest.exceptions import APIError

REPO_ROOT = Path(__file__).resolve().parents[1]
ALLOWED = "https://abastible-llayllay.vercel.app"
TOKEN_BRANCH = "a0000000-0000-0000-0000-000000000001"
OTHER_BRANCH = "b0000000-0000-0000-0000-000000000001"

BODY = {
    "branch_id": OTHER_BRANCH,
    "customer_id": "11111111-1111-1111-1111-111111111111",
    "items": [
        {"type": "refill", "list_price_id": "22222222-2222-2222-2222-222222222222", "quantity": 2},
        {"type": "cylinder", "cylinder_id": 5, "quantity": 1},
    ],
}


@pytest.fixture()
def module():
    sys.path.insert(0, str(REPO_ROOT / "src"))
    spec = importlib.util.spec_from_file_location("vercel_index_auth", REPO_ROOT / "api" / "index.py")
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)  # type: ignore[union-attr]
    return loaded


@pytest.fixture()
def quote_pipeline(module, monkeypatch):
    """Stub everything after the caller check, keeping save_quotation observable."""
    from quote_generator.supabase_client import CustomerData, ResolvedItem

    monkeypatch.setattr(module, "fetch_customer", lambda _id: CustomerData(name="Acme", rut="76.123.456-7"))
    monkeypatch.setattr(
        module,
        "resolve_items",
        lambda *_args, **_kwargs: [ResolvedItem("lp", "11", "", 2, 20000, 0.0)],
    )
    service_client = MagicMock()
    service_client.rpc.return_value.execute.return_value.data = 91
    monkeypatch.setattr(module, "_get_client", lambda: service_client)
    monkeypatch.setattr(module, "render_quote_pdf", lambda *_args: None)
    save = MagicMock()
    monkeypatch.setattr(module, "save_quotation", save)
    return save


def _post(module, headers=None, body=None):
    client = module.app.test_client()
    return client.post(
        "/generate_quotation",
        json=BODY if body is None else body,
        headers={"Origin": ALLOWED, **(headers or {})},
    )


def test_preflight_allows_the_authorization_header(module):
    response = module.app.test_client().open(
        "/generate_quotation", method="OPTIONS", headers={"Origin": ALLOWED}
    )
    assert "Authorization" in response.headers["Access-Control-Allow-Headers"]


def test_request_without_token_gets_401_when_auth_is_required(module, monkeypatch):
    monkeypatch.setenv("QUOTATION_REQUIRE_AUTH", "true")
    authorize = MagicMock()
    monkeypatch.setattr(module, "authorize_caller", authorize)

    response = _post(module)

    assert response.status_code == 401
    assert response.headers["Access-Control-Allow-Origin"] == ALLOWED
    authorize.assert_not_called()


def test_request_without_token_still_works_while_auth_is_optional(module, monkeypatch, quote_pipeline):
    monkeypatch.delenv("QUOTATION_REQUIRE_AUTH", raising=False)

    response = _post(module)

    assert response.status_code == 200
    assert quote_pipeline.call_args.kwargs["branch_id"] == OTHER_BRANCH


def test_rejected_token_is_answered_with_its_status(module, monkeypatch, quote_pipeline):
    from quote_generator.supabase_client import CallerRejected

    def reject(*_args):
        raise CallerRejected(404, "cliente, precio o cilindro no encontrado en la sucursal")

    monkeypatch.setattr(module, "authorize_caller", reject)

    response = _post(module, headers={"Authorization": "Bearer user-token"})

    assert response.status_code == 404
    quote_pipeline.assert_not_called()


def test_branch_comes_from_the_token_not_the_body(module, monkeypatch, quote_pipeline):
    authorize = MagicMock(return_value=TOKEN_BRANCH)
    monkeypatch.setattr(module, "authorize_caller", authorize)

    response = _post(module, headers={"Authorization": "Bearer user-token"})

    assert response.status_code == 200
    authorize.assert_called_once_with(
        "user-token",
        BODY["customer_id"],
        ["22222222-2222-2222-2222-222222222222"],
        [5],
    )
    assert quote_pipeline.call_args.kwargs["branch_id"] == TOKEN_BRANCH


def test_body_without_branch_is_accepted_with_a_token(module, monkeypatch, quote_pipeline):
    monkeypatch.setattr(module, "authorize_caller", MagicMock(return_value=TOKEN_BRANCH))
    body = {key: value for key, value in BODY.items() if key != "branch_id"}

    response = _post(module, headers={"Authorization": "Bearer user-token"}, body=body)

    assert response.status_code == 200
    assert quote_pipeline.call_args.kwargs["branch_id"] == TOKEN_BRANCH


# ---------------------------------------------------------------------------
# authorize_caller
# ---------------------------------------------------------------------------


@pytest.fixture()
def postgrest(monkeypatch):
    from quote_generator import supabase_client

    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    instance = MagicMock()
    factory = MagicMock(return_value=instance)
    monkeypatch.setattr(supabase_client, "SyncPostgrestClient", factory)
    return factory, instance


def test_authorize_caller_sends_the_user_token_and_returns_the_branch(postgrest):
    from quote_generator.supabase_client import authorize_caller

    factory, instance = postgrest
    instance.rpc.return_value.execute.return_value.data = TOKEN_BRANCH

    assert authorize_caller("user-token", "customer", ["lp"], [5]) == TOKEN_BRANCH

    headers = factory.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer user-token"
    assert headers["apikey"] == "anon-key"
    instance.rpc.assert_called_once_with(
        "authorize_quotation",
        {"p_customer_id": "customer", "p_list_price_ids": ["lp"], "p_cylinder_ids": [5]},
    )


@pytest.mark.parametrize(
    ("code", "message", "status"),
    [
        ("PGRST301", "JWSError", 401),
        ("PGRST303", "JWT expired", 401),
        ("42501", "Quotation access denied", 403),
        ("P0002", "Customer not found", 404),
        ("22P02", "invalid input syntax for type uuid", 400),
    ],
)
def test_authorize_caller_maps_database_refusals(postgrest, code, message, status):
    from quote_generator.supabase_client import CallerRejected, authorize_caller

    _factory, instance = postgrest
    instance.rpc.return_value.execute.side_effect = APIError({"code": code, "message": message})

    with pytest.raises(CallerRejected) as raised:
        authorize_caller("user-token", None, [], [])
    assert raised.value.status == status
