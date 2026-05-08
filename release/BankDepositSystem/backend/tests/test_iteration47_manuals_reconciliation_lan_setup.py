"""Iteration 47: manuals, reconciliation print data, LAN launcher, setup download, and auth playbook checks."""

# Module: Public training manuals + setup artifact checks
# Module: Reconciliation matched-balance API contract
# Module: Local install LAN launcher and frontend API fallback code checks
# Module: Auth playbook regression (cookies, CORS, lockout, bcrypt, seed admin behavior)

from __future__ import annotations

import os
import re
import uuid
from io import BytesIO
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values
from pypdf import PdfReader

try:
    from pymongo import MongoClient
except Exception:  # pragma: no cover
    MongoClient = None


frontend_env = dotenv_values("/app/frontend/.env")
backend_env = dotenv_values("/app/backend/.env")

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
LOCAL_API_URL = "http://localhost:8001"
MONGO_URL = os.environ.get("MONGO_URL") or backend_env.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME") or backend_env.get("DB_NAME")

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@123"
ADMIN_ORG = "general-union"


@pytest.fixture(scope="module")
def api_session():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is missing")
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def admin_headers(api_session):
    response = api_session.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD, "organization_id": ADMIN_ORG},
        timeout=25,
    )
    if response.status_code != 200:
        pytest.skip(f"Admin login failed: {response.status_code}")
    payload = response.json()
    token = payload.get("token")
    if not token:
        pytest.skip("No admin token returned")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def mongo_db():
    if MongoClient is None:
        pytest.skip("pymongo is not available")
    if not MONGO_URL or not DB_NAME:
        pytest.skip("MONGO_URL/DB_NAME missing")
    client = MongoClient(MONGO_URL)
    try:
        yield client[DB_NAME]
    finally:
        client.close()


def _assert_pdf_a4_ish(pdf_bytes: bytes):
    reader = PdfReader(BytesIO(pdf_bytes))
    assert len(reader.pages) >= 2
    first_page = reader.pages[0]
    width = float(first_page.mediabox.width)
    height = float(first_page.mediabox.height)
    assert 580 <= width <= 610
    assert 830 <= height <= 855
    return reader


def _page_text(reader: PdfReader, idx: int) -> str:
    return (reader.pages[idx].extract_text() or "").strip()


def test_public_manual_ar_pdf_returns_direct_pdf_and_a4(api_session):
    response = api_session.get(f"{BASE_URL}/api/admin/training/manual-ar.pdf", timeout=60)
    assert response.status_code == 200
    assert "application/pdf" in response.headers.get("content-type", "")
    reader = _assert_pdf_a4_ish(response.content)
    for idx in [0, 1]:
        resources = reader.pages[idx].get("/Resources") or {}
        x_objects = resources.get("/XObject") if hasattr(resources, "get") else None
        assert x_objects is not None


def test_public_manual_en_pdf_returns_direct_pdf_a4_and_programmer_name(api_session):
    response = api_session.get(f"{BASE_URL}/api/admin/training/manual-en.pdf", timeout=60)
    assert response.status_code == 200
    assert "application/pdf" in response.headers.get("content-type", "")
    reader = _assert_pdf_a4_ish(response.content)
    for idx in [0, 1]:
        resources = reader.pages[idx].get("/Resources") or {}
        x_objects = resources.get("/XObject") if hasattr(resources, "get") else None
        assert x_objects is not None

    server_text = Path("/app/backend/server.py").read_text(encoding="utf-8")
    assert 'display_owner = english_manual_label(owner, "Youssef Abdelghany Ahmed")' in server_text


