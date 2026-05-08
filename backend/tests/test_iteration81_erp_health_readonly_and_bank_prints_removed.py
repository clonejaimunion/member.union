import os
from urllib.parse import urlparse

import pytest
import requests
from dotenv import dotenv_values


# ERP Health + removed bank-prints regression: API shape, direct PDF links, and read-only data integrity.
FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
ORG_ID = "social-solidarity"


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
def admin_token(base_url):
    response = requests.post(
        f"{base_url}/api/auth/login",
        json={"username": "admin", "password": "Admin@123", "organization_id": ORG_ID},
        headers=_headers(),
        timeout=60,
    )
    if response.status_code != 200:
        pytest.skip(f"admin login failed: {response.status_code} {response.text}")
    token = response.json().get("token")
    if not token:
        pytest.skip("admin token missing")
    return token


@pytest.fixture(scope="module")
def readonly_snapshot(base_url, admin_token):
    def _count(path: str, params: dict | None = None):
        response = requests.get(
            f"{base_url}{path}",
            params=params or {},
            headers=_headers(admin_token),
            timeout=90,
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert isinstance(payload, (list, dict))
        return payload

    journal_entries = _count("/api/journal-entries")
    reconciliations = _count("/api/banks/banque-misr/reconciliations")
    banks = _count("/api/banks")
    trial_balance = _count("/api/trial-balance", {"non_zero_only": "false"})
    banque_misr_bank = next((bank for bank in banks if bank.get("id") == "banque-misr"), None)
    assert banque_misr_bank is not None

    return {
        "journal_entries_count": len(journal_entries),
        "reconciliations_count": len(reconciliations),
        "trial_balance_rows_count": len(trial_balance.get("rows", [])),
        "banque_misr_opening_balance": float(banque_misr_bank.get("opening_balance") or 0),
        "banque_misr_opening_balance_date": banque_misr_bank.get("opening_balance_date"),
    }


def test_bank_prints_external_route_returns_404_after_removal(base_url, admin_token):
    response = requests.get(
        f"{base_url}/api/bank-prints/banque-misr/external-data",
        headers=_headers(admin_token),
        timeout=60,
    )
    assert response.status_code == 404, response.text
    body = response.json()
    assert "تم إلغاء مطبوعات بنكية" in body.get("detail", "")


def test_erp_health_report_json_shape_and_required_metrics(base_url, admin_token):
    response = requests.get(
        f"{base_url}/api/erp-health-report",
        headers=_headers(admin_token),
        timeout=180,
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert isinstance(body.get("overall_score"), int)
    assert 0 <= body["overall_score"] <= 100
    assert isinstance(body.get("metrics"), list)
    assert len(body["metrics"]) >= 8
    assert isinstance(body.get("recommendations"), list)
    assert len(body["recommendations"]) >= 1
    assert isinstance(body.get("direct_download_url"), str)

    required_metric_keys = {
        "journal_accuracy",
        "trial_balance_consistency",
        "bank_reconciliation_efficiency",
        "performance_metrics",
        "integration_score",
        "external_dependency",
        "data_stability",
        "audit_completeness",
    }
    returned_metric_keys = {item.get("key") for item in body["metrics"]}
    assert required_metric_keys.issubset(returned_metric_keys)


def test_erp_health_report_direct_download_url_is_external_and_public_pdf(base_url, admin_token):
    report_response = requests.get(
        f"{base_url}/api/erp-health-report",
        headers=_headers(admin_token),
        timeout=180,
    )
    assert report_response.status_code == 200, report_response.text
    direct_url = report_response.json().get("direct_download_url")
    assert isinstance(direct_url, str) and direct_url.startswith("http")

    api_host = urlparse(base_url).netloc
    direct_host = urlparse(direct_url).netloc
    assert direct_host == api_host

    direct_download_response = requests.get(direct_url, timeout=180)
    assert direct_download_response.status_code == 200
    assert direct_download_response.headers.get("content-type", "").startswith("application/pdf")
    assert direct_download_response.content[:4] == b"%PDF"


def test_erp_health_report_pdf_endpoint_returns_pdf_with_admin_token(base_url, admin_token):
    response = requests.get(
        f"{base_url}/api/erp-health-report/pdf",
        headers=_headers(admin_token),
        timeout=180,
    )
    assert response.status_code == 200, response.text
    assert response.headers.get("content-type", "").startswith("application/pdf")
    assert response.content[:4] == b"%PDF"


def test_erp_health_generation_is_readonly_on_core_collections(base_url, admin_token, readonly_snapshot):
    generate_response = requests.get(
        f"{base_url}/api/erp-health-report",
        headers=_headers(admin_token),
        timeout=180,
    )
    assert generate_response.status_code == 200, generate_response.text

    journal_after = requests.get(
        f"{base_url}/api/journal-entries",
        headers=_headers(admin_token),
        timeout=90,
    )
    assert journal_after.status_code == 200, journal_after.text

    reconciliations_after = requests.get(
        f"{base_url}/api/banks/banque-misr/reconciliations",
        headers=_headers(admin_token),
        timeout=90,
    )
    assert reconciliations_after.status_code == 200, reconciliations_after.text

    banks_after = requests.get(
        f"{base_url}/api/banks",
        headers=_headers(admin_token),
        timeout=90,
    )
    assert banks_after.status_code == 200, banks_after.text

    trial_balance_after = requests.get(
        f"{base_url}/api/trial-balance",
        params={"non_zero_only": "false"},
        headers=_headers(admin_token),
        timeout=90,
    )
    assert trial_balance_after.status_code == 200, trial_balance_after.text

    bank_print_requests_after = requests.get(
        f"{base_url}/api/bank-prints/requests",
        params={"bank_id": "banque-misr"},
        headers=_headers(admin_token),
        timeout=90,
    )
    assert bank_print_requests_after.status_code == 404, bank_print_requests_after.text

    banque_misr_after = next(
        (bank for bank in banks_after.json() if bank.get("id") == "banque-misr"),
        None,
    )
    assert banque_misr_after is not None

    assert len(journal_after.json()) == readonly_snapshot["journal_entries_count"]
    assert len(reconciliations_after.json()) == readonly_snapshot["reconciliations_count"]
    assert len(trial_balance_after.json().get("rows", [])) == readonly_snapshot["trial_balance_rows_count"]
    assert float(banque_misr_after.get("opening_balance") or 0) == readonly_snapshot["banque_misr_opening_balance"]
    assert banque_misr_after.get("opening_balance_date") == readonly_snapshot["banque_misr_opening_balance_date"]
