"""Iteration 23 seed: create stable banking-expense movement for Trial Balance UI checks."""

import os

import pytest
import requests
from dotenv import dotenv_values


# Seed data for UI verification: trial balance movement in year 2101/month 11
ENV_BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
FILE_BASE_URL = dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL")
BASE_URL = (ENV_BASE_URL or FILE_BASE_URL or "").rstrip("/")


def _headers(token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _login():
    return requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "admin_takaful", "password": "Admin@123", "organization_id": "social-solidarity"},
        headers=_headers(),
        timeout=30,
    )


def test_seed_trial_balance_ui_data():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not configured")

    login = _login()
    assert login.status_code == 200, login.text
    token = login.json().get("token")
    assert token

    payload = {
        "bank_id": "industrial-development",
        "year": 2101,
        "month": 11,
        "items": [{"statement": "TEST ITER23 UI TB", "count": 1, "amount": 100}],
    }
    response = requests.put(
        f"{BASE_URL}/api/banking-expenses/manual",
        json=payload,
        headers=_headers(token),
        timeout=30,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["year"] == 2101
    assert data["month"] == 11
    assert data["items"][0]["total"] == 100