def test_reconciliation_matched_payload_includes_status_and_calculated_balance(api_session, admin_headers):
    amount = 12345.67
    payload = {
        "period_label": f"ITER47-MATCH-{uuid.uuid4().hex[:6]}",
        "administration": "النقابة العامة للعاملين بالزراعة والري",
        "book_balance": amount,
        "bank_statement_balance": amount,
        "outstanding_checks": [],
        "collection_checks": [],
    }
    response = api_session.post(
        f"{BASE_URL}/api/banks/industrial-development/reconciliations",
        headers=admin_headers,
        json=payload,
        timeout=25,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_matched"] is True
    assert data["status_text"] == "الرصيد مطابق"
    assert float(data["calculated_balance"]) == pytest.approx(amount, abs=0.01)


def test_setup_download_returns_valid_exe_payload(api_session):
    response = api_session.get(f"{BASE_URL}/api/download/setup", timeout=60)
    assert response.status_code == 200
    assert response.content[:2] == b"MZ"
    assert len(response.content) > 1_000_000


def test_frontend_api_js_has_lan_origin_fallback_when_backend_env_is_localhost():
    text = Path("/app/frontend/src/lib/api.js").read_text(encoding="utf-8")
    assert "isBrowserLanHost" in text
    assert "isConfiguredLocalhost" in text
    assert "window.location.origin" in text
    assert re.search(r"isBrowserLanHost\s*&&\s*isConfiguredLocalhost", text)


def test_run_backend_bat_binds_0_0_0_0_for_lan_access():
    text = Path("/app/local_install/run_backend_server.bat").read_text(encoding="utf-8")
    assert "--host 0.0.0.0" in text
    assert "--port 8001" in text


def test_start_launcher_bat_shows_network_url_and_adds_firewall_rule():
    text = Path("/app/local_install/start_bank_deposit_system.bat").read_text(encoding="utf-8")
    assert "Network URL" in text
    assert "netsh advfirewall firewall add rule" in text
    assert "localport=8001" in text


def test_auth_login_sets_httponly_cookie(api_session):
    response = api_session.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD, "organization_id": ADMIN_ORG},
        timeout=25,
    )
    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie", "")
    assert "access_token=" in set_cookie
    assert "HttpOnly" in set_cookie


def test_auth_cors_preflight_allows_credentials_with_explicit_origin(api_session):
    target_base = LOCAL_API_URL
    response = api_session.options(
        f"{target_base}/api/auth/login",
        headers={
            "Origin": BASE_URL,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
        timeout=25,
    )
    assert response.status_code in [200, 204]
    assert response.headers.get("access-control-allow-credentials") == "true"
    allow_origin = response.headers.get("access-control-allow-origin", "")
    assert allow_origin and allow_origin != "*"


def test_auth_bruteforce_lockout_after_three_failures(api_session, mongo_db):
    username = "admin_union"
    org_id = "general-union"
    identifier = f"{org_id}:{username}"
    mongo_db.login_attempts.delete_many({"identifier": identifier})

    for _ in range(3):
        failed = api_session.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": username, "password": "WrongPass@123", "organization_id": org_id},
            timeout=20,
        )
        assert failed.status_code == 401

    locked = api_session.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": username, "password": "WrongPass@123", "organization_id": org_id},
        timeout=20,
    )
    assert locked.status_code == 429

    mongo_db.login_attempts.delete_many({"identifier": identifier})


def test_seed_admin_hashes_use_bcrypt_2b_prefix(mongo_db):
    for username in ["admin", "admin_union", "admin_takaful"]:
        user = mongo_db.users.find_one({"username": username}, {"_id": 0, "password_hash": 1})
        assert user and isinstance(user.get("password_hash"), str)
        assert user["password_hash"].startswith("$2b$")


def test_seed_admin_code_updates_existing_admin_when_password_changes():
    text = Path("/app/backend/server.py").read_text(encoding="utf-8")
    assert "if not verify_password(ADMIN_INITIAL_PASSWORD, existing.get(\"password_hash\", \"\"))" in text
    assert "document[\"password_hash\"] = hash_password(ADMIN_INITIAL_PASSWORD)" in text
    assert "await db.users.update_one({\"id\": existing[\"id\"]}, {\"$set\": document})" in text