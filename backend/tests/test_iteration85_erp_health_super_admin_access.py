import os
import uuid
from urllib.parse import urlparse

import pytest
import requests
from dotenv import dotenv_values


# ERP Health access-control regression: super-admin-only API guards and protected direct PDF files.
FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL") or "").rstrip("/")


def _headers(token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _login(base_url: str, username: str, password: str, organization_id: str):
    return requests.post(
        f"{base_url}/api/auth/login",
        json={"username": username, "password": password, "organization_id": organization_id},
        headers=_headers(),
        timeout=60,
    )


@pytest.fixture(scope="session")
def base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not configured")
    return BASE_URL


@pytest.fixture(scope="session")
def super_admin_login_response(base_url):
    response = _login(base_url, "admin", "Admin@123", "general-union")
    if response.status_code != 200:
        pytest.skip(f"super admin login failed: {response.status_code} {response.text}")
    return response


@pytest.fixture(scope="session")
def super_admin_token(super_admin_login_response):
    token = super_admin_login_response.json().get("token")
    if not token:
        pytest.skip("super admin token missing")
    return token


@pytest.fixture(scope="session")
def non_super_admin_token(base_url):
    response = _login(base_url, "admin_union", "Admin@123", "general-union")
    if response.status_code != 200:
        pytest.skip(f"non-super admin login failed: {response.status_code} {response.text}")
    token = response.json().get("token")
    if not token:
        pytest.skip("non-super admin token missing")
    return token


def test_login_sets_http_only_cookie_for_auth(super_admin_login_response):
    body = super_admin_login_response.json()
    assert body.get("token")
    assert body.get("user", {}).get("role") == "super_admin"

    set_cookie = super_admin_login_response.headers.get("set-cookie", "")
    assert "access_token=" in set_cookie
    assert "HttpOnly" in set_cookie


def test_erp_health_endpoints_require_token(base_url):
    json_response = requests.get(f"{base_url}/api/erp-health-report", timeout=90)
    assert json_response.status_code == 401
    assert "تسجيل الدخول" in json_response.json().get("detail", "")

    pdf_response = requests.get(f"{base_url}/api/erp-health-report/pdf", timeout=90)
    assert pdf_response.status_code == 401
    assert "تسجيل الدخول" in pdf_response.json().get("detail", "")

    files_response = requests.get(f"{base_url}/api/erp-health-report/files/{uuid.uuid4()}", timeout=90)
    assert files_response.status_code == 401
    assert "تسجيل الدخول" in files_response.json().get("detail", "")


def test_non_super_admin_cannot_access_erp_health_endpoints(base_url, non_super_admin_token):
    json_response = requests.get(
        f"{base_url}/api/erp-health-report",
        headers=_headers(non_super_admin_token),
        timeout=90,
    )
    assert json_response.status_code == 403
    assert "السوبر أدمن" in json_response.json().get("detail", "")

    pdf_response = requests.get(
        f"{base_url}/api/erp-health-report/pdf",
        headers=_headers(non_super_admin_token),
        timeout=90,
    )
    assert pdf_response.status_code == 403
    assert "السوبر أدمن" in pdf_response.json().get("detail", "")

    files_response = requests.get(
        f"{base_url}/api/erp-health-report/files/{uuid.uuid4()}",
        headers=_headers(non_super_admin_token),
        timeout=90,
    )
    assert files_response.status_code == 403
    assert "السوبر أدمن" in files_response.json().get("detail", "")


def test_super_admin_can_generate_report_and_download_protected_file(base_url, super_admin_token):
    report_response = requests.get(
        f"{base_url}/api/erp-health-report",
        headers=_headers(super_admin_token),
        timeout=180,
    )
    assert report_response.status_code == 200, report_response.text
    report = report_response.json()

    assert isinstance(report.get("id"), str) and report["id"]
    assert isinstance(report.get("overall_score"), int)
    assert isinstance(report.get("metrics"), list) and len(report["metrics"]) >= 1
    assert isinstance(report.get("direct_download_url"), str) and "/api/erp-health-report/files/" in report["direct_download_url"]

    parsed_base = urlparse(base_url)
    parsed_direct = urlparse(report["direct_download_url"])
    assert parsed_direct.netloc == parsed_base.netloc

    report_id_from_url = report["direct_download_url"].rstrip("/").split("/")[-1]
    assert report_id_from_url == report["id"]

    super_download = requests.get(
        f"{base_url}/api/erp-health-report/files/{report['id']}",
        headers=_headers(super_admin_token),
        timeout=180,
    )
    assert super_download.status_code == 200, super_download.text
    assert super_download.headers.get("content-type", "").startswith("application/pdf")
    assert super_download.content[:4] == b"%PDF"

    unauth_download = requests.get(
        f"{base_url}/api/erp-health-report/files/{report['id']}",
        timeout=120,
    )
    assert unauth_download.status_code == 401
    assert "تسجيل الدخول" in unauth_download.json().get("detail", "")


def test_super_admin_pdf_endpoint_returns_pdf(base_url, super_admin_token):
    response = requests.get(
        f"{base_url}/api/erp-health-report/pdf",
        headers=_headers(super_admin_token),
        timeout=180,
    )
    assert response.status_code == 200, response.text
    assert response.headers.get("content-type", "").startswith("application/pdf")
    assert response.content[:4] == b"%PDF"
