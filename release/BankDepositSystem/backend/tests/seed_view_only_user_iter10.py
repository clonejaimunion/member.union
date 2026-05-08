"""Create or reset a deterministic view_reports-only user for UI permission testing."""

import os
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@123"
VIEW_USERNAME = "ui_viewonly_iter10_fixed"
VIEW_PASSWORD = "ViewOnly@123"


def main() -> int:
    if not BASE_URL:
        print("Missing REACT_APP_BACKEND_URL")
        return 1

    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    login = session.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    if login.status_code != 200:
        print(f"Admin login failed: {login.status_code} {login.text}")
        return 1

    token = login.json().get("token")
    if not token:
        print("No admin token returned (possible 2FA requirement)")
        return 1

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    users_resp = session.get(f"{BASE_URL}/api/admin/users", headers=headers, timeout=30)
    if users_resp.status_code != 200:
        print(f"List users failed: {users_resp.status_code} {users_resp.text}")
        return 1

    users = users_resp.json()
    existing = next((u for u in users if u.get("username") == VIEW_USERNAME), None)

    if existing:
        update_resp = session.put(
            f"{BASE_URL}/api/admin/users/{existing['id']}",
            headers=headers,
            json={
                "password": VIEW_PASSWORD,
                "is_active": True,
                "permissions": {
                    "enter_deposits": False,
                    "view_reports": True,
                    "edit_deposits": False,
                    "manage_users": False,
                },
            },
            timeout=30,
        )
        if update_resp.status_code != 200:
            print(f"Update user failed: {update_resp.status_code} {update_resp.text}")
            return 1
        print(f"Updated user: {VIEW_USERNAME} / {VIEW_PASSWORD}")
        return 0

    create_resp = session.post(
        f"{BASE_URL}/api/admin/users",
        headers=headers,
        json={
            "username": VIEW_USERNAME,
            "password": VIEW_PASSWORD,
            "permissions": {
                "enter_deposits": False,
                "view_reports": True,
                "edit_deposits": False,
                "manage_users": False,
            },
            "is_active": True,
        },
        timeout=30,
    )
    if create_resp.status_code != 200:
        print(f"Create user failed: {create_resp.status_code} {create_resp.text}")
        return 1

    print(f"Created user: {VIEW_USERNAME} / {VIEW_PASSWORD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
