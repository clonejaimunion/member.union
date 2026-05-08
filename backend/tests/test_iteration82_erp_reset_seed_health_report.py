import os
from urllib.parse import urlparse

import pytest
import requests
from dotenv import dotenv_values


# ERP reset/seed verification: banks fallback, seeded entries, trial balance, ERP health, and audit trace.
FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
ORG_ID = "social-solidarity"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@123"
DEFAULT_BANK_IDS = {"industrial-development", "banque-misr", "agricultural-bank"}
EXPECTED_SOURCE_TYPES = {"opening_balance", "deposit", "deposit_interest", "revenue", "expense"}
KNOWN_FINAL_REPORT_ID = "030165c2-ed04-4f01-9222-fcbe4b56680b"


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


@pytest.fixture(scope="session")
def login_response(base_url):
    response = requests.post(
        f"{base_url}/api/auth/login",
        json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD,
            "organization_id": ORG_ID,
        },
        headers=_headers(),
        timeout=60,
    )
    if response.status_code != 200:
        pytest.skip(f"admin login failed: {response.status_code} {response.text}")
    return response


@pytest.fixture(scope="session")
def admin_token(login_response):
    token = login_response.json().get("token")
    if not token:
        pytest.skip("admin token missing")
    return token


def test_login_sets_http_only_cookie(login_response):
    set_cookie = login_response.headers.get("set-cookie", "")
    assert "access_token=" in set_cookie
    assert "HttpOnly" in set_cookie


def test_reset_kept_default_banks_only(base_url, admin_token):
    response = requests.get(f"{base_url}/api/banks", headers=_headers(admin_token), timeout=60)
    assert response.status_code == 200, response.text
    banks = response.json()
    assert len(banks) == 3
    bank_ids = {item.get("id") for item in banks}
    assert bank_ids == DEFAULT_BANK_IDS


def test_seed_clean_dataset_has_expected_journal_entries(base_url, admin_token):
    response = requests.get(f"{base_url}/api/journal-entries", headers=_headers(admin_token), timeout=90)
    assert response.status_code == 200, response.text
    entries = response.json()
    assert len(entries) == 5

    active_source_types = {entry.get("source_type") for entry in entries}
    assert active_source_types == EXPECTED_SOURCE_TYPES

    for entry in entries:
        assert entry.get("status") == "approved"
        assert abs(float(entry.get("total_debit") or 0) - float(entry.get("total_credit") or 0)) < 0.01


def test_seed_has_source_documents_for_deposit_revenue_expense(base_url, admin_token):
    entries_response = requests.get(f"{base_url}/api/journal-entries", headers=_headers(admin_token), timeout=90)
    assert entries_response.status_code == 200, entries_response.text
    entries = entries_response.json()

    revenue_entry = next((item for item in entries if item.get("source_type") == "revenue"), None)
    expense_entry = next((item for item in entries if item.get("source_type") == "expense"), None)
    deposit_entry = next((item for item in entries if item.get("source_type") == "deposit"), None)

    assert revenue_entry and revenue_entry.get("source_id")
    assert expense_entry and expense_entry.get("source_id")
    assert deposit_entry and deposit_entry.get("source_id")

    revenue_response = requests.get(
        f"{base_url}/api/revenues/{revenue_entry['source_id']}",
        headers=_headers(admin_token),
        timeout=60,
    )
    assert revenue_response.status_code == 200, revenue_response.text

    expense_response = requests.get(
        f"{base_url}/api/expenses/{expense_entry['source_id']}",
        headers=_headers(admin_token),
        timeout=60,
    )
    assert expense_response.status_code == 200, expense_response.text

    deposits_response = requests.get(
        f"{base_url}/api/banks/banque-misr/deposits",
        headers=_headers(admin_token),
        timeout=60,
    )
    assert deposits_response.status_code == 200, deposits_response.text
    deposits = deposits_response.json()
    assert any(item.get("id") == deposit_entry["source_id"] for item in deposits)


def test_trial_balance_2026_is_balanced(base_url, admin_token):
    response = requests.get(
        f"{base_url}/api/trial-balance",
        params={"from_date": "2026-01-01", "to_date": "2026-12-31", "non_zero_only": "false"},
        headers=_headers(admin_token),
        timeout=90,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload.get("is_balanced") is True
    assert abs(float(payload.get("total_debit") or 0) - float(payload.get("total_credit") or 0)) < 0.01


def test_erp_health_report_score_and_direct_pdf(base_url, admin_token):
    response = requests.get(f"{base_url}/api/erp-health-report", headers=_headers(admin_token), timeout=180)
    assert response.status_code == 200, response.text
    payload = response.json()

    assert int(payload.get("overall_score") or 0) >= 90
    assert isinstance(payload.get("metrics"), list) and len(payload["metrics"]) >= 8
    assert isinstance(payload.get("recommendations"), list) and len(payload["recommendations"]) >= 1

    direct_download_url = payload.get("direct_download_url")
    assert isinstance(direct_download_url, str) and direct_download_url.startswith("http")

    api_host = urlparse(base_url).netloc
    direct_host = urlparse(direct_download_url).netloc
    assert direct_host == api_host

    pdf_response = requests.get(direct_download_url, timeout=180)
    assert pdf_response.status_code == 200
    assert pdf_response.headers.get("content-type", "").startswith("application/pdf")
    assert pdf_response.content[:4] == b"%PDF"


def test_erp_health_metrics_show_no_key_accounting_issues(base_url, admin_token):
    response = requests.get(f"{base_url}/api/erp-health-report", headers=_headers(admin_token), timeout=180)
    assert response.status_code == 200, response.text
    payload = response.json()

    metrics = {item.get("key"): item for item in payload.get("metrics", [])}
    journal_metric = metrics.get("journal_accuracy") or {}
    stability_metric = metrics.get("data_stability") or {}

    journal_details = str(journal_metric.get("details") or "")
    stability_details = str(stability_metric.get("details") or "")

    assert "قيود غير متوازنة: 0" in journal_details
    assert "سطور غير صحيحة: 0" in journal_details
    assert "سطور بلا حساب: 0" in journal_details
    assert "روابط حسابات مفقودة: 0" in stability_details


def test_known_final_report_direct_file_download_works(base_url):
    response = requests.get(f"{base_url}/api/erp-health-report/files/{KNOWN_FINAL_REPORT_ID}", timeout=180)
    assert response.status_code == 200, response.text
    assert response.headers.get("content-type", "").startswith("application/pdf")
    assert response.content[:4] == b"%PDF"


def test_audit_logs_include_erp_reset_correction_path(base_url, admin_token):
    response = requests.get(
        f"{base_url}/api/admin/security/audit-logs",
        params={"limit": 1000},
        headers=_headers(admin_token),
        timeout=120,
    )
    assert response.status_code == 200, response.text
    logs = response.json()

    matching = [
        item for item in logs
        if str(item.get("path") or "").startswith("/api/system/erp-reset-correction")
        or str(item.get("path") or "").startswith("/system/erp-reset-correction")
    ]
    assert len(matching) >= 1
