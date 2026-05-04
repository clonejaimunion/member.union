import os
import time
import uuid
from datetime import date

import pytest
import requests


# Scope: membership import preview/commit with status + status_effective_date persistence.
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")


def _api(path: str) -> str:
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not configured")
    return f"{BASE_URL.rstrip('/')}/api{path}"


def _build_csv_bytes(member_number: str, member_name: str, national_id: str) -> bytes:
    csv_text = (
        "رقم العضوية,الاسم,الرقم القومي,تاريخ الميلاد,العنوان,في حالة الوفاة\n"
        f"{member_number},{member_name},{national_id},1974-05-20,عنوان اختبار,مستفيد اختبار\n"
    )
    return csv_text.encode("utf-8")


@pytest.fixture(scope="module")
def auth_header():
    response = requests.post(
        _api("/auth/login"),
        json={
            "username": "admin",
            "password": "Admin@123",
            "organization_id": "social-solidarity",
        },
        timeout=30,
    )
    if response.status_code != 200:
        pytest.skip(f"Login failed: {response.status_code} {response.text}")
    token = response.json().get("token")
    assert isinstance(token, str) and token
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def cleanup_members(auth_header):
    created_member_ids = []
    yield created_member_ids
    for member_id in created_member_ids:
        requests.delete(_api(f"/memberships/{member_id}"), headers=auth_header, timeout=30)


def test_import_preview_returns_selected_status_fields(auth_header):
    suffix = uuid.uuid4().hex[:6]
    member_number = f"59{int(time.time()) % 100000}{suffix[:1]}"
    national_id = f"3{str(int(time.time() * 1000) % 10**13).zfill(13)}"
    status_effective_date = date.today().isoformat()

    files = {
        "file": (
            f"iter59_preview_{suffix}.csv",
            _build_csv_bytes(member_number, f"TEST_IT59_PREVIEW_{suffix}", national_id),
            "text/csv",
        )
    }
    data = {
        "governorate": f"IT59_GOV_{suffix}",
        "union_committee": f"IT59_COM_{suffix}",
        "status": "retired",
        "status_effective_date": status_effective_date,
    }

    response = requests.post(_api("/memberships/import/preview"), headers=auth_header, data=data, files=files, timeout=40)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["accepted_count"] == 1
    assert isinstance(body.get("preview_id"), str) and body["preview_id"]

    first_row = body["accepted_rows"][0]
    assert first_row["status"] == "retired"
    assert first_row["status_label"] == "معاش"
    assert first_row["status_effective_date"] == status_effective_date


def test_import_commit_persists_non_active_status_and_subscription_stop_date(auth_header, cleanup_members):
    suffix = uuid.uuid4().hex[:6]
    member_number = f"59{int(time.time()) % 100000}{suffix[:1]}"
    national_id = f"3{str((int(time.time() * 1000) + 77) % 10**13).zfill(13)}"
    status_effective_date = date.today().isoformat()

    preview_files = {
        "file": (
            f"iter59_commit_{suffix}.csv",
            _build_csv_bytes(member_number, f"TEST_IT59_COMMIT_{suffix}", national_id),
            "text/csv",
        )
    }
    preview_data = {
        "governorate": f"IT59_GOV_{suffix}",
        "union_committee": f"IT59_COM_{suffix}",
        "status": "resigned",
        "status_effective_date": status_effective_date,
    }

    preview_response = requests.post(
        _api("/memberships/import/preview"), headers=auth_header, data=preview_data, files=preview_files, timeout=40
    )
    assert preview_response.status_code == 200, preview_response.text
    preview_body = preview_response.json()
    assert preview_body["accepted_count"] == 1

    commit_response = requests.post(
        _api("/memberships/import/commit"),
        headers={**auth_header, "Content-Type": "application/json"},
        json={"preview_id": preview_body["preview_id"]},
        timeout=40,
    )
    assert commit_response.status_code == 200, commit_response.text
    commit_body = commit_response.json()
    assert commit_body["imported_count"] == 1

    imported_member = commit_body["imported_members"][0]
    cleanup_members.append(imported_member["id"])
    assert imported_member["status"] == "resigned"
    assert imported_member["status_label"] == "مستقيل"
    assert imported_member["status_effective_date"] == status_effective_date
    assert imported_member["subscription_stop_date"] == status_effective_date


def test_import_commit_active_status_keeps_subscription_stop_date_null(auth_header, cleanup_members):
    suffix = uuid.uuid4().hex[:6]
    member_number = f"59{int(time.time()) % 100000}{suffix[:1]}"
    national_id = f"3{str((int(time.time() * 1000) + 199) % 10**13).zfill(13)}"

    preview_files = {
        "file": (
            f"iter59_active_{suffix}.csv",
            _build_csv_bytes(member_number, f"TEST_IT59_ACTIVE_{suffix}", national_id),
            "text/csv",
        )
    }
    preview_data = {
        "governorate": f"IT59_GOV_{suffix}",
        "union_committee": f"IT59_COM_{suffix}",
        "status": "active",
    }

    preview_response = requests.post(
        _api("/memberships/import/preview"), headers=auth_header, data=preview_data, files=preview_files, timeout=40
    )
    assert preview_response.status_code == 200, preview_response.text
    preview_body = preview_response.json()
    assert preview_body["accepted_count"] == 1
    assert preview_body["accepted_rows"][0]["status"] == "active"
    assert preview_body["accepted_rows"][0]["status_effective_date"] is None

    commit_response = requests.post(
        _api("/memberships/import/commit"),
        headers={**auth_header, "Content-Type": "application/json"},
        json={"preview_id": preview_body["preview_id"]},
        timeout=40,
    )
    assert commit_response.status_code == 200, commit_response.text
    commit_body = commit_response.json()
    assert commit_body["imported_count"] == 1

    imported_member = commit_body["imported_members"][0]
    cleanup_members.append(imported_member["id"])
    assert imported_member["status"] == "active"
    assert imported_member["status_label"] == "فعال"
    assert imported_member["subscription_stop_date"] is None
