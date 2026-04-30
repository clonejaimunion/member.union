"""Iteration 33: Localhost/offline packaging regression checks."""

# Module: Localhost UI/API serving checks
# Feature: Offline-ready release artifact validation

from pathlib import Path

import requests


BASE_LOCAL_URL = "http://localhost:8001"
PUBLIC_ORGS_ENDPOINT = f"{BASE_LOCAL_URL}/api/organizations/public"


def test_localhost_root_serves_react_html():
    response = requests.get(BASE_LOCAL_URL, timeout=20)

    assert response.status_code == 200
    body = response.text.lower()
    assert "<!doctype html" in body
    assert "<div id=\"root\"" in body


def test_public_organizations_returns_two_local_orgs():
    response = requests.get(PUBLIC_ORGS_ENDPOINT, timeout=20)

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) == 2

    org_ids = {org.get("id") for org in payload}
    assert org_ids == {"general-union", "social-solidarity"}

    for org in payload:
        assert isinstance(org.get("name"), str) and org["name"].strip()
        assert isinstance(org.get("login_label"), str) and org["login_label"].strip()
        assert isinstance(org.get("modules"), dict)


def test_release_frontend_build_has_no_preview_domain_and_has_localhost_reference():
    build_dir = Path("/app/release/BankDepositSystem/frontend/build")
    assert build_dir.exists() and build_dir.is_dir()

    preview_domain = "interest-calculator-12.preview.emergentagent.com"
    localhost_ref = "localhost:8001"

    preview_hits = []
    localhost_hits = []

    for path in build_dir.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if preview_domain in text:
            preview_hits.append(str(path))
        if localhost_ref in text:
            localhost_hits.append(str(path))

    assert preview_hits == []
    assert len(localhost_hits) >= 1


def test_release_backend_wheels_exist_for_offline_install():
    wheel_dir = Path("/app/release/BankDepositSystem/backend/wheels")
    assert wheel_dir.exists() and wheel_dir.is_dir()

    wheels = list(wheel_dir.glob("*.whl"))
    assert len(wheels) > 0
    wheel_names = {wheel.name.lower() for wheel in wheels}
    assert any(name.startswith("colorama-") for name in wheel_names)


def test_setup_exe_exists_and_is_not_empty():
    setup_exe = Path("/app/dist/BankDepositSystemSetup.exe")
    assert setup_exe.exists() and setup_exe.is_file()
    assert setup_exe.stat().st_size > 0
