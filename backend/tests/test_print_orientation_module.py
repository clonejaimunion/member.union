"""Smoke tests for the new print orientation toggle frontend module.

These tests verify the static contents of the new JS module/components
without requiring a browser. They guard against regressions in:

- /app/frontend/src/lib/printOrientation.js
- /app/frontend/src/components/PrintOrientationToggle.jsx
- /app/frontend/src/components/ExportReportButtons.jsx
- Pages converted to use printNow / usePrintOrientation
"""
from pathlib import Path

ROOT = Path("/app/frontend/src")


def test_print_orientation_lib_exists_and_exports_api():
    content = (ROOT / "lib" / "printOrientation.js").read_text(encoding="utf-8")
    for token in [
        "usePrintOrientation",
        "printWithOrientation",
        "printNow",
        "getSavedPrintOrientation",
        "orientationOptions",
        "@page { size: A4 ${orientation}; }",
        "@page expenses-analysis-landscape",
        "@page reconciliation-single-page",
    ]:
        assert token in content, f"missing token: {token}"


def test_orientation_toggle_component_exists():
    content = (ROOT / "components" / "PrintOrientationToggle.jsx").read_text(encoding="utf-8")
    assert "PrintOrientationToggle" in content
    assert "orientationOptions" in content
    assert "data-testid" in content


def test_export_report_buttons_uses_orientation():
    content = (ROOT / "components" / "ExportReportButtons.jsx").read_text(encoding="utf-8")
    assert "usePrintOrientation" in content
    assert "printWithOrientation" in content
    assert "PrintOrientationToggle" in content
    assert "x:Orientation=\"${excelOrientation}\"" in content or "x:Orientation=\\\"${excelOrientation}\\\"" in content


def test_no_remaining_raw_window_print_in_app_code():
    """The only place that should call window.print() is the orientation library."""
    leftovers = []
    for path in ROOT.rglob("*.jsx"):
        text = path.read_text(encoding="utf-8")
        if "window.print()" in text:
            leftovers.append(str(path))
    for path in ROOT.rglob("*.js"):
        if "printOrientation.js" in str(path):
            continue
        text = path.read_text(encoding="utf-8")
        if "window.print()" in text:
            leftovers.append(str(path))
    assert leftovers == [], f"window.print() still used directly in: {leftovers}"


def test_critical_pages_import_print_helpers():
    expected = {
        "ActuarialStudyPage.jsx": ["usePrintOrientation", "printWithOrientation", "PrintOrientationToggle"],
        "ExpensesAnalysisPage.jsx": ["usePrintOrientation", "printWithOrientation", "PrintOrientationToggle"],
        "BanqueMisrPrintPage.jsx": ["usePrintOrientation", "printWithOrientation", "PrintOrientationToggle"],
        "FeasibilityStudyPage.jsx": ["printNow"],
        "CustodyAdvancesPage.jsx": ["printNow"],
        "FixedAssetsPage.jsx": ["printNow"],
        "FinancialStatementsPage.jsx": ["printNow"],
        "MembershipPage.jsx": ["printNow"],
        "TreasuryBanksPage.jsx": ["printNow"],
        "BankReconciliationPage.jsx": ["printNow"],
    }
    for filename, tokens in expected.items():
        text = (ROOT / "pages" / filename).read_text(encoding="utf-8")
        for token in tokens:
            assert token in text, f"{filename} missing token: {token}"


def test_index_css_keeps_existing_page_rules():
    """The new system must not break the existing @page rules in index.css."""
    text = (ROOT / "index.css").read_text(encoding="utf-8")
    assert "@page expenses-analysis-landscape" in text
    assert "@page reconciliation-single-page" in text
