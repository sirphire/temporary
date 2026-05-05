import json
from typing import Dict, List

import gspread
import streamlit as st
from google.oauth2.service_account import Credentials

from config import SHEET_COLUMNS

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _get_credentials():
    """
    Streamlit Cloud secrets format:
    [gcp_service_account]
    type = "service_account"
    project_id = "..."
    private_key_id = "..."
    private_key = "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"
    client_email = "..."
    client_id = "..."
    auth_uri = "https://accounts.google.com/o/oauth2/auth"
    token_uri = "https://oauth2.googleapis.com/token"
    auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
    client_x509_cert_url = "..."
    """
    info = dict(st.secrets["gcp_service_account"])
    return Credentials.from_service_account_info(info, scopes=SCOPES)


@st.cache_resource(show_spinner=False)
def get_client():
    return gspread.authorize(_get_credentials())


def open_sheet(sheet_url_or_id: str, worksheet_name: str = "products"):
    gc = get_client()
    if sheet_url_or_id.startswith("http"):
        sh = gc.open_by_url(sheet_url_or_id)
    else:
        sh = gc.open_by_key(sheet_url_or_id)

    try:
        ws = sh.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=worksheet_name, rows=1000, cols=len(SHEET_COLUMNS))

    ensure_header(ws)
    return ws


def ensure_header(ws):
    header = ws.row_values(1)
    if header[: len(SHEET_COLUMNS)] != SHEET_COLUMNS:
        ws.update("A1:G1", [SHEET_COLUMNS])


def get_records(ws) -> List[Dict[str, str]]:
    ensure_header(ws)
    return ws.get_all_records()


def append_urls(ws, rows: List[Dict[str, str]]):
    if not rows:
        return 0

    existing = set()
    for rec in get_records(ws):
        url = str(rec.get("url", "")).strip()
        if url:
            existing.add(url)

    new_rows = []
    for row in rows:
        url = row.get("url", "").strip()
        if not url or url in existing:
            continue
        existing.add(url)
        new_rows.append([
            url,
            row.get("category", ""),
            row.get("title", ""),
            row.get("lens_rings", ""),
            row.get("status", "PENDING"),
            row.get("checked_at", ""),
            row.get("error", ""),
        ])

    if new_rows:
        ws.append_rows(new_rows, value_input_option="USER_ENTERED")

    return len(new_rows)


def next_pending_row(ws):
    values = ws.get_all_values()
    if len(values) <= 1:
        return None

    header = values[0]
    status_idx = header.index("status")
    url_idx = header.index("url")

    for i, row in enumerate(values[1:], start=2):
        status = row[status_idx].strip().upper() if len(row) > status_idx else ""
        url = row[url_idx].strip() if len(row) > url_idx else ""
        if url and status in ("", "PENDING", "ERROR"):
            return i, dict(zip(header, row))

    return None


def update_result(ws, row_number: int, result: Dict[str, str]):
    header = ws.row_values(1)
    current = ws.row_values(row_number)
    current += [""] * (len(header) - len(current))

    for key, val in result.items():
        if key in header:
            current[header.index(key)] = val

    end_col = chr(ord("A") + len(header) - 1)
    ws.update(f"A{row_number}:{end_col}{row_number}", [current], value_input_option="USER_ENTERED")


def stats(ws):
    recs = get_records(ws)
    total = len(recs)
    found = sum(1 for r in recs if str(r.get("lens_rings", "")).upper() == "FOUND")
    not_found = sum(1 for r in recs if str(r.get("lens_rings", "")).upper() == "NOT_FOUND")
    done = sum(1 for r in recs if str(r.get("status", "")).upper() == "DONE")
    pending = sum(1 for r in recs if str(r.get("status", "")).upper() in ("", "PENDING"))
    errors = sum(1 for r in recs if str(r.get("status", "")).upper() == "ERROR")
    return {
        "total": total,
        "done": done,
        "pending": pending,
        "found": found,
        "not_found": not_found,
        "errors": errors,
    }
