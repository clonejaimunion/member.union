"""Iteration 26: Membership import/report regression + auth playbook checks."""

import io
import os
import time
import uuid
import zipfile
from datetime import datetime

import pytest
import requests
from pymongo import MongoClient


def _resolve_base_url() -> str | None:
    direct = os.environ.get("REACT_APP_BACKEND_URL")
    if direct:
        return direct
    env_path = "/app/frontend/.env"
    if not os.path.exists(env_path):
        return None
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                value = line.split("=", 1)[1].strip()
                if value:
                    return value
    return None


BASE_URL = _resolve_base_url()


def _api(path: str) -> str:
    assert BASE_URL, "REACT_APP_BACKEND_URL is required for public-endpoint testing"
    return f"{BASE_URL.rstrip('/')}/api{path}"


def _build_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _build_minimal_xlsx(headers: list[str], rows: list[list[str]]) -> bytes:
    shared = []
    index_map = {}

    def s_idx(value: str) -> int:
        text = str(value)
        if text not in index_map:
            index_map[text] = len(shared)
            shared.append(text)
        return index_map[text]

    all_rows = [headers] + rows
    sheet_rows_xml = []
    for row_index, row in enumerate(all_rows, start=1):
        cells_xml = []
        for col_index, cell in enumerate(row, start=1):
            col_letter = chr(64 + col_index)
            cell_ref = f"{col_letter}{row_index}"
            idx = s_idx(cell)
            cells_xml.append(f'<c r="{cell_ref}" t="s"><v>{idx}</v></c>')
        sheet_rows_xml.append(f"<row r=\"{row_index}\">{''.join(cells_xml)}</row>")

    shared_items = "".join(f"<si><t>{value}</t></si>" for value in shared)
    shared_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'count="{len(shared)}" uniqueCount="{len(shared)}">{shared_items}</sst>'
    )
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(sheet_rows_xml)}</sheetData></worksheet>"
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" '
        'Target="sharedStrings.xml"/>'
        '</Relationships>'
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>'
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/sharedStrings.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
        '</Types>'
    )

    out = io.BytesIO()
    with zipfile.ZipFile(out, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        zf.writestr("xl/sharedStrings.xml", shared_xml)
    return out.getvalue()


def _build_minimal_docx(table_rows: list[list[str]]) -> bytes:
    def cell_xml(value: str) -> str:
        safe = str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f"<w:tc><w:p><w:r><w:t>{safe}</w:t></w:r></w:p></w:tc>"

    rows_xml = []
    for row in table_rows:
        rows_xml.append(f"<w:tr>{''.join(cell_xml(c) for c in row)}</w:tr>")

    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body><w:tbl>{''.join(rows_xml)}</w:tbl></w:body></w:document>"
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/></Relationships>'
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '</Types>'
    )

    out = io.BytesIO()
    with zipfile.ZipFile(out, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("word/document.xml", document_xml)
    return out.getvalue()


def _build_minimal_pdf(text_lines: list[str]) -> bytes:
    escaped_lines = [line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in text_lines]
    text_ops = ["BT", "/F1 11 Tf", "50 780 Td"]
    for idx, line in enumerate(escaped_lines):
        if idx == 0:
            text_ops.append(f"({line}) Tj")
        else:
            text_ops.append("T*")
            text_ops.append(f"({line}) Tj")
    text_ops.append("ET")
    stream_data = "\n".join(text_ops).encode("latin-1", errors="ignore")

    objects = []
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    objects.append(b"2 0 obj\n<< /Type /Pages /Count 1 /Kids [3 0 R] >>\nendobj\n")
    objects.append(b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>\nendobj\n")
    objects.append(f"4 0 obj\n<< /Length {len(stream_data)} >>\nstream\n".encode("latin-1") + stream_data + b"\nendstream\nendobj\n")
    objects.append(b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")

    pdf = b"%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf += obj

    xref_start = len(pdf)
    xref = [b"xref\n", f"0 {len(offsets)}\n".encode("latin-1"), b"0000000000 65535 f \n"]
    for offset in offsets[1:]:
        xref.append(f"{offset:010d} 00000 n \n".encode("latin-1"))
    trailer = (
        b"trailer\n"
        + f"<< /Size {len(offsets)} /Root 1 0 R >>\n".encode("latin-1")
        + b"startxref\n"
        + f"{xref_start}\n".encode("latin-1")
        + b"%%EOF"
    )
    return pdf + b"".join(xref) + trailer


def _import_file(token: str, governorate: str, committee: str, filename: str, payload: bytes, content_type: str):
    return requests.post(
        _api("/memberships/import"),
        headers=_build_headers(token),
        data={"governorate": governorate, "union_committee": committee},
        files={"file": (filename, payload, content_type)},
        timeout=40,
    )


@pytest.fixture(scope="module")
def social_token():
    response = requests.post(
        _api("/auth/login"),
        json={"username": "admin_takaful", "password": "Admin@123", "organization_id": "social-solidarity"},
        timeout=20,
    )
    if response.status_code != 200:
        response = requests.post(
            _api("/auth/login"),
            json={"username": "admin", "password": "Admin@123", "organization_id": "social-solidarity"},
            timeout=20,
        )
    if response.status_code != 200:
        pytest.skip(f"Social admin login failed: {response.status_code} {response.text}")
    return response.json()["token"]


@pytest.fixture(scope="module")
def union_token():
    response = requests.post(
        _api("/auth/login"),
        json={"username": "admin_union", "password": "Admin@123", "organization_id": "general-union"},
        timeout=20,
    )
    if response.status_code != 200:
        pytest.skip(f"Union admin login failed: {response.status_code} {response.text}")
    return response.json()["token"]


@pytest.fixture(scope="module", autouse=True)
def cleanup_seeded_memberships():
    # membership import/report cleanup for TEST_IT26 seeded rows
    yield
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        return
    client = MongoClient(mongo_url)
    try:
        client[db_name].memberships.delete_many(
            {
                "organization_id": "social-solidarity",
                "$or": [
                    {"name": {"$regex": "^TEST_IT26_"}},
                    {"union_committee": {"$regex": "^IT26_"}},
                ],
            }
        )
    finally:
        client.close()


def test_auth_cookie_is_httponly():
    response = requests.post(
        _api("/auth/login"),
        json={"username": "admin_takaful", "password": "Admin@123", "organization_id": "social-solidarity"},
        timeout=20,
    )
    if response.status_code != 200:
        response = requests.post(
            _api("/auth/login"),
            json={"username": "admin", "password": "Admin@123", "organization_id": "social-solidarity"},
            timeout=20,
        )
    assert response.status_code == 200, response.text
    assert "access_token=" in response.headers.get("set-cookie", "")
    assert "HttpOnly" in response.headers.get("set-cookie", "")


def test_bruteforce_lockout_after_5_failures():
    username = f"it26_lock_{str(uuid.uuid4())[:6]}"
    for _ in range(5):
        bad = requests.post(
            _api("/auth/login"),
            json={"username": username, "password": "wrong", "organization_id": "social-solidarity"},
            timeout=20,
        )
        assert bad.status_code == 401
    locked = requests.post(
        _api("/auth/login"),
        json={"username": username, "password": "wrong", "organization_id": "social-solidarity"},
        timeout=20,
    )
    assert locked.status_code == 429


def test_auth_cors_preflight_has_credentials_header():
    assert BASE_URL, "REACT_APP_BACKEND_URL is required"
    response = requests.options(
        _api("/auth/login"),
        headers={
            "Origin": BASE_URL.rstrip("/"),
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
        timeout=20,
    )
    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-origin") == BASE_URL.rstrip("/")
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_import_xlsx_ignores_extra_columns_and_uses_selected_location(social_token):
    suffix = str(uuid.uuid4())[:6]
    gov = "القاهرة"
    committee = f"IT26_XLSX_{suffix}"
    headers = [
        "رقم العضوية",
        "الاسم",
        "الرقم القومي",
        "تاريخ الميلاد",
        "العنوان",
        "في حالة الوفاة",
        "عمود زائد",
        "محافظة",
        "لجنة",
    ]
    rows = [
        [f"8100{suffix}", f"TEST_IT26_XLSX_A_{suffix}", f"2990101{int(time.time()) % 10000000:07d}", "1974-02-01", "عنوان 1", "مستفيد 1", "EXTRA1", "غير متوقع", "غير متوقع"],
        [f"8200{suffix}", f"TEST_IT26_XLSX_B_{suffix}", f"2980202{(int(time.time()) + 1) % 10000000:07d}", "1975-03-02", "عنوان 2", "مستفيد 2", "EXTRA2", "قيمة ملف", "قيمة ملف"],
    ]
    payload = _build_minimal_xlsx(headers, rows)
    response = _import_file(social_token, gov, committee, "it26.xlsx", payload, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["imported_count"] == 2
    assert body["skipped_count"] == 0
    assert all(member["governorate"] == gov for member in body["imported_members"])
    assert all(member["union_committee"] == committee for member in body["imported_members"])


def test_import_xlsx_rejects_duplicates_and_incomplete_rows(social_token):
    suffix = str(uuid.uuid4())[:6]
    gov = "الجيزة"
    committee = f"IT26_SKIP_{suffix}"
    member_no = f"8300{suffix}"
    national = f"2970303{int(time.time()) % 10000000:07d}"
    headers = ["رقم العضوية", "الاسم", "الرقم القومي", "تاريخ الميلاد", "العنوان", "في حالة الوفاة"]
    rows = [
        [member_no, f"TEST_IT26_OK_{suffix}", national, "1972-01-01", "عنوان", "مستفيد"],
        [member_no, f"TEST_IT26_DUP_{suffix}", f"2960404{(int(time.time()) + 2) % 10000000:07d}", "1972-01-01", "عنوان", "مستفيد"],
        [f"8400{suffix}", f"TEST_IT26_MISS_{suffix}", f"2950505{(int(time.time()) + 3) % 10000000:07d}", "", "عنوان", "مستفيد"],
    ]
    payload = _build_minimal_xlsx(headers, rows)
    response = _import_file(social_token, gov, committee, "it26_skip.xlsx", payload, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["imported_count"] == 1
    assert body["skipped_count"] == 2
    reasons = " | ".join(row.get("reason", "") for row in body.get("skipped_rows", []))
    assert ("مكرر" in reasons) or ("البيانات المطلوبة" in reasons)


def test_import_docx_table_works(social_token):
    suffix = str(uuid.uuid4())[:6]
    gov = "الإسكندرية"
    committee = f"IT26_DOCX_{suffix}"
    docx_rows = [
        ["رقم العضوية", "الاسم", "الرقم القومي", "تاريخ الميلاد", "العنوان", "في حالة الوفاة"],
        [f"8500{suffix}", f"TEST_IT26_DOCX_{suffix}", f"2940606{int(time.time()) % 10000000:07d}", "1973-06-06", "عنوان دوك", "مستفيد دوك"],
    ]
    payload = _build_minimal_docx(docx_rows)
    response = _import_file(
        social_token,
        gov,
        committee,
        "it26.docx",
        payload,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["imported_count"] == 1
    assert body["imported_members"][0]["union_committee"] == committee


def test_import_pdf_text_parses_or_returns_clear_skip_reason(social_token):
    suffix = str(int(time.time()))[-6:]
    gov = "سوهاج"
    committee = f"IT26_PDF_{suffix}"

    good_pdf = _build_minimal_pdf(
        [
            "membership no|name|national id|birth date|address|beneficiary",
            f"8600{suffix}|TEST_IT26_PDF_{suffix}|2930707{int(time.time()) % 10000000:07d}|1971-07-01|Address PDF|Beneficiary PDF",
        ]
    )
    good_response = _import_file(social_token, gov, committee, "it26_good.pdf", good_pdf, "application/pdf")
    assert good_response.status_code == 200, good_response.text
    good_body = good_response.json()
    if good_body["imported_count"] == 0:
        assert good_body["skipped_count"] >= 1
        assert "البيانات المطلوبة" in good_body["skipped_rows"][0]["reason"]
    else:
        assert good_body["imported_count"] >= 1

    bad_pdf = _build_minimal_pdf([
        "membership no|name",
        "8700X|INCOMPLETE ONLY",
    ])
    bad_response = _import_file(social_token, gov, committee, "it26_bad.pdf", bad_pdf, "application/pdf")
    assert bad_response.status_code == 200, bad_response.text
    bad_body = bad_response.json()
    assert bad_body["imported_count"] == 0
    assert bad_body["skipped_count"] >= 1
    assert "البيانات المطلوبة" in bad_body["skipped_rows"][0]["reason"]


def test_annual_report_shows_rows_totals_and_print_data_ready(social_token):
    year = datetime.utcnow().year
    response = requests.get(
        _api("/memberships/annual-report"),
        headers=_build_headers(social_token),
        params={"year": year},
        timeout=30,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "rows" in body and "totals" in body
    assert isinstance(body["rows"], list)
    totals = body["totals"]
    assert totals["governorate"] == "الإجمالي"
    assert totals["union_committee"] == "كل اللجان"
    assert totals["total_registered"] >= totals["new_members"]


def test_imported_data_visible_in_search_and_current_size_formula(social_token):
    name_prefix = "TEST_IT26_XLSX_A_"
    search = requests.get(
        _api("/memberships/search"),
        headers=_build_headers(social_token),
        params={"name": name_prefix},
        timeout=20,
    )
    assert search.status_code == 200, search.text
    search_rows = search.json()
    assert any(name_prefix in row["name"] for row in search_rows)

    size = requests.get(_api("/memberships/current-size"), headers=_build_headers(social_token), timeout=20)
    assert size.status_code == 200, size.text
    body = size.json()
    assert body["current_membership_size"] == body["total_members"] - body["retired_members"]


def test_membership_paths_blocked_for_general_union(union_token):
    response = requests.get(_api("/memberships"), headers=_build_headers(union_token), timeout=20)
    assert response.status_code == 404
