import os
import uuid

import pytest
import requests
from dotenv import dotenv_values


# Tax Engine profile + invoice lifecycle + audit + tenant isolation checks.
FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
SOCIAL_ORG = "social-solidarity"
UNION_ORG = "general-union"
MARKER = "TEST_TAX_ENGINE_AUTOMATION_DELETE_ME"


def _headers(token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


@pytest.fixture(scope="session")
def base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not configured")
    return BASE_URL


def _login(base_url: str, username: str, password: str, organization_id: str):
    response = requests.post(
        f"{base_url}/api/auth/login",
        json={"username": username, "password": password, "organization_id": organization_id},
        headers=_headers(),
        timeout=90,
    )
    return response


@pytest.fixture(scope="session")
def social_login(base_url):
    response = _login(base_url, "admin", "Admin@123", SOCIAL_ORG)
    if response.status_code != 200:
        pytest.skip(f"social admin login failed: {response.status_code} {response.text}")
    body = response.json()
    token = body.get("token")
    if not token:
        pytest.skip("social admin token missing")
    return {"token": token, "response": response, "body": body}


@pytest.fixture(scope="session")
def union_token(base_url):
    response = _login(base_url, "admin_union", "Admin@123", UNION_ORG)
    if response.status_code != 200:
        pytest.skip(f"general-union login failed: {response.status_code} {response.text}")
    token = response.json().get("token")
    if not token:
        pytest.skip("general-union token missing")
    return token


@pytest.fixture(scope="module")
def social_context(base_url, social_login):
    token = social_login["token"]
    profile_response = requests.get(
        f"{base_url}/api/tax-engine/profile",
        headers=_headers(token),
        timeout=90,
    )
    assert profile_response.status_code == 200, profile_response.text
    profile = profile_response.json()

    banks_response = requests.get(
        f"{base_url}/api/banks",
        headers=_headers(token),
        timeout=90,
    )
    assert banks_response.status_code == 200, banks_response.text
    banks = banks_response.json()
    assert len(banks) > 0

    rules = profile.get("tax_rules") or []
    default_rule = next((rule for rule in rules if rule.get("is_default")), rules[0] if rules else None)
    assert default_rule is not None, "No tax_rules configured in social-solidarity profile"

    return {
        "token": token,
        "profile": profile,
        "bank_id": banks[0]["id"],
        "rule": default_rule,
    }


@pytest.fixture(scope="module")
def created_invoices():
    return {"sales_id": None, "purchase_id": None, "approved_sales": None}


def test_auth_login_sets_httponly_cookie(base_url, social_login):
    set_cookie = social_login["response"].headers.get("set-cookie") or social_login["response"].headers.get("Set-Cookie") or ""
    assert "HttpOnly" in set_cookie


def test_tax_profile_get_put_and_configuration_flags(base_url, social_context):
    token = social_context["token"]
    profile = social_context["profile"]

    assert profile["organization_id"] == SOCIAL_ORG
    assert isinstance(profile.get("is_configured"), bool)
    assert isinstance(profile.get("configuration_errors"), list)

    put_payload = {
        "tax_registration_id": profile.get("tax_registration_id"),
        "taxpayer_name": profile.get("taxpayer_name"),
        "country_code": profile.get("country_code") or "EG",
        "currency": profile.get("currency") or "EGP",
        "eta_environment": profile.get("eta_environment") or "offline_ready",
        "tax_rules": profile.get("tax_rules") or [],
        "document_type_codes": profile.get("document_type_codes") or {},
        "journal_accounts": profile.get("journal_accounts") or {},
        "eta_payload_schema": profile.get("eta_payload_schema") or {},
        "auto_create_journal_on_approval": bool(profile.get("auto_create_journal_on_approval", True)),
    }
    put_response = requests.put(
        f"{base_url}/api/tax-engine/profile",
        json=put_payload,
        headers=_headers(token),
        timeout=90,
    )
    assert put_response.status_code == 200, put_response.text
    saved = put_response.json()
    assert saved["organization_id"] == SOCIAL_ORG
    assert isinstance(saved.get("is_configured"), bool)
    assert isinstance(saved.get("configuration_errors"), list)


def test_create_sales_draft_uses_profile_rule_and_snapshot(base_url, social_context, created_invoices):
    token = social_context["token"]
    rule = social_context["rule"]
    bank_id = social_context["bank_id"]
    invoice_number = f"{MARKER}-S-{uuid.uuid4().hex[:8]}"
    line_net = 100.0

    payload = {
        "invoice_type": "sales",
        "invoice_number": invoice_number,
        "issue_date": "2026-02-01",
        "customer_name": f"{MARKER} CUSTOMER SALES",
        "customer_tax_number": "123456789",
        "customer_type": "company",
        "payment_method": "bank_transfer",
        "bank_id": bank_id,
        "source_document_type": "manual",
        "lines": [
            {
                "description": f"{MARKER} SALES LINE",
                "quantity": 1,
                "unit_price": line_net,
                "item_code": rule["item_code"],
                "tax_status": rule.get("tax_status") or "standard",
                "discount_amount": 0,
            }
        ],
    }

    response = requests.post(
        f"{base_url}/api/tax-engine/invoices",
        json=payload,
        headers=_headers(token),
        timeout=90,
    )
    assert response.status_code == 200, response.text
    body = response.json()

    expected_tax = round(line_net * float(rule.get("rate") or 0) / 100, 2)
    assert body["invoice_type"] == "sales"
    assert body["invoice_number"] == invoice_number
    assert body["tax_amount"] == expected_tax
    assert body["total_amount"] == round(line_net + expected_tax, 2)
    assert body.get("tax_engine_snapshot") is not None
    assert body["tax_engine_snapshot"].get("document_type_code") == (social_context["profile"].get("document_type_codes") or {}).get("sales")
    assert rule["id"] in (body["tax_engine_snapshot"].get("rules_used") or [])
    assert isinstance(body["tax_engine_snapshot"].get("lines"), list)
    created_invoices["sales_id"] = body["id"]


def test_create_purchase_draft_supports_invoice_type_purchase(base_url, social_context, created_invoices):
    token = social_context["token"]
    rule = social_context["rule"]
    bank_id = social_context["bank_id"]
    invoice_number = f"{MARKER}-P-{uuid.uuid4().hex[:8]}"
    line_net = 200.0

    payload = {
        "invoice_type": "purchase",
        "invoice_number": invoice_number,
        "issue_date": "2026-02-01",
        "customer_name": f"{MARKER} SUPPLIER PURCHASE",
        "customer_tax_number": "987654321",
        "customer_type": "company",
        "payment_method": "bank_transfer",
        "bank_id": bank_id,
        "source_document_type": "manual",
        "lines": [
            {
                "description": f"{MARKER} PURCHASE LINE",
                "quantity": 1,
                "unit_price": line_net,
                "item_code": rule["item_code"],
                "tax_status": rule.get("tax_status") or "standard",
                "discount_amount": 0,
            }
        ],
    }

    response = requests.post(
        f"{base_url}/api/tax-engine/invoices",
        json=payload,
        headers=_headers(token),
        timeout=90,
    )
    assert response.status_code == 200, response.text
    body = response.json()

    expected_tax = round(line_net * float(rule.get("rate") or 0) / 100, 2)
    assert body["invoice_type"] == "purchase"
    assert body["tax_amount"] == expected_tax
    assert body["total_amount"] == round(line_net + expected_tax, 2)
    assert body["tax_engine_snapshot"].get("document_type_code") == (social_context["profile"].get("document_type_codes") or {}).get("purchase")
    assert rule["id"] in (body["tax_engine_snapshot"].get("rules_used") or [])
    created_invoices["purchase_id"] = body["id"]


def test_approve_sales_invoice_creates_journal_and_tax_entity(base_url, social_context, created_invoices):
    token = social_context["token"]
    sales_id = created_invoices.get("sales_id")
    assert isinstance(sales_id, str) and len(sales_id) > 0

    approve_response = requests.post(
        f"{base_url}/api/tax-engine/invoices/{sales_id}/approve",
        headers=_headers(token),
        timeout=120,
    )
    assert approve_response.status_code == 200, approve_response.text
    body = approve_response.json()

    assert isinstance(body.get("journal_entry_id"), str) and len(body["journal_entry_id"]) > 0
    assert isinstance(body.get("tax_invoice_entity_id"), str) and len(body["tax_invoice_entity_id"]) > 0
    assert body["invoice"]["journal_entry_id"] == body["journal_entry_id"]
    assert body["invoice"]["tax_invoice_entity_id"] == body["tax_invoice_entity_id"]
    assert body["invoice"]["status"] == "ready"
    assert body["invoice"].get("eta_document_uuid") is None
    assert body["invoice"].get("eta_submission_id") is None
    created_invoices["approved_sales"] = body

    journals_response = requests.get(
        f"{base_url}/api/journal-entries",
        headers=_headers(token),
        timeout=120,
    )
    assert journals_response.status_code == 200, journals_response.text
    journals = journals_response.json()
    journal = next((item for item in journals if item.get("id") == body["journal_entry_id"]), None)
    assert journal is not None
    assert journal.get("source_type") == "tax_invoice"
    assert journal.get("source_id") == sales_id


def test_tax_engine_audit_logs_written_under_system_path(base_url, social_context, created_invoices):
    token = social_context["token"]
    response = requests.get(
        f"{base_url}/api/admin/security/audit-logs",
        params={"limit": 400},
        headers=_headers(token),
        timeout=120,
    )
    assert response.status_code == 200, response.text
    logs = response.json()
    tax_logs = [item for item in logs if item.get("path") == "/system/tax-engine"]
    assert len(tax_logs) > 0

    actions = {item.get("action") for item in tax_logs}
    assert "TAX_PROFILE_SAVED" in actions
    assert "TAX_INVOICE_CREATED" in actions
    assert "TAX_INVOICE_APPROVED" in actions

    approved = created_invoices.get("approved_sales") or {}
    if approved.get("invoice"):
        approved_invoice_id = approved["invoice"].get("id")
        assert any((log.get("after_document") or {}).get("invoice", {}).get("id") == approved_invoice_id for log in tax_logs if log.get("action") == "TAX_INVOICE_APPROVED")


def test_multitenant_general_union_cannot_see_social_tax_engine_data(base_url, union_token, social_context, created_invoices):
    social_registration = social_context["profile"].get("tax_registration_id")

    union_profile_response = requests.get(
        f"{base_url}/api/tax-engine/profile",
        headers=_headers(union_token),
        timeout=90,
    )
    assert union_profile_response.status_code == 200, union_profile_response.text
    union_profile = union_profile_response.json()
    assert union_profile.get("organization_id") == UNION_ORG
    if social_registration:
        assert union_profile.get("tax_registration_id") != social_registration

    union_invoices_response = requests.get(
        f"{base_url}/api/electronic-invoices",
        headers=_headers(union_token),
        timeout=90,
    )
    assert union_invoices_response.status_code == 200, union_invoices_response.text
    union_invoice_ids = {item.get("id") for item in union_invoices_response.json()}

    for key in ["sales_id", "purchase_id"]:
        assert created_invoices.get(key) not in union_invoice_ids
