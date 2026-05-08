"""Iteration 86 - Windows silent startup packaging and branding regression checks."""

from pathlib import Path
import os

import requests
from dotenv import dotenv_values


ROOT_DIR = Path("/app")
LOCAL_INSTALL_DIR = ROOT_DIR / "local_install"
RELEASE_DIR = ROOT_DIR / "release" / "BankDepositSystem"
DIST_SETUP_PATH = ROOT_DIR / "dist" / "BankDepositSystemSetup.exe"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _get_base_url() -> str:
    base_url = os.environ.get("REACT_APP_BACKEND_URL")
    if base_url:
        return base_url
    env_values = dotenv_values(str(ROOT_DIR / "frontend" / ".env"))
    fallback = env_values.get("REACT_APP_BACKEND_URL")
    assert fallback, "REACT_APP_BACKEND_URL env var is required"
    return str(fallback)


def _assert_worker_runtime_strategy(content: str) -> None:
    lowered = content.lower()
    assert "backend\\wheels_win" in lowered
    assert "requirements-runtime.txt" in lowered
    assert "windows_wheels_ready.txt" in lowered
    assert "--no-index --find-links" in lowered
    assert "bank_deposit_runtime_ready_py311.flag" in lowered
    assert 'if "%deps_ready%"=="0"' in lowered
    assert "import fastapi, motor.motor_asyncio" in lowered
    assert "pip install --timeout 15 --retries 1" in lowered
    assert "pip_default_timeout=15" in lowered
    assert "pip_retries=1" in lowered


def _assert_splash_waits_for_health_with_timeout(content: str) -> None:
    lowered = content.lower()
    compact = lowered.replace(" ", "")
    assert "/api/health" in lowered
    assert "/api/app-settings/public" not in lowered
    assert "varmaxwaitms=180000;" in compact
    assert "showstartupfailure" in lowered
    assert "تعذر إكمال تشغيل الخدمات الخلفية" in content
    assert "startup_error.txt" in lowered


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
        "backend/requirements-runtime.txt",
        "backend/wheels_win/WINDOWS_WHEELS_READY.txt",
        "mongodb/bin/mongod.exe",
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


def test_worker_uses_offline_windows_wheels_and_skips_repeated_install():
    content = _read_text(LOCAL_INSTALL_DIR / "start_system_worker.bat")
    _assert_worker_runtime_strategy(content)
    lowered = content.lower()

    assert "python 3.11 is required" in lowered
    assert "/api/health" in lowered


def test_worker_starts_mongodb_before_backend_and_reports_failures():
    content = _read_text(LOCAL_INSTALL_DIR / "start_system_worker.bat").lower()

    assert "mongodb\\bin\\mongod.exe" in content
    assert "mongo-data" in content
    assert "mongodb.log" in content
    assert "start-service -name mongodb" in content
    assert "start-process -filepath $exe" in content
    assert "--dbpath" in content
    assert "127.0.0.1',27017" in content
    assert "goto mongo_ready" in content
    assert "mongodb did not start" in content
    assert "startup_error.txt" in content
    assert content.find("mongo_ready") < content.find("run_backend_hidden.vbs")


def test_release_worker_keeps_same_runtime_strategy():
    content = _read_text(RELEASE_DIR / "start_system_worker.bat")
    _assert_worker_runtime_strategy(content)
    lowered = content.lower()
    assert "mongodb\\bin\\mongod.exe" in lowered
    assert "start-process -filepath $exe" in lowered
    assert "mongodb did not start" in lowered


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
    assert "/api/health" in content
    assert "maxWaitMs" in content
    assert "startup_error.txt" in content
    assert "readStartupError" in content


def test_splash_uses_health_wait_and_guardrails_in_local_and_release():
    local_content = _read_text(LOCAL_INSTALL_DIR / "splash.hta")
    release_content = _read_text(RELEASE_DIR / "splash.hta")
    _assert_splash_waits_for_health_with_timeout(local_content)
    _assert_splash_waits_for_health_with_timeout(release_content)


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
    base_url = _get_base_url()

    response = requests.get(f"{base_url.rstrip('/')}/api/download/setup", timeout=60)

    assert response.status_code == 200
    assert len(response.content) == DIST_SETUP_PATH.stat().st_size


# Health endpoint smoke for splash lightweight wait probe
def test_health_endpoint_returns_200_with_small_payload():
    base_url = _get_base_url()

    response = requests.get(f"{base_url.rstrip('/')}/api/health", timeout=15)

    assert response.status_code == 200
    payload = response.json()
    assert payload.get("status") == "ok"
    assert payload.get("service") == "bank-deposit-system"
    assert len(payload.keys()) <= 4


def test_release_contains_runtime_requirements_and_windows_wheels():
    runtime_req_path = RELEASE_DIR / "backend" / "requirements-runtime.txt"
    wheels_dir = RELEASE_DIR / "backend" / "wheels_win"
    marker_path = wheels_dir / "WINDOWS_WHEELS_READY.txt"

    assert runtime_req_path.exists()
    assert marker_path.exists()
    assert len(list(wheels_dir.glob("*.whl"))) > 0


def test_release_contains_bundled_portable_mongodb_executable():
    mongod_path = RELEASE_DIR / "mongodb" / "bin" / "mongod.exe"

    assert mongod_path.exists()
    assert mongod_path.stat().st_size > 10_000_000
