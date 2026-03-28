from __future__ import annotations

import argparse
import csv
import json
import re
from io import StringIO
from pathlib import Path
from urllib.parse import quote, urlparse

import gspread
import requests
from oauth2client.service_account import ServiceAccountCredentials


DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
ROSTER_SHEET_ID = "1KUVJ_FhXFqze92Nn6Q4PGyohI4rcMHYr2FhqFmW7SfQ"
ROSTER_TAB_NAME = "Roster Info"
ROSTER_RANGE = "B3:D650"


def extract_sheet_id(value: str) -> str:
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", value)
    if match:
        return match.group(1)
    return value.strip()


def build_candidate_urls(sheet_id: str, tab_name: str, cell_range: str) -> list[str]:
    tab = quote(tab_name, safe="")
    cell_range = quote(cell_range, safe="!:")
    return [
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={tab}&range={cell_range}",
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&sheet={tab}&range={cell_range}",
    ]


def fetch_public_range(sheet_id: str, tab_name: str, cell_range: str) -> str:
    session = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0"}

    for url in build_candidate_urls(sheet_id, tab_name, cell_range):
        response = session.get(url, headers=headers, timeout=30, allow_redirects=True)
        content_type = response.headers.get("content-type", "")
        text = response.text

        if response.ok and ("text/csv" in content_type or text.startswith('"') or "," in text[:200]):
            return text

        if "ServiceLogin" in response.url or "Sign in" in text or response.status_code in {401, 403}:
            raise PermissionError(
                "Google Sheet is not publicly readable from this environment. "
                "Share it publicly or export the tab to CSV first."
            )

    raise RuntimeError("Could not retrieve the requested sheet range as CSV.")


def fetch_authenticated_range(
    credentials_info: dict[str, str], sheet_id: str, tab_name: str, cell_range: str
) -> str:
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_info, DEFAULT_SCOPES)
    client = gspread.authorize(credentials)
    worksheet = client.open_by_key(sheet_id).worksheet(tab_name)
    values = worksheet.get(cell_range)

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerows(values)
    return buffer.getvalue()


def fetch_range_csv_text(
    sheet_id: str,
    tab_name: str,
    cell_range: str,
    credentials_info: dict[str, str] | None = None,
) -> str:
    if credentials_info:
        return fetch_authenticated_range(credentials_info, sheet_id, tab_name, cell_range)
    return fetch_public_range(sheet_id, tab_name, cell_range)


def write_csv_text(csv_text: str, output_path: Path) -> int:
    rows = list(csv.reader(csv_text.splitlines()))
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)
    return len(rows)


def default_output_name(sheet_id: str, tab_name: str) -> Path:
    safe_tab = re.sub(r"[^A-Za-z0-9._-]+", "_", tab_name).strip("_") or "sheet"
    return Path(f"{safe_tab}_{sheet_id[:8]}.csv")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a public Google Sheet tab/range to CSV.")
    parser.add_argument("sheet", help="Google Sheet URL or sheet id")
    parser.add_argument("--tab", required=True, help="Worksheet/tab name, for example 'Roster Info'")
    parser.add_argument("--range", dest="cell_range", required=True, help="A1 range, for example 'B3:D650'")
    parser.add_argument("--output", type=Path, default=None, help="Output CSV path")
    args = parser.parse_args()

    sheet_id = extract_sheet_id(args.sheet)
    output_path = args.output or default_output_name(sheet_id, args.tab)
    csv_text = fetch_public_range(sheet_id, args.tab, args.cell_range)
    row_count = write_csv_text(csv_text, output_path)
    print(f"Wrote {row_count} rows to {output_path}")


if __name__ == "__main__":
    main()
