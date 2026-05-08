"""Iteration 86 - Windows silent startup packaging and branding regression checks."""

from pathlib import Path
import os

import requests


ROOT_DIR = Path("/app")
LOCAL_INSTALL_DIR = ROOT_DIR / "local_install"
RELEASE_DIR = ROOT_DIR / "release" / "BankDepositSystem"
DIST_SETUP_PATH = ROOT_DIR / "dist" / "BankDepositSystemSetup.exe"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# NSIS + launcher integration checks
def test_nsis_shortcuts_target_wscript_and_vbs_launcher():
    content = _read_text(LOCAL_INSTALL_DIR / "BankDepositSystem.nsi")
    assert 'CreateShortCut "$SMPROGRAMS\\Bank Deposit Interest System\\Bank Deposit System.lnk" "$SYSDIR\\wscript.exe"' in content
    assert 'CreateShortCut "$DESKTOP\\Bank Deposit System.lnk" "$SYSDIR\\wscript.exe"' in content
    assert '"$INSTDIR\\launch_bank_deposit_system.vbs"' in content


# Silent startup package files in release
def test_release_contains_required_silent_startup_files():
    required_files = [
        "launch_bank_deposit_system.vbs",
        "splash.hta",
        "start_system_worker.bat",
        "run_backend_hidden.vbs",
        "run_backend_server.bat",
    ]
    missing = [name for name in required_files if not (RELEASE_DIR / name).exists()]
    assert missing == []


# Batch hardening checks
def test_batch_files_have_no_pause_or_echo_on_and_use_localappdata_logs():
    for bat_name in ["start_system_worker.bat", "run_backend_server.bat"]:
        content = _read_text(LOCAL_INSTALL_DIR / bat_name)
        lowered = content.lower()

        assert "pause" not in lowered
        assert "echo on" not in lowered
        assert "@echo off" in lowered
        assert "%localappdata%\\bankdepositsystem\\logs" in lowered


# Splash behavior checks
def test_splash_hta_uses_official_logo_arabic_statuses_hidden_worker_and_localhost_open():
    content = _read_text(LOCAL_INSTALL_DIR / "splash.hta")

    assert "app_assets\\\\erp-official-logo.png" in content
    assert "جاري تهيئة النظام" in content
    assert "جاري فحص قاعدة البيانات" in content
    assert "جاري التحقق من الترخيص" in content
    assert "جاري تشغيل الموديولات" in content
    assert "جاري فتح الواجهة الرئيسية" in content
    assert 'shell.Run("cmd.exe /c \\\"" + appDir + "\\\\start_system_worker.bat\\\"", 0, false);' in content
    assert 'shell.Run("http://localhost:8001", 1, false);' in content


# Official logo propagation checks
def test_official_logo_exists_in_source_frontend_and_release_paths():
    assert (ROOT_DIR / "app_assets" / "erp-official-logo.png").exists()
    assert (ROOT_DIR / "frontend" / "public" / "assets" / "branding" / "erp-official-logo.png").exists()
    assert (RELEASE_DIR / "app_assets" / "erp-official-logo.png").exists()


# Frontend login branding checks
def test_login_page_uses_required_official_logo_selector_and_path():
    content = _read_text(ROOT_DIR / "frontend" / "src" / "pages" / "LoginPage.jsx")
    assert "const officialSystemLogo = \"/assets/branding/erp-official-logo.png\";" in content
    assert 'data-testid="login-official-logo-image"' in content


# Frontend module selection branding checks
def test_module_selection_contains_required_official_logo_selector():
    content = _read_text(ROOT_DIR / "frontend" / "src" / "pages" / "ModuleSelection.jsx")
    assert 'data-testid="module-selection-official-logo"' in content


# Installer artifact checks
def test_nsis_installer_exists_in_dist():
    assert DIST_SETUP_PATH.exists()
    assert DIST_SETUP_PATH.stat().st_size > 0


# Public API download endpoint checks
def test_download_setup_endpoint_returns_200_and_matches_installer_size():
    base_url = os.environ.get("REACT_APP_BACKEND_URL")
    assert base_url, "REACT_APP_BACKEND_URL env var is required"

    response = requests.get(f"{base_url.rstrip('/')}/api/download/setup", timeout=60)

    assert response.status_code == 200
    assert len(response.content) == DIST_SETUP_PATH.stat().st_size
