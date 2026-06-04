"""Static tests for the rebuilt Statements page (Detailed Interest report).

These guard the new requirements:
- New 5-column print-only report inside StatementsPage.jsx.
- Columns: مسلسل | رقم الوديعة | الحالة | مبلغ الوديعة | عائد {period}.
- Active status augmented with maturity date when available.
- Grand total row for the period interest sum.
- ExportReportButtons routes to the new print section only.
- Backend exposes `maturity_date` on `DepositStatementRow` schema and endpoint.
"""
from pathlib import Path

PAGE = Path("/app/frontend/src/pages/StatementsPage.jsx")
BACKEND = Path("/app/backend/server.py")


def test_page_renders_new_print_report():
    text = PAGE.read_text(encoding="utf-8")
    assert 'data-testid="detailed-interest-print-report"' in text
    assert 'data-testid="detailed-interest-print-table"' in text
    for header_testid in [
        "detailed-interest-print-header-serial",
        "detailed-interest-print-header-deposit",
        "detailed-interest-print-header-status",
        "detailed-interest-print-header-amount",
        "detailed-interest-print-header-interest",
    ]:
        assert header_testid in text, f"missing header: {header_testid}"


def test_print_report_uses_active_with_maturity_status():
    text = PAGE.read_text(encoding="utf-8")
    assert "formatActiveStatus" in text
    # Runtime concatenation of "نشطة" + " حتى " + maturity_date.
    assert "حتى ${row.maturity_date}" in text
    # Status only takes maturity when row.status === active
    assert 'row.status === "active" && row.maturity_date' in text


def test_grand_total_row_for_period_interest():
    text = PAGE.read_text(encoding="utf-8")
    assert 'data-testid="detailed-interest-print-grand-total-row"' in text
    assert "إجمالي العائد عن" in text
    assert "totalCurrentInterest" in text


def test_export_buttons_target_new_print_section_only():
    text = PAGE.read_text(encoding="utf-8")
    assert 'printSelectors={["[data-testid=\'detailed-interest-print-report\']"]}' in text
    assert 'selectors={["[data-testid=\'detailed-interest-print-report\']"]}' in text


def test_old_full_table_is_hidden_from_print():
    text = PAGE.read_text(encoding="utf-8")
    assert 'print:hidden" data-testid="detailed-interest-table-wrapper"' in text


def test_backend_schema_exposes_maturity_date():
    text = BACKEND.read_text(encoding="utf-8")
    assert "class DepositStatementRow(BaseModel):" in text
    # The new optional field
    assert "maturity_date: Optional[str] = None" in text
    # The endpoint populates it
    assert "maturity_date=normalize_datetime(deposit.maturity_datetime).date().isoformat() if deposit.maturity_datetime else None" in text
