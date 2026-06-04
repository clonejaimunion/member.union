"""Static tests for the rebuilt Accrued Interest page.

These guard the new requirements:
- Deposit dropdown (all + per-deposit) replacing the grid of buttons.
- Year dropdown preserved.
- Dedicated print-only report section with 4 columns + grand total row.
- ExportReportButtons wired to the new section through printSelectors.
"""
from pathlib import Path

PAGE = Path("/app/frontend/src/pages/AccruedInterestPage.jsx")


def test_page_renders_new_dropdowns():
    text = PAGE.read_text(encoding="utf-8")
    assert 'data-testid="accrued-deposit-selector"' in text
    assert 'data-testid="accrued-deposit-option-all"' in text
    assert 'data-testid="accrued-year-selector"' in text
    assert "كل الودائع المسجلة" in text
    assert "وديعة رقم {deposit.deposit_number}" in text


def test_old_button_grid_removed():
    text = PAGE.read_text(encoding="utf-8")
    assert 'data-testid="accrued-deposit-picker-section"' not in text
    assert 'data-testid="accrued-deposit-all-button"' not in text


def test_dedicated_print_report_with_four_columns():
    text = PAGE.read_text(encoding="utf-8")
    assert 'data-testid="accrued-print-report"' in text
    assert 'data-testid="accrued-print-table"' in text
    for column in ["رقم الحساب", "رقم الوديعة", "مبلغ الوديعة", "العائد عن الفترة"]:
        assert column in text, f"missing column: {column}"
    assert 'data-testid="accrued-print-grand-total-row"' in text
    assert "الإجمالي العام للعائد عن الفترة" in text


def test_export_buttons_target_print_report_only():
    text = PAGE.read_text(encoding="utf-8")
    # The new section is the only target for print/export.
    assert 'printSelectors={["[data-testid=\'accrued-print-report\']"]}' in text
    assert 'selectors={["[data-testid=\'accrued-print-report\']"]}' in text


def test_old_full_table_hidden_from_print():
    text = PAGE.read_text(encoding="utf-8")
    # Old wrapper still in the DOM for screen, but hidden from print.
    assert 'data-testid="accrued-table-wrapper"' in text
    assert 'print:hidden" data-testid="accrued-table-wrapper"' in text
    # Old deposit sections likewise hidden from print.
    assert 'print:hidden" data-testid="accrued-deposit-sections"' in text
