from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ALLOWED = "https://abastible-llayllay.vercel.app"
HEADER = "Access-Control-Allow-Origin"


@pytest.fixture(scope="module")
def client():
    sys.path.insert(0, str(REPO_ROOT / "src"))
    spec = importlib.util.spec_from_file_location("vercel_index", REPO_ROOT / "api" / "index.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module.app.test_client()


def test_allowed_origin_is_echoed_back(client):
    response = client.open("/generate_quotation", method="OPTIONS", headers={"Origin": ALLOWED})
    assert response.headers[HEADER] == ALLOWED


def test_unknown_origin_gets_no_allow_origin_header(client):
    # Naming a different allowed origin instead would be no more permissive —
    # the browser blocks on the mismatch — but it was unstable across deploys,
    # because ALLOWED_ORIGINS is a set and the fallback took an arbitrary member.
    response = client.open(
        "/generate_quotation", method="OPTIONS", headers={"Origin": "https://not-allowed.example"}
    )
    assert HEADER not in response.headers


def test_request_without_an_origin_gets_no_allow_origin_header(client):
    response = client.open("/generate_quotation", method="OPTIONS")
    assert HEADER not in response.headers


def test_vary_on_origin_is_always_set(client):
    # Without it a shared cache could hand one origin the response built for
    # another, which is exactly what makes an allowlist echo unsafe to cache.
    for headers in ({"Origin": ALLOWED}, {"Origin": "https://not-allowed.example"}, {}):
        response = client.open("/generate_quotation", method="OPTIONS", headers=headers)
        assert response.headers["Vary"] == "Origin"


@pytest.mark.parametrize(
    ("path", "method", "expected_status"),
    [
        ("/generate_quotation", "POST", 400),  # rejected by the app's own validation
        ("/missing", "GET", 404),
        ("/generate_quotation", "GET", 405),
    ],
)
def test_error_responses_still_carry_cors_headers(client, path, method, expected_status):
    # These come back from error handlers rather than the route, so they are the
    # easiest place to lose the headers — and a response the browser discards is
    # indistinguishable to the caller from the endpoint being down.
    response = client.open(path, method=method, headers={"Origin": ALLOWED}, json={})
    assert response.status_code == expected_status
    assert response.headers[HEADER] == ALLOWED
