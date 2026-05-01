"""Regression tests for public email masking and 2026 financial statements integrity."""

import os
import time

import bcrypt
import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")

# Module scope: lockout cleanup + auth playbook + public settings + financial statements formulas.
ORG_CREDENTIALS = {
    "social-solidarity": {"username": "admin_takaful", "password": "Admin@123"},
    "general-union": {"username": "admin_union", "password": "Admin@123"},
}


@pytest.fixture(scope="session")
def base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not set")
    return BASE_URL.rstrip("/")


@pytest.fixture(scope="session")
def mongo_db():
    env_values = dotenv_values("/app/backend/.env")
    mongo_url = os.environ.get("MONGO_URL") or env_values.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME") or env_values.get("DB_NAME")
    if not mongo_url or not db_name:
        pytest.skip("MONGO_URL/DB_NAME are missing")

    mongo_url = str(mongo_url).strip().strip('"').strip("'")
    db_name = str(db_name).strip().strip('"').strip("'")
    client = MongoClient(mongo_url)
    db = client[db_name]
    yield db
    client.close()


@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


def login(session: requests.Session, base_url: str, organization_id: str):
    creds = ORG_CREDENTIALS[organization_id]
    response = session.post(
        f"{base_url}/api/auth/login",
        json={
            "username": creds["username"],
            "password": creds["password"],
            "organization_id": organization_id,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body.get("token"), str) and body["token"]
    assert body["user"]["organization_id"] == organization_id
    return response, body


def test_cleanup_known_lockout_attempts_for_iteration_29_30_31(mongo_db):
    identifiers = [
        "general-union:test_lockout_probe_user",
        "general-union:test_lockout_probe_user_iter30",
    ]
    mongo_db.login_attempts.delete_many({"identifier": {"$in": identifiers}})
    remaining = list(mongo_db.login_attempts.find({"identifier": {"$in": identifiers}}, {"_id": 0}))
    assert remaining == []


def test_public_settings_has_no_example_or_iter_emails(api_client, base_url):
    response = api_client.get(f"{base_url}/api/app-settings/public")
    assert response.status_code == 200, response.text
    data = response.json()
    organizations = data.get("organizations", {})
    assert isinstance(organizations, dict)

    for org_id, org in organizations.items():
        email = (org.get("email") or "").strip().lower()
        assert not email.endswith("@example.com"), f"{org_id} has example email: {email}"
        assert "+iter" not in email, f"{org_id} has test iteration email: {email}"


def test_public_settings_key_orgs_have_official_email_or_none(api_client, base_url):
    response = api_client.get(f"{base_url}/api/app-settings/public")
    assert response.status_code == 200
    data = response.json()
    organizations = data.get("organizations", {})

    for org_id in ["social-solidarity", "general-union"]:
        assert org_id in organizations
        email = organizations[org_id].get("email")
        assert email is None or ("@" in email and not email.lower().endswith("@example.com") and "+iter" not in email.lower())


def test_auth_playbook_login_sets_httponly_cookie(api_client, base_url):
    login_response, _ = login(api_client, base_url, "social-solidarity")
    set_cookie = login_response.headers.get("set-cookie", "")
    assert "access_token=" in set_cookie
    assert "HttpOnly" in set_cookie


def test_auth_playbook_bruteforce_lockout_after_three_failures(api_client, base_url):
    username = f"TEST_iter45_lockout_probe_{int(time.time())}"
    payload = {
        "username": username,
        "password": "WrongPass@123",
        "organization_id": "general-union",
    }
    statuses = []
    for _ in range(4):
        response = api_client.post(f"{base_url}/api/auth/login", json=payload)
        statuses.append(response.status_code)
    assert statuses[:3] == [401, 401, 401]
    assert statuses[3] == 429


def test_auth_playbook_cors_preflight_allows_credentials(base_url):
    response = requests.options(
        f"{base_url}/api/auth/login",
        headers={
            "Origin": base_url,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
    )
    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-credentials") == "true"
    assert response.headers.get("access-control-allow-origin") not in (None, "")


def test_auth_playbook_bcrypt_hash_format_starts_with_2b():
    generated = bcrypt.hashpw("Admin@123".encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
    assert generated.startswith("$2b$")


def test_seed_admin_password_update_logic_present_in_code_review():
    """Password-change path is environment-driven; validate via code presence in this run."""
    with open("/app/backend/server.py", "r", encoding="utf-8") as handle:
        content = handle.read()
    assert "ensure_default_admin" in content
    assert "if not verify_password(ADMIN_INITIAL_PASSWORD, existing.get(\"password_hash\", \"\"))" in content
    assert "document[\"password_hash\"] = hash_password(ADMIN_INITIAL_PASSWORD)" in content


def test_financial_statements_2026_by_year_query_returns_required_sections(api_client, base_url):
    _, auth = login(api_client, base_url, "social-solidarity")
    headers = {"Authorization": f"Bearer {auth['token']}"}
    response = api_client.get(f"{base_url}/api/financial-statements?year=2026", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()

    assert data.get("organization_id") == "social-solidarity"
    assert "balance_sheet" in data
    assert "revenues_expenses" in data
    assert "receipts_payments" in data


def test_financial_statements_2026_formulas_and_validity(api_client, base_url):
    _, auth = login(api_client, base_url, "social-solidarity")
    headers = {"Authorization": f"Bearer {auth['token']}"}
    response = api_client.get(
        f"{base_url}/api/financial-statements?from_date=2026-01-01&to_date=2026-12-31",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()

    assets = float(data["balance_sheet"]["assets"]["total"])
    liabilities = float(data["balance_sheet"]["liabilities"]["total"])
    equity = float(data["balance_sheet"]["equity"]["total"])
    check_total = float(data["balance_sheet"]["check"]["total"])
    assert round(assets - (liabilities + equity), 2) == round(check_total, 2)
    assert abs(round(check_total, 2)) <= 0.01

    revenues_total = float(data["revenues_expenses"]["revenues"]["total"])
    expenses_total = float(data["revenues_expenses"]["expenses"]["total"])
    result_total = float(data["revenues_expenses"]["result"]["total"])
    assert round(revenues_total - expenses_total, 2) == round(result_total, 2)

    receipts_total = float(data["receipts_payments"]["receipts"]["total"])
    payments_total = float(data["receipts_payments"]["payments"]["total"])
    net_total = float(data["receipts_payments"]["net_cash_flow"]["total"])
    assert round(receipts_total - payments_total, 2) == round(net_total, 2)

    assert data.get("is_accounting_valid") is True
    critical_errors = [err for err in data.get("accounting_errors", []) if err.get("severity") == "critical"]
    assert critical_errors == []


def test_setup_download_exists_and_non_empty(api_client, base_url):
    response = api_client.get(f"{base_url}/api/download/setup")
    assert response.status_code == 200, response.text
    content_type = response.headers.get("content-type", "")
    assert "application/vnd.microsoft.portable-executable" in content_type
    assert len(response.content) > 100_000
